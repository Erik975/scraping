"""
Script : Mondafrique/main.py
But :
    Lire le flux RSS de Mondafrique, télécharger les articles
    et les stocker dans un JSON (avec 3 tentatives en cas d'erreur)

Auteur : PTH
Date : 2025-07-31
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
BASE_DIR = Path("/home/user/Documents/scrap/Mondafrique")
JSON_FILE = BASE_DIR / "articles.json"
DONE_FILE = BASE_DIR / "done.txt"
TIMEOUT_MS = 15000

# Flux RSS Mondafrique
RSS_URLS = [
    "https://mondafrique.com/feed/"
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

def normalize_linebreaks(text):
    """Nettoie les retours à la ligne superflus"""
    text = re.sub(r"(?<![\.\?\!\:])\n(?![\n])", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()

async def extract_clean_text(page):
    """Récupère le titre et le contenu nettoyé d’un article Mondafrique"""
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.select_one("h1.entry-title")
    content_div = soup.select_one("div.td-post-content")

    if not title_tag or not content_div:
        raise ValueError("Titre ou contenu introuvable dans la page")

    title = clean_text(title_tag.get_text(strip=True))
    text = clean_text(content_div.get_text(separator="\n", strip=True))
    return title, text

def load_json_data():
    """Charge ou initialise la structure JSON"""
    if JSON_FILE.exists():
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"articles": []}

def save_json_data(data):
    """Sauvegarde les données JSON"""
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def process_article(article, page, data):
    """Télécharge un article et l’ajoute dans le JSON"""
    await page.goto(article.link, timeout=TIMEOUT_MS)
    await page.wait_for_timeout(3000)

    title, body = await extract_clean_text(page)
    body = normalize_linebreaks(body)

    scraping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_pub = getattr(article, "published", scraping_date)

    data["articles"].append({
        "scraping_status": "scraped",
        "link": article.link,
        "provider": "Mondafrique",
        "titre": title if title else "Titre inconnu",
        "date": date_pub,
        "scraping_date": scraping_date,
        "language": "fr",
        "text": f"{title}\n\n{body}" if title else body,
        "extraction_method": "playwright",
        "html_metadata": {},
        "statistics": {
            "chars": len(body),
            "words": len(body.split()),
            "lines": len(body.split("\n"))
        }
    })

    print(f"✅ Article ajouté : {title}")

async def main():
    done_urls = read_done()
    data = load_json_data()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for rss_url in RSS_URLS:
            print(f"\n📡 Lecture du flux RSS : {rss_url}")
            await page.goto(rss_url)
            rss_content = await page.evaluate("""() => fetch(window.location.href).then(r => r.text())""")
            feed = feedparser.parse(rss_content)

            for entry in feed.entries:
                print(f"🔍 {entry.link}")

                if entry.link in done_urls:
                    print("⏩ Déjà téléchargé")
                    continue

                success = False
                for attempt in range(1, 4):  # 3 tentatives max
                    try:
                        await process_article(entry, page, data)
                        success = True
                        break
                    except Exception as e:
                        print(f"⚠️ Erreur tentative {attempt} sur {entry.link} : {e}")
                        if attempt < 3:
                            await asyncio.sleep(3)
                        else:
                            print(f"❌ Abandon après 3 échecs : {entry.link}")

                if success:
                    mark_done(entry.link)
                    done_urls.add(entry.link)
                    save_json_data(data)  # Sauvegarde après chaque article

                await asyncio.sleep(2)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
