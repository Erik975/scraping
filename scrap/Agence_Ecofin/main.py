"""
Script : Afrik/main.py
But :
    Lire plusieurs flux RSS d'Agence Ecofin, télécharger les articles
    et les enregistrer dans un JSON au lieu de PDF

Date : 2025-08-02
"""

import re
import unicodedata
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
import feedparser
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
BASE_DIR = Path("/home/user/Documents/scrap/Agence_Ecofin")
JSON_FILE = BASE_DIR / "articles.json"
DONE_FILE = BASE_DIR / "done.txt"
TIMEOUT_MS = 15000

# Liste des flux RSS Agence Ecofin
RSS_URLS = [
    "https://www.agenceecofin.com/obrss-2/agence-rss",
    "https://www.agenceecofin.com/obrss-2/finance-rss",
    "https://www.agenceecofin.com/obrss-2/gestionpublique-rss",
    "https://www.agenceecofin.com/obrss-2/hebdo-rss2",
    "https://www.agenceecofin.com/obrss-2/agro-rss",
    "https://www.agenceecofin.com/obrss-2/electricite-rss",
    "https://www.agenceecofin.com/obrss-2/hydrocarbures-rss",
    "https://www.agenceecofin.com/obrss-2/mines-rss",
    "https://www.agenceecofin.com/obrss-2/telecom-rss",
    "https://www.agenceecofin.com/obrss-2/comm-rss",
    "https://www.agenceecofin.com/obrss-2/droits-rss",
]

# --- UTILS ---
def read_done():
    if DONE_FILE.exists():
        return set(line.strip() for line in DONE_FILE.read_text(encoding="utf-8").splitlines())
    return set()

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
    """Extrait le texte de l'article depuis la page HTML"""
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    article_div = soup.select_one("div.itemIntroText")
    if not article_div:
        raise ValueError("Contenu introuvable dans la page")

    text = article_div.get_text(separator="\n", strip=True)
    return clean_text(text)

async def process_article(article, page, data, max_retries=3):
    """Télécharge un article et l’ajoute au JSON, avec retry en cas d’erreur"""
    attempt = 0
    while attempt < max_retries:
        try:
            await page.goto(article.link, timeout=TIMEOUT_MS)
            await page.wait_for_timeout(3000)

            text_content = await extract_clean_text(page)
            title = clean_text(article.title.strip())
            text_content = re.sub(r"(?<![\.\?\!\:])\n(?![\n])", " ", text_content)
            text_content = re.sub(r"\n{2,}", "\n\n", text_content)

            scraping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            data["articles"].append({
                "scraping_status": "scraped",
                "link": article.link,
                "provider": "Agence_Ecofin",
                "titre": title,
                "date": article.get("published", "inconnue"),
                "scraping_date": scraping_date,
                "language": "fr",
                "text": f"{title}\n\n{text_content}",
                "extraction_method": "Playwright (Chromium)",
                "html_metadata": {},
                "statistics": {
                    "chars": len(text_content),
                    "words": len(text_content.split()),
                    "lines": len(text_content.split("\n"))
                }
            })

            # Sauvegarde du JSON
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            print(f"✅ Article ajouté au JSON : {title}")
            return  # Succès, on quitte la fonction

        except Exception as e:
            attempt += 1
            print(f"⚠️ Erreur sur {article.link} (tentative {attempt}/{max_retries}) : {e}")
            if attempt >= max_retries:
                print(f"❌ Échec après {max_retries} tentatives, passage à l'article suivant.")
            else:
                await asyncio.sleep(3)  # Pause avant la prochaine tentative


async def main():
    done_urls = read_done()

    # Charger les articles déjà enregistrés si le JSON existe
    if JSON_FILE.exists():
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"articles": []}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for rss_url in RSS_URLS:
            print(f"\n📡 Lecture du flux RSS : {rss_url}")
            already_downloaded_count = 0

            # Lecture du flux RSS
            await page.goto(rss_url)
            rss_content = await page.evaluate("""() => fetch(window.location.href).then(r => r.text())""")
            feed = feedparser.parse(rss_content)

            for entry in feed.entries:
                print(f"🔍 {entry.link}")

                if entry.link in done_urls:
                    already_downloaded_count += 1
                    print(f"⏩ Déjà téléchargé ({already_downloaded_count}/10)")
                    if already_downloaded_count >= 10:
                        break
                    continue

                try:
                    await process_article(entry, page, data)
                    mark_done(entry.link)
                    done_urls.add(entry.link)
                except Exception as e:
                    print(f"⚠️ Erreur sur {entry.link} : {e}")

                await asyncio.sleep(2)


        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
