"""
Script : RFI/main.py
But :
    Lire un flux RSS de RFI, télécharger les articles
    et les enregistrer dans un fichier JSON sans effacer les anciens
"""

import re
import unicodedata
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import feedparser
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
JSON_FILE = Path("articles.json")
DONE_FILE = Path("done.txt")
RSS_URL = "https://www.rfi.fr/fr/rss"
MAX_DAYS = 5
TIMEOUT_MS = 15000
MAX_RETRIES = 3  # nombre de tentatives

# --- UTILS ---
def read_done():
    if DONE_FILE.exists():
        return set(line.strip() for line in DONE_FILE.read_text(encoding="utf-8").splitlines())
    return set()

def mark_done(url):
    with DONE_FILE.open("a", encoding="utf-8") as f:
        f.write(url.strip() + "\n")

def is_recent(entry, max_days):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        article_date = datetime(*entry.published_parsed[:6])
        return article_date >= datetime.now() - timedelta(days=max_days)
    return True

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

def load_json():
    """Charge le JSON existant ou initialise une structure vide avec 'articles'."""
    if JSON_FILE.exists():
        with JSON_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
        if "articles" not in data:
            data["articles"] = []
        return data
    return {"articles": []}

def save_json(data):
    """Réécrit entièrement le fichier JSON (sans perte de données)."""
    with JSON_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def extract_clean_text(page):
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    article_div = soup.select_one(".t-content__article-wrapper")
    if not article_div:
        raise ValueError("Contenu introuvable via .t-content__article-wrapper")

    text = article_div.get_text(separator="\n", strip=True)
    text = clean_text(text)
    return text

async def process_article(article, page, data):
    """Télécharge l'article avec retries"""
    retries = 0
    success = False
    scraping_date = datetime.now().isoformat()
    try:
        if hasattr(article, "published_parsed") and article.published_parsed:
            date_pub = datetime(*article.published_parsed[:6]).isoformat()
        else:
            date_pub = None
    except Exception:
        date_pub = None
        
    while retries < MAX_RETRIES and not success:
        try:
            await page.goto(article.link, timeout=TIMEOUT_MS)
            await page.wait_for_timeout(3000)

            text = await extract_clean_text(page)
            title = clean_text(article.title.strip())
            text = text.strip()

            # ✅ AJOUT dans le JSON (sans effacer les anciens)
            data["articles"].append({
                "scraping_status": "scraped",
                "link": article.link,
                "provider": "RFI",
                "titre": title,
                "date": date_pub,
                "scraping_date": scraping_date,
                "language": "fr",
                "text": f"{title}\n\n{text}",
                "extraction_method": "playwright",
                "html_metadata": {},
                "statistics": {
                    "chars": len(text),
                    "words": len(text.split()),
                    "lines": len(text.split("\n"))
                }
            })

            print(f"✅ Article ajouté : {article.link}")
            success = True
        except Exception as e:
            retries += 1
            print(f"⚠️ Erreur ({retries}/{MAX_RETRIES}) sur {article.link} : {e}")
            if retries < MAX_RETRIES:
                print("🔄 Nouvelle tentative...")
                await asyncio.sleep(2)
            else:
                print(f"⏩ Abandon après {MAX_RETRIES} échecs.")
                data["urls"][article.link] = {
                    "scraping_status": "failed",
                    "error": str(e),
                    "scraping_date": scraping_date
                }

async def main():
    done_urls = read_done()
    data = load_json()  # <-- On charge une seule fois le JSON existant
    already_downloaded_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Charger et parser le flux RSS
        await page.goto(RSS_URL)
        rss_content = await page.evaluate("""() => fetch(window.location.href).then(r => r.text())""")
        feed = feedparser.parse(rss_content)

        for entry in feed.entries:
            print(f"🔍 {entry.link}")

            if entry.link in done_urls:
                print(f"⏩ Déjà téléchargé, on passe")
                already_downloaded_count += 1
                if already_downloaded_count >= 5:
                    break
                await asyncio.sleep(1)
                continue

            if not is_recent(entry, MAX_DAYS):
                continue

            mark_done(entry.link)
            done_urls.add(entry.link)

            await process_article(entry, page, data)
            save_json(data)  # <-- on sauve après chaque ajout
            await asyncio.sleep(2)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
