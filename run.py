import subprocess
import os
import sys
import json
import time

PROGRESS_FILE = "progress.json"

def run_script(script_name, path):
    """Lance un script Python et gère les erreurs."""
    command = ["python3", script_name]
    print(f"\n🚀 Lancement de {script_name} dans {path}...")
    result = subprocess.run(command, cwd=path, text=True)

    if result.returncode == 0:
        print(f"✅ {script_name} terminé avec succès.")
        return True
    else:
        print(f"❌ Erreur lors de l'exécution de {script_name}")
        print("---- STDOUT ----")
        print(result.stdout)
        print("---- STDERR ----")
        print(result.stderr)
        return False

def merge_all_json(base_path, subdirs, output_file):
    """Fusionne tous les fichiers articles.json en un seul JSON."""
    print("\n🔄 Fusion de tous les fichiers articles.json ...")
    merged_articles = []
    for subdir in subdirs:
        json_path = os.path.join(base_path, subdir, "articles.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                    articles = data.get("articles", [])
                    merged_articles.extend(articles)
                print(f"✔️ {len(articles)} articles ajoutés depuis {subdir}")
            except Exception as e:
                print(f"⚠️ Impossible de lire {json_path} : {e}")
        else:
            print(f"⚠️ Aucun fichier {json_path} trouvé")

    # Sauvegarde
    merged_path = os.path.join(base_path, output_file)
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump({"articles": merged_articles}, f, ensure_ascii=False, indent=4)

    print(f"\n✅ Fusion terminée, total articles : {len(merged_articles)}")
    print(f"📁 Fichier sauvegardé : {merged_path}")

def save_progress(index):
    """Sauvegarde la progression dans un fichier JSON."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"last_index": index}, f)

def load_progress():
    """Charge la progression si elle existe."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_index", 0)
    return 0

if __name__ == "__main__":
    base_dir = "/home/user/Documents/scrap/"
    scrap_dirs = [
        "Journal_Afrique_FR24",
        "RFI",
        "Projet_Chine_Afrique",
        "Afrik",
        "AfriqueXXI",
        "Agence_Ecofin",
        "allAfrica",
        "BBC_Afrique",
        "SIKA_Finance",
        "Africa_News",
        "Mondafrique",
    ]

    start_index = load_progress()
    print(f"▶️ Reprise à l'index {start_index} ({scrap_dirs[start_index] if start_index < len(scrap_dirs) else 'fin'})")

    '''for i in range(start_index, len(scrap_dirs)):
        directory = scrap_dirs[i]
        script_path = os.path.join(base_dir, directory)

        success = run_script("main.py", script_path)
        if not success:
            print(f"⏸️ Arrêt du processus. Reprendra sur '{directory}' au prochain lancement.")
            save_progress(i)  # Sauvegarde où on s'est arrêté
            sys.exit(1)
        else:
            save_progress(i + 1)'''

    # Fusion des JSON à la fin
    merge_all_json(base_dir, scrap_dirs, "/home/user/Documents/synthese/data.json")

    # Suppression du fichier de progression
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("\n🧹 Progression réinitialisée.")

