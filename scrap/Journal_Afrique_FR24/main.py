"""
Script : Journal_Afrique_FR24/main.py
But : 
  - Parcourir une playlist YouTube
  - Télécharger la transcription (si dispo)
  - Enregistrer les transcriptions dans un fichier JSON
  - Éviter de retraiter les vidéos déjà traitées

Date : 2025-07-28
"""

import os
import time
import json
from datetime import datetime
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

# ====================== 🔧 CONFIGURATION ======================

BASE_DIR = Path(".")
JSON_FILE = BASE_DIR / "articles.json"   # Fichier JSON pour stocker les transcriptions
DONE_FILE = Path("done.txt")             # Fichier pour stocker les IDs déjà traités
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLCnUnV3yCIYtAvfS-LPlFoC2IiPOb13uQ"

MAX_ALREADY_DONE = 5  # Stoppe le script si 5 vidéos consécutives sont déjà traitées

# ====================== ⚙️ UTILITAIRES ======================

def load_done_ids():
    """Charge les IDs déjà traités depuis done.txt"""
    if DONE_FILE.exists():
        return set(DONE_FILE.read_text().splitlines())
    return set()

def save_done_id(video_id):
    """Ajoute un ID vidéo dans done.txt"""
    with open(DONE_FILE, "a") as f:
        f.write(video_id + "\n")

def clean_text(text):
    """Nettoie le texte pour éviter les caractères spéciaux problématiques"""
    replacements = {
        '•': '-', '“': '"', '”': '"', '’': "'", 
        '–': '-', '—': '-', '«': '"', '»': '"'
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text

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

def transcript_to_text(transcript):
    """Convertit la liste de segments en texte brut"""
    return " ".join(clean_text(entry['text']) for entry in transcript)

# ====================== 🚀 SCRIPT PRINCIPAL ======================

def main():
    done_ids = load_done_ids()
    data = load_json_data()
    consecutive_already_done = 0

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': True,
        'ignoreerrors': True
    }

    with YoutubeDL(ydl_opts) as ydl:
        playlist_dict = ydl.extract_info(PLAYLIST_URL, download=False)
        videos = playlist_dict.get('entries', [])
        time.sleep(2)

        for video in videos:
            time.sleep(1)
            video_id = video.get('id')
            title = video.get('title', f"Video {video_id}")

            if not video_id:
                continue

            print(f"🔍 {title}")

            # Vérifie si déjà traité
            if video_id in done_ids:
                consecutive_already_done += 1
                print(f"⏩ Déjà traité, on passe.")
                if consecutive_already_done >= MAX_ALREADY_DONE:
                    break
                continue
            else:
                consecutive_already_done = 0  # reset

            # Récupère titre complet
            try:
                with YoutubeDL({'quiet': True, 'skip_download': True}) as ydl_info:
                    info = ydl_info.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                    video_title = info.get('title', title)
            except Exception as e:
                print(f"❌ Erreur récupération titre : {e}")
                continue

            # Récupère transcription
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['fr'])
            except Exception as e:
                print(f"⚠️ Transcript indisponible pour {video_id} : {e}")
                transcript = []

            if transcript:
                try:
                    text = transcript_to_text(transcript)
                    scraping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 🔽 Ajout au JSON avec la structure demandée
                    data["articles"].append({
                        "scraping_status": "scraped",
                        "link": f"https://www.youtube.com/watch?v={video_id}",
                        "provider": "Journal_Afrique_FR24",
                        "titre": video_title if video_title else "Titre inconnu",
                        "date": scraping_date,
                        "scraping_date": scraping_date,
                        "language": "fr",
                        "text": f"{video_title}\n\n{text}" if video_title else text,
                        "extraction_method": "YouTubeTranscriptApi",
                        "html_metadata": {},
                        "statistics": {
                            "chars": len(text),
                            "words": len(text.split()),
                            "lines": len(text.split("\n"))
                        }
                    })

                    save_json_data(data)  # sauvegarde après chaque ajout
                    save_done_id(video_id)
                    done_ids.add(video_id)

                    print(f"✅ Transcription ajoutée : {video_title}")

                except Exception as e:
                    print(f"❌ Erreur enregistrement JSON pour {video_id} : {e}")
            else:
                print(f"⚠️ Pas de transcript pour {video_id}")

# ====================== ▶️ LANCEMENT ======================

if __name__ == "__main__":
    main()
