"""
Script : resume_by_gemini.py
But : Parcourir le dossier PDF, ne traiter QUE les PDF modifiés aujourd’hui,
      générer un résumé de chaque article avec l’API Gemini,
      puis créer un fichier HTML par article (au lieu d’un seul global).

Auteur : PTH
Date : 2025-08-01
"""

import markdown
import os
import re
import datetime
import shutil
import time
from urllib.parse import quote
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import subprocess

API_KEYS = [
    "AIzaSyB-ZFSra3QAwh1YO0wtsuj6Xx-I99LlrV4",
    "AIzaSyB9qetZJ90xA9bJV-zW3NIE8kG8om2g7hI",
    "AIzaSyDjivt4xeVRSvZfT5YoUoD1k5CyuD8gquA",
    "AIzaSyA7ePuU7yv-s2uZyRzpZibiTAzsMSbXo4U",
    "AIzaSyAe0QdwGUZ4aODx_kRob9ixYzc2MM6sMc4",
    "AIzaSyBy3zDzNnnV5h2AWPnCHvb8jmzs4JM9QM0",
    "AIzaSyB0xokwOS_Buk2ExKeZVJ93H7o0PyU-n3k"
]

current_key_index = 0

def configure_gemini():
    global current_key_index
    genai.configure(api_key=API_KEYS[current_key_index])

def switch_key():
    global current_key_index
    if current_key_index + 1 < len(API_KEYS):
        current_key_index += 1
        configure_gemini()
        print(f"🔄 Basculement sur la clé API n°{current_key_index + 1}")
        return True
    else:
        print("❌ Plus aucune clé API disponible.")
        return False

configure_gemini()
model = genai.GenerativeModel("gemini-1.5-flash")

def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        with open(pdf_path, "rb") as file:
            reader = PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de {pdf_path}: {e}")
    return text.strip()

def clean_text(summary: str) -> str:
    summary = re.sub(r"\*\*(.*?)\*\*", r"\1", summary)
    summary = re.sub(r"\*", "", summary)
    summary = re.sub(r"^\d+\.\s*", "- ", summary, flags=re.MULTILINE)
    summary = re.sub(r"\n{2,}", "\n", summary)
    return summary.strip()

def summarize_with_gemini(text: str, title: str, max_retries: int = 7, wait_time: int = 5) -> str:
    global model
    prompt = f"""
    Tu es journaliste spécialisé dans la veille stratégique. Voici tes consignes :
    🎯 Objectif : fournir une **veille structurée**, lisible et exploitable rapidement à partir de l'article donné en fin de prompt.

    1️⃣ **Commence par une section "###🔍 En un coup d'œil"**
    - Fournis 3 à 5 bullet points résumant l'essentiel.

    2️⃣ **Puis rédige une synthèse complète**, en suivant ce format clair :
    ### [Nom de la catégorie] 
    Synthèse complète et concise n'omettant aucun élément important.

    3️⃣ Utilise des sous-titres Markdown (###) pour chaque catégorie pertinente.

    📄 **Titre :** {title}
    Texte :
    {text}
    """

    for attempt in range(1, max_retries + 1):
        try:
            print(f"⏳ Tentative {attempt}/{max_retries} pour : {title}")
            response = model.generate_content(prompt)
            return clean_text(response.text.strip())
        except ResourceExhausted:
            print(f"⚠️ Quota dépassé pour {title} avec la clé actuelle.")
            if switch_key():
                model = genai.GenerativeModel("gemini-1.5-flash")
            else:
                return "[Quota dépassé - Aucune clé disponible]"
        except Exception as e:
            print(f"⚠️ Erreur Gemini pour {title} (tentative {attempt}): {e}")
            if attempt < max_retries:
                print(f"🔁 Nouvelle tentative dans {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"❌ Abandon après {max_retries} tentatives pour {title}")
                return "[Erreur de résumé]"

def clean_filename(name):
    name = name.strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name

def generate_html_single_article(title: str, summary: str, output_path: str, PRESSE_PROVIDER: str):
    today = datetime.date.today().strftime("%Y-%m-%d")
    soup = BeautifulSoup("<html><head><meta charset='utf-8'></head><body></body></html>", "html.parser")

    style = soup.new_tag("style")
    style.string = """
    body { font-family: Arial, sans-serif; margin: 40px; background-color: #f9f9f9; color: #333; }
    h1 { color: #2a5d9f; }
    a { color: #1794ad; text-decoration: none; transition: text-decoration 0.3s ease; }
    a:hover { text-decoration: underline; }
    """
    soup.head.append(style)

    body = soup.body
    h1 = soup.new_tag("h1")
    h1.string = f"Synthèse de l’article « {title} » – {PRESSE_PROVIDER} ({today})"
    body.append(h1)

    encoded_title = quote(title)
    p_link = soup.new_tag("p")
    a_pdf = soup.new_tag("a", href=f"pdfs/{encoded_title}.pdf")
    a_pdf.string = f"📄 Voir l’article original : {title}"
    p_link.append(a_pdf)
    body.append(p_link)

    html_summary = markdown.markdown(summary)
    summary_block = BeautifulSoup(html_summary, "html.parser")
    body.append(summary_block)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(soup.prettify())
    print(f"✅ Fichier créé : {output_path}")

def main(PRESSE_PROVIDER):
    today_str_folder = datetime.date.today().strftime("%Y%m%d")  # pour dossier
    today_str_file = datetime.date.today().strftime("%Y-%m-%d") # pour fichiers

    base_path = f"/home/user/Documents/synthese/{PRESSE_PROVIDER}/{today_str_folder}"
    pdf_dest_path = os.path.join(base_path, "pdfs")
    PDF_DIR = f"/home/user/Documents/scrap/{PRESSE_PROVIDER}/pdfs"

    today = datetime.date.today()
    os.makedirs(pdf_dest_path, exist_ok=True)

    articles_found = False

    for file in os.listdir(PDF_DIR):
        if file.endswith(".pdf"):
            pdf_path = os.path.join(PDF_DIR, file)
            mod_date = datetime.date.fromtimestamp(os.path.getmtime(pdf_path))
            if mod_date != today:
                continue

            articles_found = True
            dest_pdf_path = os.path.join(pdf_dest_path, file)
            try:
                shutil.copy2(pdf_path, dest_pdf_path)
                print(f"📂 Copie de {file} vers {dest_pdf_path}")
            except Exception as e:
                print(f"❌ Erreur lors de la copie de {file} : {e}")

            print(f"📄 Lecture du fichier : {file}")
            text = extract_text_from_pdf(pdf_path)
            if not text:
                print(f"⚠️ Aucun texte trouvé dans {file}")
                continue

            title = file.replace(".pdf", "")
            print(f"📝 Résumé de : {title}")
            summary = summarize_with_gemini(text, title)

            safe_title = clean_filename(title)
            output_html = os.path.join(base_path, f"{today_str_file}_{safe_title}.html")
            generate_html_single_article(title, summary, output_html, PRESSE_PROVIDER)

    if not articles_found:
        print("⚠️ Aucun PDF trouvé aujourd’hui. Suppression du répertoire...")
        shutil.rmtree(base_path, ignore_errors=True)
        return

    try:
        print("\n🚀 Lancement de generate_data_js.py...")
        subprocess.run(
            ["python3", f"/home/user/Documents/synthese/generate_data_js.py"], 
            check=True
        )
        print("✅ Script generate_data_js.py exécuté avec succès.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'exécution de generate_data_js.py : {e}")

