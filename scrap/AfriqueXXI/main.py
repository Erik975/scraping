"""
Script : AfriqueXXI/main.py
But :
    Lire un flux RSS d'afriquexxi.com, télécharger les articles
    et les exporter dans un JSON au fur et à mesure

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
BASE_DIR = Path("/home/user/Documents/scrap/AfriqueXXI")
DONE_FILE = BASE_DIR / "done.txt"
JSON_FILE = BASE_DIR / "articles.json"
RSS_URL = "https://afriquexxi.info/?page=backend&lang=frpage=backend&lang=fr"
TIMEOUT_MS = 15000


# --- UTILS ---
def read_done():
    if DONE_FILE.exists():
        return set(line.strip() for line in DONE_FILE.read_text(encoding="utf-8").splitlines())
    return set()

def save_json(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def normalize_linebreaks(text):
    text = re.sub(r"(?<![\.\?\!\:])\n(?![\n])", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()

def mark_done(url):
    with DONE_FILE.open("a", encoding="utf-8") as f:
        f.write(url.strip() + "\n")

def sanitize_filename(url):
    parsed = urlparse(url)
    return parsed.path.strip("/").replace("/", "_")[:100]

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

    article_div = soup.select_one("div.texte_article")
    if not article_div:
        raise ValueError("Contenu introuvable dans la page")

    text = article_div.get_text(separator="\n", strip=True)
    text = clean_text(text)
    return text

async def process_article(article, page, data, max_retries=3):
    attempt = 0
    while attempt < max_retries:
        try:
            await page.goto(article.link, timeout=TIMEOUT_MS)
            await page.wait_for_timeout(3000)

            text = await extract_clean_text(page)
            title = article.title.strip()
            text = normalize_linebreaks(text)
            title = clean_text(title)

            scraping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            article_data = {
                "scraping_status": "scraped",
                "link": article.link,
                "provider": "AfriqueXXI",
                "titre": title,
                "date": article.get("published", "inconnue"),
                "scraping_date": scraping_date,
                "language": "fr",
                "text": f"{title}\n\n{text}",
                "extraction_method": "Playwright (Chromium)",
                "html_metadata": {},
                "statistics": {
                    "chars": len(text),
                    "words": len(text.split()),
                    "lines": len(text.split("\n"))
                }
            }

            data["articles"].append(article_data)
            save_json(data)

            mark_done(article.link)
            print(f"✅ Article sauvegardé : {article.link}")
            return  # succès

        except Exception as e:
            attempt += 1
            print(f"⚠️ Erreur sur {article.link} (tentative {attempt}/{max_retries}) : {e}")
            if attempt >= max_retries:
                print(f"❌ Échec après {max_retries} tentatives, on passe à l'article suivant.")
            else:
                await asyncio.sleep(3)

async def main():
    done_urls = read_done()

    # Charger JSON existant ou initialiser
    if JSON_FILE.exists():
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"articles": []}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        feed = feedparser.parse(RSS_URL)

        for entry in feed.entries:
            print(f"🔍 {entry.link}")

            if entry.link in done_urls:
                print(f"⏩ Déjà téléchargé, on passe")
                await asyncio.sleep(1)
                continue

            # Suppression du filtre sur la date — on traite tous les articles
            await process_article(entry, page, data)
            await asyncio.sleep(2)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
