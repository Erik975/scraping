import json
import os

PATH_REEL= "Projet Afrique Chine"
NEW_PATH= "Projet_Chine_Afrique"

FILE_PATH = f"/home/user/Documents/scrap/{NEW_PATH}/articles.json"  # <-- adapte si ton fichier est ailleurs

def normalize_allafrica(file_path):
    if not os.path.exists(file_path):
        print(f"❌ Fichier introuvable : {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    changes = 0

    for article in articles:
        if article.get("provider") == PATH_REEL:
            article["provider"] = NEW_PATH
            changes += 1

    # ✅ Réécriture du fichier avec les providers corrigés
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"articles": articles}, f, ensure_ascii=False, indent=4)

    print(f"✅ Remplacement terminé : {changes} occurences modifiées.")

if __name__ == "__main__":
    normalize_allafrica(FILE_PATH)
