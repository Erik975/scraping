import json
from pathlib import Path

# 📂 Chemin vers ton fichier JSON original
INPUT_FILE = Path("/home/user/Documents/synthese/data.json")
OUTPUT_FILE = INPUT_FILE

# 🏷️ Critère pour identifier les doublons : "titre" ou "link"
KEY = "titre"

def remove_duplicates():
    # 1️⃣ Charger le JSON existant
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    print(f"📥 {len(articles)} articles trouvés dans le fichier.")

    # 2️⃣ Détection des doublons
    seen = set()
    unique_articles = []
    duplicates_count = 0

    for article in articles:
        key_value = article.get(KEY, "").strip()
        if key_value not in seen:
            seen.add(key_value)
            unique_articles.append(article)
        else:
            duplicates_count += 1

    # 3️⃣ Réécrire le JSON propre
    cleaned_data = {"articles": unique_articles}
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

    print(f"✅ Nettoyage terminé.")
    print(f"   ➡️ Articles avant : {len(articles)}")
    print(f"   ➡️ Articles après : {len(unique_articles)}")
    print(f"   ➡️ Doublons supprimés : {duplicates_count}")

if __name__ == "__main__":
    remove_duplicates()
