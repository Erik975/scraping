import json
import re
import html
import os
from datetime import datetime

INPUT_FILE = "../synthese/data.json"   # ⚠️ Fais une sauvegarde avant de lancer
OUTPUT_FILE = INPUT_FILE               # Écrase le même fichier

# ─────────────────────────────
# 🔵 1. Normalisation de la date
# ─────────────────────────────
def convert_date(date_str):
    """
    Convertit une date du format 'Fri, 01 Aug 2025 17:16:50 GMT' en '2025-08-01'.
    Si erreur, renvoie la date d'origine.
    """
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str

def normalize_dates(data):
    """Normalise les dates de tous les articles."""
    changes = 0
    for article in data.get("articles", []):
        date_orig = article.get("date")
        if date_orig:
            date_new = convert_date(date_orig)
            if date_new != date_orig:
                article["date"] = date_new
                changes += 1
    print(f"📅 {changes} dates normalisées.")
    return data

# ─────────────────────────────
# 🔵 2. Nettoyage du titre (décodage HTML uniquement)
# ─────────────────────────────
def clean_titles(data):
    """Décode les entités HTML dans le champ titre uniquement."""
    for i, article in enumerate(data.get("articles", []), start=1):
        if "titre" in article and article["titre"]:
            original_title = article["titre"]
            article["titre"] = html.unescape(original_title)
            if original_title != article["titre"]:
                print(f"   🏷️ Article {i} titre décodé : '{original_title}' → '{article['titre']}'")
    return data

# ─────────────────────────────
# 🔵 3. Détection des sous-titres
# ─────────────────────────────
def detect_subtitles(text):
    """
    Détecte des sous-titres (phrases courtes sans ponctuation forte)
    et les transforme en <h4>.
    """
    lines = text.split("\n")
    new_lines = []
    subtitle_count = 0

    for idx, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line:
            continue

        print(f"   🔍 Ligne {idx+1}: '{clean_line}'")

        # Critère : ligne courte (3-8 mots) sans ., ! ou ? à la fin
        if 3 <= len(clean_line.split()) <= 8 and not re.search(r"[.?!]$", clean_line):
            print(f"      ➡️ Sous-titre détecté ✅")
            new_lines.append(f"<h4>{clean_line}</h4>")
            subtitle_count += 1
        else:
            new_lines.append(clean_line)

    return "\n".join(new_lines)

# ─────────────────────────────
# 🔵 4. Mise en <h1> du titre dans le texte
# ─────────────────────────────
def highlight_title_in_text(text, title):
    """
    Cherche dans le texte la version encodée du titre (ex: &amp;)
    et remplace par le titre décodé entouré de <h1>.
    """
    title_encoded = html.escape(title)

    if title_encoded in text:
        text = text.replace(title_encoded, f"<h1>{title}</h1>", 1)
        print(f"   🏷️ Titre encodé mis en <h1> dans le texte.")
    elif title in text:
        text = text.replace(title, f"<h1>{title}</h1>", 1)
        print(f"   🏷️ Titre décodé mis en <h1> dans le texte.")
    else:
        print(f"   ⚠️ Titre non trouvé dans le texte.")
    return text

# ─────────────────────────────
# 🔵 5. Nettoyage global du texte
# ─────────────────────────────
def clean_text(text, article_index, title, date=None):
    """Nettoie et reformate le texte avec logs détaillés."""
    print(f"\n📝 Nettoyage du texte pour l'article #{article_index}")

    # 🔠 Décodage des entités HTML dans le texte
    text = html.unescape(text)
    print("   🔠 Entités HTML décodées")

    original_preview = text[:120].replace("\n", " ") + ("..." if len(text) > 120 else "")
    print(f"   🔹 Texte original (début) : {original_preview}")

    # 🏷️ Mise en <h1> du titre dans le texte
    text = highlight_title_in_text(text, title)

    # 📆 Ajout de la date juste après le <h1>
    if date:
        print(f"   📆 Ajout de la date formatée : {date}")
        text = re.sub(r"(</h1>)", r"\1\n<p class='date'>" + date + "</p>", text, count=1)

    # 🔧 Nettoyage des espaces et retours à la ligne
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"\s{2,}", " ", text)
    print(f"   🔧 Espaces et retours à la ligne normalisés.")

    # ✨ Détection des sous-titres et conversion en <h4>
    text = detect_subtitles(text)
    print(f"   ✨ Sous-titres détectés et convertis en <h4>.")

    cleaned_preview = text[:120].replace("\n", " ") + ("..." if len(text) > 120 else "")
    print(f"   ✅ Texte nettoyé (début) : {cleaned_preview}")

    return text.strip()

# ─────────────────────────────
# 🔵 6. Script principal
# ─────────────────────────────
print(f"📂 Chargement du fichier : {INPUT_FILE}")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"✅ Fichier chargé. Nombre d'articles : {len(data.get('articles', []))}")

# 1. Normaliser les dates
data = normalize_dates(data)

# 2. Nettoyer les titres (HTML entities)
data = clean_titles(data)

# 3. Appliquer les mises en forme au texte
for i, article in enumerate(data.get("articles", []), start=1):
    print(f"\n==============================")
    print(f"📄 Article {i}/{len(data['articles'])}")
    print(f"   🏷️ Titre : {article.get('titre', 'Sans titre')}")
    print(f"   🌐 Provider : {article.get('provider', 'Inconnu')}")

    if "text" in article and article["text"]:
        print("   ✍️ Traitement du contenu...")
        article["text"] = clean_text(article["text"], i, article.get("titre", ""), article.get("date"))
    else:
        print("   ⚠️ Aucun contenu trouvé pour cet article.")

# Sauvegarde finale
print(f"\n💾 Sauvegarde du fichier nettoyé dans : {OUTPUT_FILE}")
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("\n✅ Nettoyage terminé avec succès ! 🎉")
