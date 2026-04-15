"""
Bot Telegram pour Only The Best.
Lance avec: python3 src/telegram_bot.py

Le bouton Menu persistant (bas-gauche du chat) est configuré séparément
via src/set_telegram_menu.py. Ce bot gère les commandes interactives.
"""
import json
import os
import random
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
APP_URL = "https://bobkaneus-svg.github.io/chefs-picks/"

# Charge les restos de la sélection (in_selection = true)
DATA_FILE = Path(__file__).parent.parent / "dashboard" / "data.json"
_all = json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else []
restaurants = [r for r in _all if r.get("in_selection") is True and r.get("entity_type") != "hotel"]


def _cta(label: str = "Ouvrir l'app"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, web_app=WebAppInfo(url=APP_URL))]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cities = sorted({r.get("city", "") for r in restaurants if r.get("city")})
    await update.message.reply_text(
        f"*Only The Best*\n"
        f"Les meilleurs restos, triés sur le volet.\n\n"
        f"*{len(restaurants)}* pépites\n"
        f"*{len(cities)}* villes · {', '.join(cities[:5])}{' +…' if len(cities)>5 else ''}\n\n"
        f"Ouvre l'app pour les découvrir sur la carte.",
        parse_mode="Markdown",
        reply_markup=_cta("✨ Découvrir les pépites"),
    )


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorted_r = sorted(restaurants, key=lambda r: r.get("editorial_score", 0) or r.get("google_rating", 0), reverse=True)[:10]
    lines = []
    for i, r in enumerate(sorted_r, 1):
        rating = r.get("google_rating", "")
        lines.append(
            f"*{i}.* {r['name']} — _{r.get('city', '')}_\n"
            f"    {r.get('cuisine_type', 'Restaurant')} · {r.get('price_range', '€€')} · 🔥 {rating}★"
        )
    await update.message.reply_text(
        "*Top 10 des pépites*\n\n" + "\n\n".join(lines),
        parse_mode="Markdown",
        reply_markup=_cta("Voir sur la carte"),
    )


async def random_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not restaurants:
        await update.message.reply_text("Aucune pépite pour l'instant.")
        return
    r = random.choice(restaurants)

    # Construit un extrait éditorial
    dishes = r.get("signature_dishes") or []
    dish_line = ""
    if dishes:
        d = dishes[0]
        dish_line = f"\n\n🍽️ _{d.get('phrase_fr') or d.get('phrase', '')}_"

    text = (
        f"*{r['name']}*\n"
        f"{r.get('city', '')} · {r.get('cuisine_type', 'Restaurant')} · {r.get('price_range', '€€')}\n"
        f"🔥 {r.get('google_rating', '')}★ ({r.get('reviews_count_google', 0)} avis)"
        f"{dish_line}"
    )

    # Deep link direct vers la fiche
    deep_link = APP_URL + "#r=" + r["id"]
    kb = [[InlineKeyboardButton("Ouvrir la fiche", web_app=WebAppInfo(url=deep_link))]]
    if r.get("google_maps_url"):
        kb.append([InlineKeyboardButton("Y aller (Google Maps)", url=r["google_maps_url"])])

    if r.get("photo_url"):
        await update.message.reply_photo(photo=r["photo_url"], caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def ville(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        cities = {}
        for r in restaurants:
            cities[r.get("city", "?")] = cities.get(r.get("city", "?"), 0) + 1
        top_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:15]
        lines = [f"*{c}* — {n} pépites" for c, n in top_cities]
        await update.message.reply_text(
            "*Villes couvertes*\n\n" + "\n".join(lines) + "\n\nUtilise `/ville Marseille` pour filtrer.",
            parse_mode="Markdown",
        )
        return

    query = " ".join(context.args).lower()
    matches = [r for r in restaurants if query in r.get("city", "").lower()]
    if not matches:
        await update.message.reply_text(f"Aucune pépite pour \"{query}\". Essaie `/ville` pour voir la liste.")
        return

    matches.sort(key=lambda r: r.get("editorial_score", 0), reverse=True)
    lines = []
    for r in matches[:10]:
        lines.append(f"*{r['name']}* · {r.get('cuisine_type', 'Restaurant')} · {r.get('price_range', '€€')}")
    await update.message.reply_text(
        f"*{len(matches)} pépites à {matches[0].get('city', '')}*\n\n" + "\n\n".join(lines),
        parse_mode="Markdown",
        reply_markup=_cta("Voir sur la carte"),
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("random", random_pick))
    app.add_handler(CommandHandler("ville", ville))
    print(f"Bot Only The Best démarré ({len(restaurants)} pépites)")
    app.run_polling()


if __name__ == "__main__":
    main()
