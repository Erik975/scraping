"""
Script : Sika/main_combined_json.py
But :
    - Scraper les liens d'articles depuis SikaFinance
    - Télécharger le contenu de chaque article
    - Stocker chaque article dans un fichier JSON unique

Auteur : PTH + ChatGPT
Date : 2025-08-02
"""

import unicodedata
import asyncio
import re
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
BASE_DIR = Path("/home/user/Documents/scrap/SIKA_Finance")
JSON_FILE = BASE_DIR / "articles.json"
BASE_DIR.mkdir(parents=True, exist_ok=True)

DONE_FILE = BASE_DIR / "done.txt"
URL = "https://www.sikafinance.com/marches/actualites_bourse_brvm"

TIMEOUT_MS = 15000
MAX_RETRIES = 3        # 3 tentatives par article

# --- UTILS ---
def read_done():
    """Lit les URL déjà traitées"""
    if DONE_FILE.exists():
        return set(line.strip() for line in DONE_FILE.read_text(encoding="utf-8").splitlines())
    return set()

def mark_done(url):
    """Marque une URL comme traitée"""
    with DONE_FILE.open("a", encoding="utf-8") as f:
        f.write(url.strip() + "\n")

def clean_text(text):
    """Nettoie le texte des caractères spéciaux"""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("latin-1", "ignore").decode("latin-1")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def scrape_links():
    """Scrape les liens des articles depuis SikaFinance"""
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tbody = soup.find("tbody")
    if not tbody:
        print("❌ Aucun <tbody> trouvé.")
        return []

    links = []
    for a in tbody.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            href = "https://www.sikafinance.com" + href
        links.append(href)

    print(f"✅ {len(links)} liens récupérés depuis SikaFinance")
    return links

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

async def extract_content(page):
    """
    Récupère et nettoie :
        - le titre
        - le texte de l'article
    """
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    # --- Titre ---
    title_div = soup.select_one("div.innerUp > h1")
    if not title_div:
        raise ValueError("❌ Titre introuvable (div.innerUp > h1 manquant)")
    title = clean_text(title_div.get_text(strip=True))

    # --- Texte ---
    article_div = soup.select_one("div.inarticle.txtbig")
    if not article_div:
        raise ValueError("❌ Contenu introuvable (div.inarticle.txtbig manquant)")
    body = clean_text(article_div.get_text(separator="\n", strip=True))

    return title, body


async def process_article(url, page, data):
    """Scrape un article et l’ajoute au JSON"""
    try:
        await page.goto(url, timeout=TIMEOUT_MS)
        await page.wait_for_timeout(3000)

        title, body = await extract_content(page)
        scraping_date = datetime.now().isoformat()

        data["articles"].append({
            "scraping_status": "scraped",
            "link": url,
            "provider": "SIKA_Finance",
            "titre": title if title else "Titre inconnu",
            "date": scraping_date,
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
        
        print(f"✅ Article ajouté au JSON : {title}")
        return True

    except Exception as e:
        print(f"⚠️ Erreur sur {url} : {e}")
        return False

async def main():
    links = scrape_links()
    if not links:
        print("❌ Aucun lien trouvé.")
        return

    done_urls = read_done()
    data = load_json()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for url in links:
            if url in done_urls:
                print(f"⏩ Déjà téléchargé, on passe : {url}")
                continue

            print(f"🔍 {url}")
            success = False

            for attempt in range(1, MAX_RETRIES + 1):
                print(f"   ➡️ Tentative {attempt}/{MAX_RETRIES} pour {url}")
                success = await process_article(url, page, data)
                if success:
                    break
                await asyncio.sleep(2)

            if success:
                mark_done(url)
                done_urls.add(url)
                save_json(data)  # 💾 sauvegarde après chaque article
            else:
                print(f"❌ Échec du scraping après {MAX_RETRIES} tentatives : {url}")

            await asyncio.sleep(2)

        await browser.close()

    print(f"🎉 Scraping terminé. {len(data['articles'])} articles enregistrés dans {JSON_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
