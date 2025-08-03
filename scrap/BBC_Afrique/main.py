"""
Script : BBC_Afrique/main_json.py
But :
    Lire le flux RSS BBC Afrique, télécharger les articles
    et les sauvegarder dans un JSON.

Auteur : PTH (modifié par ChatGPT)
Date : 2025-08-02
"""

import re
import unicodedata
import asyncio
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import feedparser
import http.client
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import requests

# --- CONFIGURATION ---
BASE_DIR = Path("/home/user/Documents/scrap/BBC_Afrique")
JSON_FILE = BASE_DIR / "articles.json"
DONE_FILE = BASE_DIR / "done.txt"
TIMEOUT_MS = 15000

RSS_URL = "https://www.bbc.com/afrique/region/index.xml"


# --- UTILS ---
def read_done():
    """Lit la liste des articles déjà téléchargés"""
    if DONE_FILE.exists():
        return set(line.strip() for line in DONE_FILE.read_text(encoding="utf-8").splitlines())
    return set()

def mark_done(url):
    """Marque un article comme téléchargé"""
    with DONE_FILE.open("a", encoding="utf-8") as f:
        f.write(url.strip() + "\n")

def sanitize_filename(url):
    """Crée un nom de fichier utilisable"""
    parsed = urlparse(url)
    return parsed.path.strip("/").replace("/", "_")[:100]

def clean_text(text):
    """Nettoie le texte (espaces, caractères spéciaux)"""
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
    """Corrige les sauts de lignes"""
    text = re.sub(r"(?<![\.\?\!\:])\n(?![\n])", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def fetch_rss():
    """Télécharge le flux RSS BBC Afrique de manière robuste"""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BBCScraper/1.0)"}
    try:
        response = requests.get(RSS_URL, headers=headers, timeout=15)
        response.raise_for_status()  # Lève une erreur si HTTP != 200
        return feedparser.parse(response.content)
    except http.client.IncompleteRead:
        print("⚠️ Flux RSS incomplet, nouvelle tentative...")
        response = requests.get(RSS_URL, headers=headers, timeout=15)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement du flux RSS : {e}")
        return None
    
# --- SCRAP ---
async def extract_clean_text(page):
    """Extrait le texte d’un article BBC avec le nouveau sélecteur CSS"""
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    article_div = soup.select_one("div.bbc-1cvxiy9")
    if not article_div:
        raise ValueError("Contenu introuvable dans la page")

    paragraphs = [p.get_text(strip=True) for p in article_div.select("p")]
    text = "\n".join(paragraphs)
    return clean_text(text)


async def process_article(entry, page, data):
    """Télécharge un article et l'ajoute au JSON"""
    await page.goto(entry.link, timeout=TIMEOUT_MS)
    await page.wait_for_timeout(2000)

    text_content = await extract_clean_text(page)
    title = clean_text(entry.title.strip())
    text_content = normalize_linebreaks(text_content)

    scraping_date = datetime.utcnow().isoformat()

    # --- Construction de la structure JSON ---
    article_data = {
        "scraping_status": "scraped",
        "link": entry.link,
        "provider": "BBC_Afrique",
        "titre": title,
        "date": getattr(entry, "published", "inconnue"),
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
    }

    data["articles"].append(article_data)
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"✅ Article ajouté au JSON : {entry.link}")


async def main():
    done_urls = read_done()
    already_downloaded_count = 0  

    # Charger ou init JSON
    if JSON_FILE.exists():
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"articles": []}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"\n📡 Lecture du flux RSS BBC Afrique : {RSS_URL}")
        
        feed = fetch_rss()
        if not feed:
            print("❌ Impossible de récupérer le flux RSS, arrêt du script.")
            return


        for entry in feed.entries:
            print(f"🔍 {entry.link}")

            if entry.link in done_urls:
                already_downloaded_count += 1
                print(f"⏩ Déjà téléchargé ({already_downloaded_count}/5)")
                if already_downloaded_count >= 5:
                    print("🛑 5 articles déjà téléchargés -> arrêt du script.")
                    break
                continue

            success = False
            for attempt in range(1, 4):  
                try:
                    await process_article(entry, page, data)
                    success = True
                    break
                except Exception as e:
                    print(f"⚠️ Erreur tentative {attempt} sur {entry.link} : {e}")
                    if attempt < 3:
                        await asyncio.sleep(3)

            if success:
                mark_done(entry.link)
                done_urls.add(entry.link)

            await asyncio.sleep(2)

        await browser.close()

    print(f"\n📁 Sauvegarde terminée dans : {JSON_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
