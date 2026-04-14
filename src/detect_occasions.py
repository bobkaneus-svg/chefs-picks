"""
Détecte les occasions/contextes d'usage de chaque resto/hôtel depuis les avis Google.
Produit le champ `occasion_tags` : ['date', 'business', 'sunday_lunch', 'family',
'tete_a_tete', 'spot_nature', 'group', 'solo'].
"""
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]

OCCASIONS = {
    "date": [
        r"en\s+amoureux", r"rendez[- ]?vous", r"soir\s+rom",
        r"romantique", r"d[îi]ner\s+(?:aux?\s+chandelles?|[àa]\s+deux|romantique)",
        r"(?:pour\s+)?une\s+premi[èe]re", r"saint[- ]?valentin",
        r"romantic", r"date\s+night", r"candle[- ]?lit", r"anniversary",
        r"rom[aá]ntic", r"aniversario",
    ],
    "tete_a_tete": [
        r"t[êe]te[- ]?[àa][- ]?t[êe]te", r"en\s+(?:duo|bin[ôo]me)",
        r"(?:pour\s+)?deux", r"cosy", r"cozy", r"intime", r"intimate",
        r"petit(?:e)?\s+(?:salle|endroit|lieu)",
    ],
    "business": [
        r"d[ée]jeuner\s+(?:pro|d['’]?affaires|business)", r"midi\s+pro",
        r"r[ée]union", r"meeting", r"client", r"entre\s+coll[èe]gues",
        r"business\s+lunch", r"working\s+lunch", r"professional",
    ],
    "family": [
        r"en\s+famille", r"avec\s+les\s+enfants?", r"family[- ]?friendly",
        r"with\s+kids", r"with\s+children", r"en\s+famille",
        r"familial", r"familiar", r"convivial",
        r"anniv(?:ersaire)?\s+(?:de\s+)?(?:mon|ma|notre|son)",
    ],
    "sunday_lunch": [
        r"dimanche\s+midi", r"d[ée]jeuner\s+dominical", r"brunch\s+dimanche",
        r"sunday\s+lunch", r"sunday\s+brunch",
        r"brunch\b",
    ],
    "group": [
        r"entre\s+amis", r"groupe", r"tabl[ée]e", r"bande\s+de\s+potes?",
        r"grand(?:e)?\s+tabl(?:e|ée)",
        r"with\s+friends", r"group\s+of", r"large\s+party",
        r"en\s+famille\s+ou\s+entre\s+amis", r"birthday",
    ],
    "solo": [
        r"seul(?:e)?", r"en\s+solo", r"manger\s+seul",
        r"solo\s+diner", r"alone",
        r"au\s+comptoir", r"at\s+the\s+bar",
    ],
    "view": [
        r"vue\s+(?:imprenable|sublime|magnifique|exceptionnelle|incroyable|[àa]\s+couper)",
        r"vue\s+sur\s+(?:la\s+mer|le\s+port|les\s+montagnes|la\s+ville)",
        r"sea\s+view", r"stunning\s+view", r"breathtaking",
        r"terrasse\s+(?:sur\s+la\s+mer|vue\s+mer)",
        r"rooftop",
    ],
    "quick_bite": [
        r"sur\s+le\s+pouce", r"rapide", r"en\s+coup\s+de\s+vent",
        r"quick\s+bite", r"lunch\s+on\s+the\s+go",
        r"snack",
    ],
    "celebration": [
        r"(?:pour\s+)?f[êe]ter", r"c[ée]l[ée]brer", r"anniversaire",
        r"birthday", r"celebration", r"special\s+occasion",
        r"occasion\s+sp[ée]ciale",
    ],
}

# Labels affichables pour chaque occasion (pour UI)
OCCASION_LABELS = {
    "date": {"label": "En amoureux", "icon": "❤️"},
    "tete_a_tete": {"label": "Tête-à-tête", "icon": "👫"},
    "business": {"label": "Dîner business", "icon": "💼"},
    "family": {"label": "En famille", "icon": "👨‍👩‍👧"},
    "sunday_lunch": {"label": "Dimanche midi", "icon": "🥐"},
    "group": {"label": "Entre amis", "icon": "🎉"},
    "solo": {"label": "En solo", "icon": "🪑"},
    "view": {"label": "Avec la vue", "icon": "🌊"},
    "quick_bite": {"label": "Sur le pouce", "icon": "⚡"},
    "celebration": {"label": "Pour célébrer", "icon": "🥂"},
}


def detect(reviews: list, min_mentions: int = 1) -> list:
    """Détecte les occasions dans une liste de textes d'avis."""
    if not reviews:
        return []
    corpus = " ".join(r or "" for r in reviews).lower()
    scores = Counter()
    for tag, patterns in OCCASIONS.items():
        n = 0
        for p in patterns:
            n += len(re.findall(p, corpus, re.IGNORECASE))
        if n >= min_mentions:
            scores[tag] = n
    # Retourne top 3 occasions
    return [tag for tag, _ in scores.most_common(3)]


def process(path: Path) -> int:
    with open(path) as f:
        data = json.load(f)
    updated = 0
    for r in data:
        # Applicable seulement aux trending restos + hôtels
        if r.get("source_type") not in ("trending", "both") and r.get("entity_type") != "hotel":
            continue
        texts = []
        for q in r.get("top_recent_quotes", []) or []:
            t = q.get("text", "") if isinstance(q, dict) else q
            if t:
                texts.append(t)
        if not texts:
            continue
        tags = detect(texts)
        if tags:
            r["occasion_tags"] = tags
            updated += 1
        elif "occasion_tags" in r:
            del r["occasion_tags"]
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return updated


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            n = process(p)
            print(f"{p.name}: {n} fiches enrichies avec occasion_tags")
