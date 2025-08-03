"""
Script : Africanews/main.py
But :
    Scraper les articles du flux RSS Africanews (https://fr.africanews.com/feed/rss?themes=news)
    Télécharger les articles et les sauvegarder dans un fichier JSON.

Date : 2025-08-02
"""

import unicodedata
import asyncio
import re
import json
from pathlib import Path
from urllib.parse import urlparse
import feedparser
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
BASE_DIR = Path("/home/user/Documents/scrap/Africa_News")
DONE_FILE = BASE_DIR / "done.txt"
JSON_FILE = BASE_DIR / "articles.json"
RSS_URL = "https://fr.africanews.com/feed/rss?themes=news"
TIMEOUT_MS = 30000
MAX_ALREADY_DONE = 5
MAX_RETRIES = 3

# --- UTILS ---
def read_done():
    if DONE_FILE.exists():
        return set(line.strip() for line in DONE_FILE.read_text(encoding="utf-8").splitlines())
    return set()

def mark_done(url):
    with DONE_FILE.open("a", encoding="utf-8") as f:
        f.write(url.strip() + "\n")

def clean_text(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("latin-1", "ignore").decode("latin-1")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

async def extract_content(page):
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.select_one("h1.article__title")
    if not h1:
        raise ValueError("❌ Titre introuvable (h1.article__title manquant)")
    title = h1.get_text(strip=True)

    article_div = soup.select_one("div.article-content__text")
    if not article_div:
        raise ValueError("❌ Contenu introuvable (div.article-content__text manquant)")
    text = article_div.get_text(separator="\n", strip=True)

    title = clean_text(title)
    text = clean_text(text)
    return title, text

async def process_article(url, page, data):
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            await page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            title, body = await extract_content(page)

            scraping_date = datetime.now().isoformat()
            file_mtime = scraping_date

            data["articles"].append({
                "scraping_status": "scraped",
                "link": url,
                "provider": "Africa_News",
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

            mark_done(url)

            # Sauvegarde immédiate après chaque article
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            print(f"✅ Article ajouté et sauvegardé : {url}")
            return True

        except Exception as e:
            attempt += 1
            print(f"⚠️ Erreur sur {url} (tentative {attempt}/{MAX_RETRIES}) : {e}")
            if attempt >= MAX_RETRIES:
                print(f"❌ Échec après {MAX_RETRIES} tentatives, on passe au suivant.")
                return False
            else:
                await asyncio.sleep(2)

async def main():
    done_urls = read_done()
    already_downloaded_count = 0
    data = {"articles": []}

    # Charger JSON existant si présent
    if JSON_FILE.exists():
        try:
            with open(JSON_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            print("⚠️ Impossible de lire articles.json, on repart à zéro.")

    print(f"📡 Lecture du flux RSS : {RSS_URL}")
    feed = feedparser.parse(RSS_URL)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for entry in feed.entries:
            url = entry.link
            if url in done_urls:
                print(f"⏩ Déjà téléchargé, on passe : {url}")
                already_downloaded_count += 1
                if already_downloaded_count >= MAX_ALREADY_DONE:
                    print("🛑 5 articles déjà scrapés → arrêt du script.")
                    break
                continue

            print(f"🔍 Scraping : {url}")

            success = await process_article(url, page, data)

            await asyncio.sleep(2)

        await browser.close()

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
