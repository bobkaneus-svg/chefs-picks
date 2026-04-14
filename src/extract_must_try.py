"""
Extrait des recommandations personnalisées et spécifiques depuis les avis Google
récents : plats à goûter absolument + autres éléments à ne pas rater.

Produit pour chaque resto trending un champ `must_try` :
[
  {"icon": "🍝", "label": "Penne allo scoglio", "kind": "dish"},
  {"icon": "🍷", "label": "La carte de vins naturels", "kind": "experience"},
  ...
]
"""
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]


# -- Catalogue de plats à reconnaître (avec icône)
# Formé pour matcher dans tout texte (FR/EN/ES/IT)
DISH_PATTERNS = [
    # Italien
    ("🍝", "Pâtes maison", r"\b(?:p[âa]tes?\s+(?:maison|fra[îi]ches?|fait(?:es)?\s+maison)|fresh\s+pasta|pasta\s+fresca|pasta\s+artigianale)\b"),
    ("🍝", "Carbonara", r"\bcarbonara\b"),
    ("🍝", "Cacio e pepe", r"\bcacio\s*e\s*pepe\b"),
    ("🍝", "Amatriciana", r"\bamatriciana\b"),
    ("🍝", "Tagliatelle", r"\btagliatell[ei]\b"),
    ("🍝", "Spaghetti aux fruits de mer", r"\b(?:spaghetti|penne|linguine)\s+(?:allo\s+scoglio|aux?\s+fruits\s+de\s+mer|al\s+frutti\s+di\s+mare)\b"),
    ("🍝", "Gnocchi", r"\bgnocchi\b"),
    ("🍝", "Ravioli", r"\bravioli\b"),
    ("🍝", "Lasagne", r"\blasagn[ei]\b"),
    ("🍕", "Pizza", r"\bpizza\b"),
    ("🧀", "Burrata", r"\bburrata\b"),
    ("🧀", "Mozzarella", r"\bmozzarella\b"),
    ("🇮🇹", "Tiramisu", r"\btiramis[uú]\b"),
    ("🇮🇹", "Risotto", r"\brisott[oi]\b"),
    # Poisson / mer
    ("🐟", "Poisson du jour", r"\bpoissons?\s+(?:du\s+jour|frais|grill[ée]s?|du\s+march[ée])\b"),
    ("🦞", "Bouillabaisse", r"\bbouillabaisse\b"),
    ("🦐", "Crevettes", r"\b(?:crevettes?|gambas|prawns|shrimps?)\b"),
    ("🐙", "Poulpe", r"\b(?:poulpe|pulpo|octopus|polpo)\b"),
    ("🦑", "Calamars", r"\b(?:calamars?|calamares|squid)\b"),
    ("🦀", "Crabe", r"\b(?:crabe|crab|cangrejo)\b"),
    ("🦪", "Huîtres", r"\b(?:hu[îi]tres?|oysters?|ostras?)\b"),
    ("🐠", "Ceviche", r"\bceviche\b"),
    ("🍣", "Sushi", r"\bsushis?\b"),
    ("🍣", "Sashimi", r"\bsashimis?\b"),
    # Viande
    ("🥩", "Côte de bœuf", r"\bc[ôo]te\s+de\s+b[oœ]uf\b"),
    ("🥩", "Filet de bœuf", r"\bfilet\s+(?:de\s+)?b[oœ]uf\b|\bfiletto\b|\bfilet\s+mignon\b"),
    ("🥩", "Black Angus", r"\bblack\s+angus\b"),
    ("🍖", "Magret de canard", r"\bmagret\s+de\s+canard\b"),
    ("🍖", "Agneau", r"\bagneau\b|\blamb\b|\bcordero\b"),
    ("🍔", "Burger", r"\bburgers?\b"),
    # Niçois / Provençal
    ("🥗", "Salade niçoise", r"\bsalade\s+ni[çc]oise\b"),
    ("🇫🇷", "Daube", r"\bdaube\b"),
    ("🇫🇷", "Farcis", r"\bfarcis?\s+(?:ni[çc]ois|provençaux?)?\b"),
    ("🇫🇷", "Socca", r"\bsocca\b"),
    ("🇫🇷", "Pissaladière", r"\bpissalad[ie][èe]res?\b"),
    # Asie
    ("🍜", "Pho", r"\bph[ôo]\b"),
    ("🥟", "Gyoza", r"\bgyozas?\b"),
    ("🥟", "Wonton", r"\bwontons?\b"),
    ("🥟", "Dim sum", r"\bdim\s+sum\b"),
    ("🍱", "Bento", r"\bbentos?\b"),
    # Petites assiettes / tapas
    ("🫒", "Tapas", r"\btapas\b"),
    ("🫒", "Mezze", r"\bm[ée]zz[ée]s?\b"),
    # Desserts
    ("🍰", "Dessert maison", r"\bdesserts?\s+(?:maison|fait\s+maison|fait\s+main)\b"),
    ("🍫", "Fondant chocolat", r"\bfondants?\s+(?:au\s+)?chocolat\b"),
    ("🍓", "Pavlova", r"\bpavlova\b"),
    # Autres
    ("🧀", "Fondue", r"\bfondue\b"),
    ("🥖", "Pain maison", r"\bpains?\s+(?:maison|fait\s+maison)\b|\bhomemade\s+bread\b"),
]

# Éléments d'expérience à ne pas rater
EXPERIENCE_PATTERNS = [
    ("🍷", "La carte des vins naturels", [
        r"vins?\s+naturels?", r"vins?\s+nature\b", r"natural\s+wines?",
    ]),
    ("🍷", "La sélection de vins", [
        r"(?:carte|s[ée]lection|liste)\s+(?:des?\s+)?vins?\s+(?:sublime|magnifique|au\s+top|exceptionnelle?|top|superbe|impressionnante?|extraordinaire|excellente)",
        r"wine\s+(?:list|selection|pairing)\s+(?:is\s+)?(?:great|amazing|excellent|superb|impressive)",
        r"sommelier",
    ]),
    ("🍸", "Les cocktails maison", [
        r"cocktails?\s+(?:maison|signature|originaux?|cr[ée]atifs?|exceptionnels?|au\s+top|excellents?)",
        r"signature\s+cocktails?", r"creative\s+cocktails?",
    ]),
    ("🌊", "La vue sur la mer", [
        r"vue\s+sur\s+(?:la\s+)?mer", r"sea\s+view", r"vista\s+(?:al?\s+)?mar",
    ]),
    ("☀️", "La terrasse", [
        r"belle\s+terrasse", r"jolie\s+terrasse", r"terrasse\s+(?:magnifique|sublime|au\s+top|incroyable|superbe|charmante)",
        r"lovely\s+terrace", r"beautiful\s+terrace", r"terraza\s+(?:preciosa|maravillosa|encantadora)",
    ]),
    ("🌅", "Le coucher de soleil", [
        r"coucher\s+de\s+soleil", r"sunset", r"puesta\s+de\s+sol", r"tramonto",
    ]),
    ("🎶", "L'ambiance musicale", [
        r"excellente\s+musique", r"belle\s+musique", r"super\s+ambiance\s+musicale",
        r"great\s+music", r"playlist\s+(?:au\s+top|g[ée]niale)",
    ]),
    ("📅", "Réserver à l'avance (très demandé)", [
        r"r[ée]server?\s+(?:[àa]\s+l[’']avance|en\s+avance|toujours)",
        r"toujours\s+(?:plein|bond[ée]|complet)",
        r"(?:always\s+|usually\s+)?(?:full|booked|busy)",
        r"siempre\s+(?:est[áa]\s+)?lleno",
    ]),
    ("👨‍🍳", "Le menu dégustation du chef", [
        r"menu\s+d[ée]gustation", r"tasting\s+menu", r"men[uú]\s+degustaci[oó]n",
        r"men[uú]\s+(?:de\s+)?d[ée]gustation",
    ]),
    ("🍞", "Le pain maison", [
        r"pains?\s+(?:maison|fait\s+maison|fait\s+main|d[ée]licieux)",
        r"homemade\s+bread", r"pan\s+casero",
    ]),
    ("🥗", "Les options sans gluten / végé", [
        r"sans\s+gluten", r"gluten[- ]?free", r"senza\s+glutine", r"sin\s+gluten",
        r"v[ée]g[ée]tarien(?:nes?)?", r"v[ée]gan", r"vegetarian", r"vegano?",
    ]),
]


def normalize(text: str) -> str:
    return text.lower() if text else ""


def find_dishes(corpus: str) -> list:
    """Retourne une liste ordonnée de plats trouvés (avec icône) — max 4."""
    counts = Counter()
    icons = {}
    for icon, label, pattern in DISH_PATTERNS:
        n = len(re.findall(pattern, corpus, flags=re.IGNORECASE))
        if n >= 1:
            counts[label] += n
            icons[label] = icon
    top = counts.most_common(4)
    return [{"icon": icons[label], "label": label, "kind": "dish", "mentions": n} for label, n in top]


def find_experiences(corpus: str) -> list:
    """Retourne une liste d'expériences à ne pas rater — max 3."""
    counts = Counter()
    icons = {}
    for icon, label, patterns in EXPERIENCE_PATTERNS:
        n = 0
        for p in patterns:
            n += len(re.findall(p, corpus, flags=re.IGNORECASE))
        if n >= 1:
            counts[label] += n
            icons[label] = icon
    top = counts.most_common(3)
    return [{"icon": icons[label], "label": label, "kind": "experience", "mentions": n} for label, n in top]


def build_must_try(reviews: list) -> list:
    if not reviews:
        return []
    corpus = " ".join(normalize(r) for r in reviews)
    dishes = find_dishes(corpus)
    exps = find_experiences(corpus)
    # Mélange : dishes en priorité (max 4) + experiences (max 3) → max 6 total
    out = dishes[:4] + exps[:3]
    return out[:6]


def process_file(path: Path) -> int:
    with open(path) as f:
        data = json.load(f)

    updated = 0
    for r in data:
        if r.get("source_type") not in ("trending", "both"):
            continue

        texts = []
        for q in r.get("top_recent_quotes", []) or []:
            txt = q.get("text", "") if isinstance(q, dict) else q
            if txt:
                texts.append(txt)

        must_try = build_must_try(texts)
        if must_try:
            r["must_try"] = must_try
            updated += 1

    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return updated


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            n = process_file(p)
            print(f"{p.name}: {n} restos enrichis avec must_try")
