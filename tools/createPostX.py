"""
Script : generate_tweet_narratives.py
But : Prendre une synthèse d'actualité en entrée et générer plusieurs narratifs
      (humour, sérieux, dénonciation, neutre, etc.) prêts à poster sur X (Twitter).
      ➕ Gère automatiquement plusieurs clés API et bascule si quota dépassé.

Auteur : PTH
Date : 2025-08-01
"""

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

# ======== 🔑 LISTE DES CLÉS API GEMINI ========
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
    """Configure Gemini avec la clé API active."""
    genai.configure(api_key=API_KEYS[current_key_index])

def switch_key():
    """Passe à la clé API suivante si possible."""
    global current_key_index
    if current_key_index + 1 < len(API_KEYS):
        current_key_index += 1
        configure_gemini()
        print(f"🔄 Basculement sur la clé API n°{current_key_index + 1}")
        return True
    else:
        print("❌ Plus aucune clé API disponible.")
        return False

# ⚙️ On configure la première clé au lancement
configure_gemini()
model = genai.GenerativeModel("gemini-1.5-flash")

# ====================== 🎭 PROMPTS TYPES ======================
NARRATIVE_STYLES = {
    "📰 Sérieux": "Rédige un tweet informatif, neutre et journalistique. Concentre-toi sur les faits.",
    "😂 Humour": "Fais un tweet drôle ou ironique sur ce sujet, sans tomber dans l’offensant.",
    "⚠️ Dénonciation": "Adopte un ton engagé et dénonciateur comme si tu alertais ton audience.",
    "🤔 Vulgarisation": "Explique ce sujet simplement, comme à un ado, avec des mots accessibles.",
    "🔥 Buzz / Punchline": "Propose un tweet percutant, court, qui pourrait devenir viral.",
}

# ====================== 🧠 FONCTION DE GÉNÉRATION ======================

def generate_narratives(synthesis: str, max_chars: int = 280, max_retries: int = 5) -> dict:
    """
    Prend une synthèse et génère plusieurs tweets selon des angles différents.
    🔄 Bascule sur une autre clé si quota dépassé.
    """
    global model
    tweets = {}

    for style, instruction in NARRATIVE_STYLES.items():
        prompt = f"""
        Contexte : {synthesis}

        🎯 Objectif : {instruction}
        ⚠️ Contraintes :
        - Maximum {max_chars} caractères (comme un tweet).
        - Pas de hashtags sauf si vraiment pertinents.
        - Pas de lien, juste le texte.
        - Style adapté à {style}.
        """

        for attempt in range(1, max_retries + 1):
            try:
                response = model.generate_content(prompt)
                tweet = response.text.strip()
                tweet = tweet.replace('"', '').replace("'", "")
                tweets[style] = tweet
                break  # ✅ on sort de la boucle si succès
            except ResourceExhausted:
                print(f"⚠️ Quota dépassé pour {style} (clé {current_key_index + 1}).")
                if switch_key():
                    model = genai.GenerativeModel("gemini-1.5-flash")
                else:
                    tweets[style] = "[Quota dépassé - Aucune clé disponible]"
                    break
            except Exception as e:
                print(f"⚠️ Erreur Gemini pour {style} (tentative {attempt}): {e}")
                if attempt == max_retries:
                    tweets[style] = f"[Erreur : {e}]"
    return tweets

# ====================== 🚀 SCRIPT PRINCIPAL ======================

if __name__ == "__main__":
    print("📥 Colle la synthèse ou un résumé d'article (finir avec ENTRÉE + CTRL+D) :\n")
    import sys
    synthesis_input = sys.stdin.read().strip()

    print("\n🎭 Génération des tweets en plusieurs angles...\n")
    results = generate_narratives(synthesis_input)

    for style, tweet in results.items():
        print(f"{style} :\n{tweet}\n{'-'*50}")
