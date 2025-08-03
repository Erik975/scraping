"""
Script : Afrik/main.py
But :
    Lire un flux RSS d'Afrik.com, télécharger les articles
    et les enregistrer dans un fichier JSON unique

Date : 2025-07-29
"""

import re
import unicodedata
import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import json
import feedparser
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


# --- CONFIGURATION ---
BASE_DIR = Path("/home/user/Documents/scrap/Afrik")
DONE_FILE = BASE_DIR / "done.txt"
RSS_FILE = BASE_DIR / "afrik_rss.xml"
OUTPUT_JSON = BASE_DIR / "articles.json"
RSS_URL = "https://www.afrik.com/feed"
TIMEOUT_MS = 15000


# --- UTILS ---
def read_done():
    if DONE_FILE.exists():
        return set(line.strip() for line in DONE_FILE.read_text(encoding="utf-8").splitlines())
    return set()


def normalize_linebreaks(text):
    text = re.sub(r"(?<![\.\?\!\:])\n(?![\n])", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def mark_done(url):
    with DONE_FILE.open("a", encoding="utf-8") as f:
        f.write(url.strip() + "\n")


def clean_text(text):
    replacements = {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
        "\u2018": "'", "\u2019": "'", "\u02BC": "'",
        "\u201c": '"', "\u201d": '"', "\u00ab": '"', "\u00bb": '"',
        "\u2026": "...",
        "\u0152": "OE", "\u0153": "oe",
        "\ufb01": "fi", "\ufb02": "fl",
        "\u2122": "(TM)", "\u00ae": "(R)", "\u00a9": "(C)",
        "\u2039": "<", "\u203a": ">", "\u201a": ",", "\u201e": '"',
        "\u00b4": "'", "\u02c6": "^", "\u02dc": "~", "\u00b8": ",",
    }

    for cp in [
        "\u00a0", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004", "\u2005",
        "\u2006", "\u2007", "\u2008", "\u2009", "\u202f", "\u205f", "\u3000"
    ]:
        replacements[cp] = " "

    for src, dest in replacements.items():
        text = text.replace(src, dest)

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("latin-1", "ignore").decode("latin-1")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def extract_clean_text(page):
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Modifié pour correspondre à la structure HTML d'afrik.com
    article_div = soup.select_one(".td-post-content")
    if not article_div:
        raise ValueError("Contenu introuvable dans la page")

    text = article_div.get_text(separator="\n", strip=True)
    text = clean_text(text)
    return text


import json

async def process_article(article, page, data, max_retries=3):
    attempt = 0
    while attempt < max_retries:
        try:
            await page.goto(article.link, timeout=TIMEOUT_MS)
            await page.wait_for_timeout(3000)

            body = await extract_clean_text(page)
            title = article.title.strip()
            body = normalize_linebreaks(body)
            title = clean_text(title)
            scraping_date = datetime.now().isoformat()
            file_mtime = scraping_date

            data["articles"].append({
                "scraping_status": "imported_pdf",
                "link": article.link,
                "provider": "AfriqueXXI",
                "titre": title if title else "Titre inconnu",
                "date": file_mtime,
                "scraping_date": scraping_date,
                "language": "fr",
                "text": f"{title}\n\n{body}" if title else body,
                "extraction_method": "",
                "html_metadata": {},
                "statistics": {
                    "chars": len(body),
                    "words": len(body.split()),
                    "lines": len(body.split("\n"))
                }
            })

            mark_done(article.link)

            # Sauvegarde immédiate dans le fichier JSON
            with open(BASE_DIR / "articles.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            print(f"✅ Article ajouté et sauvegardé : {article.link}")
            return

        except Exception as e:
            attempt += 1
            print(f"⚠️ Erreur sur {article.link} (tentative {attempt}/{max_retries}) : {e}")
            if attempt >= max_retries:
                print(f"❌ Échec après {max_retries} tentatives, on passe au suivant.")
                return
            else:
                await asyncio.sleep(2)


async def main():
    done_urls = read_done()
    already_downloaded_count = 0
    data = {"articles": []}

    # Si articles.json existe déjà, on charge pour éviter doublons dans la session
    json_path = BASE_DIR / "articles.json"
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            print("⚠️ Impossible de lire articles.json, on repart à zéro.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(RSS_URL)
        rss_content = await page.evaluate("""() => fetch(window.location.href).then(r => r.text())""")
        RSS_FILE.write_text(rss_content, encoding="utf-8")

        feed = feedparser.parse(str(RSS_FILE))

        for entry in feed.entries:
            print(f"🔍 {entry.link}")

            if entry.link in done_urls:
                print(f"⏩ Déjà téléchargé, on passe")
                already_downloaded_count += 1
                if already_downloaded_count >= 5:
                    break
                await asyncio.sleep(1)
                continue

            # On ne filtre plus par date

            mark_done(entry.link)
            done_urls.add(entry.link)

            await process_article(entry, page, data)
            await asyncio.sleep(2)

        if RSS_FILE.exists():
            RSS_FILE.unlink()

        await browser.close()



if __name__ == "__main__":
    asyncio.run(main())
