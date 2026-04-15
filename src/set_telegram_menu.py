"""
Définit le bouton Menu persistant du bot Telegram pour ouvrir la webapp.
Ce bouton reste visible même si le bot n'est pas en train de tourner.

Usage : python3 src/set_telegram_menu.py

API Telegram : setChatMenuButton (applique à tous les chats du bot par défaut).
Doc : https://core.telegram.org/bots/api#setchatmenubutton
"""
import os
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Charge le token depuis .env
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"')
                break

if not token:
    raise SystemExit("❌ TELEGRAM_BOT_TOKEN introuvable (ni env, ni .env)")

WEBAPP_URL = "https://bobkaneus-svg.github.io/chefs-picks/"
BUTTON_TEXT = "Ouvrir Only The Best"

# Set Menu Button (persistant, bas-gauche du chat)
r = requests.post(
    f"https://api.telegram.org/bot{token}/setChatMenuButton",
    json={
        "menu_button": {
            "type": "web_app",
            "text": BUTTON_TEXT,
            "web_app": {"url": WEBAPP_URL},
        }
    },
    timeout=10,
)
print("setChatMenuButton →", r.status_code, r.json())

# Met aussi à jour la description courte + l'about text du bot (optionnel, nice-to-have)
requests.post(
    f"https://api.telegram.org/bot{token}/setMyDescription",
    json={"description": "Les meilleurs restos triés sur le volet. Ouvre l'app pour les découvrir."},
    timeout=10,
)
requests.post(
    f"https://api.telegram.org/bot{token}/setMyShortDescription",
    json={"short_description": "Only The Best · les meilleurs restos, triés sur le volet."},
    timeout=10,
)

# Commandes raccourcis (tapées dans la barre de chat)
requests.post(
    f"https://api.telegram.org/bot{token}/setMyCommands",
    json={"commands": [
        {"command": "start", "description": "Ouvrir l'app"},
        {"command": "top", "description": "Top 10 pépites"},
        {"command": "random", "description": "Une pépite au hasard"},
        {"command": "ville", "description": "Restos par ville"},
    ]},
    timeout=10,
)

# Nom affiché du bot
requests.post(
    f"https://api.telegram.org/bot{token}/setMyName",
    json={"name": "Only The Best"},
    timeout=10,
)

print(f"\n✅ Menu button 'Ouvrir Only The Best' configuré sur le bot.")
print(f"   URL : {WEBAPP_URL}")
print(f"\n💡 Ouvre une conversation avec ton bot, tu devrais voir un bouton en bas-gauche.")
print(f"   Si tu le vois pas, quitte et ré-ouvre la conversation dans Telegram.")
