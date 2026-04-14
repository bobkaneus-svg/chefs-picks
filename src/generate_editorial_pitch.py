"""
Génère pour chaque resto/hôtel un `editorial_pitch` de 30-40 mots
en voix humaine, à partir de :
- signature_phrase (si dispo) → ancre principale
- signature_dishes (si dispo) → pivot gustatif
- occasion_tags (si dispo) → contexte d'usage
- google_rating + reviews_count_google → preuve sociale discrète

Templates plutôt que LLM : ton uniforme, zéro coût, facile à corriger.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]


# ─────────────────────────────────────────
# Templates par nature de signal
# ─────────────────────────────────────────

OPENERS = {
    # Pour les restos
    "restaurant": [
        "Notre coup de cœur dans {city}.",
        "On adore cet endroit.",
        "Une pépite comme on les aime.",
        "Un incontournable local.",
        "L'adresse qu'on garde pour soi.",
    ],
    # Pour les hôtels
    "hotel": [
        "Un hôtel qu'on recommande les yeux fermés.",
        "Une adresse à retenir.",
        "Notre pick hébergement pour {city}.",
        "On y va comme chez soi.",
        "Une valeur sûre à {city}.",
    ],
}

DISH_HOOKS = [
    "À commander sans hésiter : {dish}.",
    "On ne repart pas sans {dish}.",
    "Ne ratez pas {dish}.",
    "Notre conseil : {dish}.",
    "Le plat signature : {dish}.",
]

OCCASION_HOOKS = {
    "date": "Parfait pour un dîner romantique.",
    "tete_a_tete": "Idéal pour un tête-à-tête.",
    "business": "Bonne adresse pour un déjeuner d'affaires.",
    "family": "Très bien en famille.",
    "sunday_lunch": "À tester un dimanche midi.",
    "group": "Parfait entre amis.",
    "solo": "On y va même seul·e.",
    "view": "Pour profiter de la vue.",
    "quick_bite": "Idéal pour un repas rapide.",
    "celebration": "Top pour célébrer.",
}

SOCIAL_PROOF_HOOKS = [
    "Très forte notoriété locale ({rating}★, {reviews} avis).",
    "Une adresse consensuelle ({rating}★).",
    "Régulièrement plein ({reviews} avis enthousiastes).",
    "Les avis récents sont unanimes.",
    "Un des mieux notés de la ville.",
]


def _rotating(seeds: list, salt: str) -> str:
    """Pick déterministe basé sur un hash (l'ID du resto par ex)."""
    idx = sum(ord(c) for c in (salt or "x")) % len(seeds)
    return seeds[idx]


def _clean_dish(phrase: str) -> str:
    """Nettoie un signature_dish pour l'insérer dans une phrase."""
    if not phrase:
        return ""
    p = phrase.strip().rstrip(".,;:")
    # Minusculise la première lettre (sauf si suivi de tout en majuscules)
    if len(p) > 1 and p[0].isupper() and not p[:3].isupper():
        p = p[0].lower() + p[1:]
    # Limite 70 chars
    if len(p) > 70:
        cut = p.rfind(" ", 0, 67)
        p = p[:cut] + "…" if cut > 20 else p[:67] + "…"
    return p


def generate(r: dict) -> str:
    """Compose le pitch éditorial pour un resto/hôtel."""
    is_hotel = r.get("entity_type") == "hotel"
    kind = "hotel" if is_hotel else "restaurant"
    city = r.get("city", "")
    rid = r.get("id", "")

    parts = []

    # 1) Opener
    opener = _rotating(OPENERS[kind], rid)
    opener = opener.format(city=city) if "{city}" in opener else opener
    parts.append(opener)

    # 2) Signature phrase (si dispo, c'est le core du pitch)
    sp = (r.get("signature_phrase") or "").strip()
    if sp:
        # Nettoie et tronque si besoin
        sp_clean = sp.rstrip(".!?").strip('"').strip()
        if len(sp_clean) > 120:
            cut = sp_clean.rfind(",", 60, 110)
            sp_clean = sp_clean[:cut] if cut > 30 else sp_clean[:107] + "…"
        parts.append(sp_clean + ".")

    # 3) Dish hook (si signature_dishes dispo)
    dishes = r.get("signature_dishes") or []
    if dishes:
        top_dish = _clean_dish(dishes[0].get("phrase", ""))
        if top_dish and len(top_dish) > 5:
            hook = _rotating(DISH_HOOKS, rid + "_d")
            parts.append(hook.format(dish=top_dish))

    # 4) Occasion hook (si occasion_tags dispo)
    occasions = r.get("occasion_tags") or []
    if occasions:
        primary_occasion = occasions[0]
        hook = OCCASION_HOOKS.get(primary_occasion)
        if hook and len(" ".join(parts)) < 180:  # évite pitch trop long
            parts.append(hook)

    # 5) Social proof (fallback si pas de signature_phrase ET pas de dish)
    if not sp and not dishes:
        rating = r.get("google_rating")
        reviews = r.get("reviews_count_google") or r.get("reviews_count") or 0
        if rating:
            hook = _rotating(SOCIAL_PROOF_HOOKS, rid + "_s")
            parts.append(hook.format(rating=rating, reviews=reviews))

    pitch = " ".join(parts).strip()

    # Nettoyage final
    pitch = re.sub(r"\s+", " ", pitch)
    pitch = re.sub(r"\.+", ".", pitch)
    pitch = re.sub(r"\s+\.", ".", pitch)
    # S'assure que ça finit par un point
    if pitch and not pitch.endswith((".", "!", "?")):
        pitch += "."

    return pitch


def process(path: Path) -> int:
    with open(path) as f:
        data = json.load(f)
    updated = 0
    for r in data:
        if r.get("source_type") not in ("trending", "both") and r.get("entity_type") != "hotel":
            continue
        pitch = generate(r)
        if pitch:
            r["editorial_pitch"] = pitch
            updated += 1
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return updated


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            n = process(p)
            print(f"{p.name}: {n} fiches enrichies avec editorial_pitch")
