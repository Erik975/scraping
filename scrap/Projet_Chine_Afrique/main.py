"""
Script : Projet_Chine_Afrique/main.py
But :
  - Parcourir les pages quotidiennes de projetafriquechine.com
  - Extraire les liens d’articles
  - Sauvegarder le contenu dans un fichier JSON
  - Éviter de retraiter les liens déjà visités

Auteur : PTH
Date : 2025-07-28 (modifié le 2025-08-02)
"""

from playwright.sync_api import sync_playwright
from datetime import date, timedelta, datetime
from pathlib import Path
import json
import re
import unicodedata
import time


JSON_FILE = Path("articles.json")


# ──────────────── JSON MANAGEMENT ────────────────
def load_json():
    """Charge le fichier JSON ou initialise une structure vide"""
    if JSON_FILE.exists():
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"collection_info": {}, "articles": []}


def save_json(data):
    """Sauvegarde le JSON complet"""
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ──────────────── SCRAPER ────────────────
def scrape_links_for_date(current_date, existing_links):
    """Récupère tous les liens d’articles pour une date donnée"""
    url = f"https://projetafriquechine.com/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}/"
    print(f"🔍 Traitement de la date : {current_date} ({url})")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, timeout=15000)
        except Exception as e:
            print(f"❌ Erreur lors du chargement de la page : {e}")
            browser.close()
            return [], False

        title_text = page.text_content("h1.page-title") or ""
        content = page.content()
        if "Oups" in title_text or "introuvable" in content:
            browser.close()
            return [], False

        links = []

        sticky_title = page.query_selector("h2.sticky__title")
        if sticky_title:
            sticky_a = sticky_title.query_selector("a")
            if sticky_a:
                href = sticky_a.get_attribute("href")
                if href and href not in links:
                    links.append(href)

        index = 0
        while True:
            selector = f"div.no-sticky--{index}"
            element = page.query_selector(selector)
            if not element:
                break
            no_sticky_title = element.query_selector("h2.no-sticky__title a")
            if no_sticky_title:
                href = no_sticky_title.get_attribute("href")
                if href and href not in links:
                    links.append(href)
            index += 1

        browser.close()
        new_links = [l for l in links if l not in existing_links]
        return new_links, True


def clean_text(text):
    """Nettoie le texte pour éviter les caractères spéciaux moches"""
    replacements = {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
        "\u2018": "'", "\u2019": "'", "\u02BC": "'",
        "\u201c": '"', "\u201d": '"', "\u00ab": '"', "\u00bb": '"',
        "\u2026": "...", "\u0152": "OE", "\u0153": "oe",
        "\ufb01": "fi", "\ufb02": "fl",
        "\u2122": "(TM)", "\u00ae": "(R)", "\u00a9": "(C)",
        '\u1d49': " ", "\u2039": "<", "\u203a": ">", "\u201a": ",", "\u201e": '"',
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


def scrape_article_content(link):
    """Scrape un article et retourne un dictionnaire prêt pour JSON"""
    for attempt in range(3):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                print(f"🔍 Téléchargement : {link}")
                page.goto(link, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_selector("h1.entry-title", timeout=15000)
                page.wait_for_selector("div.entry-content", timeout=15000)

                title_elem = page.query_selector("h1.entry-title")
                content_elem = page.query_selector("div.entry-content")

                if not title_elem or not content_elem:
                    print("❌ Contenu non trouvé.")
                    browser.close()
                    return None

                title = clean_text(title_elem.inner_text().strip())
                text = clean_text(content_elem.inner_text().strip())

                # Date scraping
                scraping_date = datetime.now().isoformat()

                article_data = {
                    "scraping_status": "scraped",
                    "link": link,
                    "provider": "Projet Afrique Chine",
                    "titre": title,
                    "date": scraping_date,  # ⚠️ Pas de date de publication sur le site → on met la date scraping
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
                }

                browser.close()
                return article_data

        except Exception as e:
            print(f"⚠️ Erreur tentative {attempt + 1}: {e}")
            time.sleep(5)

    print(f"❌ Échec après 3 tentatives : {link}")
    return None


# ──────────────── MAIN ────────────────
def main():
    end = date(2023, 1, 1)
    start_date = date.today()

    file_path = Path("done.txt")
    existing_links = set()
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            existing_links = set(line.strip() for line in f)

    # Charger JSON existant
    data = load_json()

    consecutive_no_new = 0
    current_date = start_date

    while current_date >= end:
        new_links, page_exists = scrape_links_for_date(current_date, existing_links)

        if new_links:
            with open(file_path, "a", encoding="utf-8") as f:
                for link in new_links:
                    print(f"✅ Nouveau lien : {link}")
                    f.write(link + "\n")
                    existing_links.add(link)

                    article_data = scrape_article_content(link)
                    if article_data:
                        data["articles"].append(article_data)
                        save_json(data)  # ✅ on sauvegarde après chaque article

            consecutive_no_new = 0
        else:
            if not page_exists:
                consecutive_no_new += 1
                print(f"⏩ Aucune page trouvée pour ce jour.")
            else:
                consecutive_no_new += 1
                print(f"⏩ Aucun nouveau lien pour ce jour.")

        if consecutive_no_new >= 5:
            break

        current_date -= timedelta(days=1)


if __name__ == "__main__":
    main()
