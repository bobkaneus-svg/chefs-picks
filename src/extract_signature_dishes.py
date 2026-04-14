"""
Extrait les PLATS SIGNATURE spécifiques de chaque restaurant depuis les avis.
Au lieu de tags génériques ('Burrata'), récupère la phrase réelle avec ses
descripteurs ('la burrata crémeuse avec confiture de tomates').

Output : remplace `must_try` par des entrées enrichies :
{
  "icon": "🧀",
  "phrase": "la burrata crémeuse avec sa confiture de tomates",
  "mentions": 3
}
"""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]


# =======================================================
# Catalogue d'icônes par mot-clé de plat
# =======================================================
DISH_ICONS = {
    # Italien
    "pâtes": "🍝", "pâte": "🍝", "pasta": "🍝",
    "carbonara": "🍝", "amatriciana": "🍝", "cacio": "🍝",
    "tagliatelle": "🍝", "tagliatelli": "🍝",
    "spaghetti": "🍝", "spaghetto": "🍝",
    "penne": "🍝", "linguine": "🍝",
    "gnocchi": "🍝", "gnocci": "🍝", "gnocchis": "🍝",
    "ravioli": "🍝", "raviolis": "🍝",
    "lasagne": "🍝", "lasagnes": "🍝",
    "risotto": "🍲", "risotti": "🍲",
    "pizza": "🍕", "pizzas": "🍕",
    "burrata": "🧀", "mozzarella": "🧀", "ricotta": "🧀", "parmesan": "🧀",
    "tiramisu": "🍰", "tiramisù": "🍰",
    # Poisson / mer
    "poisson": "🐟", "fish": "🐟",
    "saumon": "🐟", "salmon": "🐟",
    "thon": "🐟", "tuna": "🐟",
    "loup": "🐟", "daurade": "🐟", "dorade": "🐟",
    "bouillabaisse": "🦞",
    "crevette": "🦐", "crevettes": "🦐", "gambas": "🦐", "shrimp": "🦐", "prawn": "🦐",
    "poulpe": "🐙", "octopus": "🐙", "pulpo": "🐙", "polpo": "🐙",
    "calamar": "🦑", "calamars": "🦑", "calamares": "🦑", "squid": "🦑",
    "crabe": "🦀", "crab": "🦀",
    "huître": "🦪", "huîtres": "🦪", "oyster": "🦪", "oysters": "🦪",
    "ceviche": "🐠",
    "sushi": "🍣", "sushis": "🍣", "sashimi": "🍣",
    "homard": "🦞", "lobster": "🦞", "langouste": "🦞",
    "tartare": "🥩",
    "carpaccio": "🥩",
    # Viande
    "steak": "🥩", "entrecôte": "🥩", "filet": "🥩", "filetto": "🥩",
    "bœuf": "🥩", "boeuf": "🥩", "beef": "🥩",
    "magret": "🍖", "canard": "🍖", "duck": "🍖",
    "agneau": "🍖", "lamb": "🍖", "cordero": "🍖",
    "veau": "🍖", "veal": "🍖",
    "foie": "🍖",  # foie gras
    "cochon": "🥓", "porc": "🥓", "pork": "🥓",
    "poulet": "🍗", "chicken": "🍗",
    "burger": "🍔", "burgers": "🍔",
    # Niçois / Provençal
    "socca": "🇫🇷", "farcis": "🇫🇷", "daube": "🇫🇷",
    "pissaladière": "🇫🇷",
    # Asie
    "pho": "🍜", "bo": "🍜", "ramen": "🍜", "udon": "🍜",
    "bento": "🍱",
    "gyoza": "🥟", "gyozas": "🥟",
    "wonton": "🥟", "wontons": "🥟",
    "bao": "🥟",
    "dim": "🥟",  # dim sum
    # Petits formats
    "tapas": "🫒", "mezze": "🫒", "mézzé": "🫒",
    "croquette": "🫒", "croquettes": "🫒", "croqueta": "🫒",
    # Desserts (plus spécifiques : évite "dessert" seul)
    "fondant": "🍫",
    "pavlova": "🍓",
    "panna": "🍮",  # panna cotta
    "cheesecake": "🍰",
    "brownie": "🍫",
    # Autres
    "fondue": "🧀",
    "crêpe": "🥞", "crêpes": "🥞", "crepe": "🥞",
    "galette": "🥞", "galettes": "🥞",
    "salade": "🥗", "salad": "🥗", "ensalada": "🥗",
}


# Mots à exclure en début de phrase (filtrer "pasta" isolé sans contexte)
STOP_HEADS = {"a", "an", "the", "le", "la", "les", "un", "une", "des", "du",
              "my", "mon", "ma", "our", "notre", "nos"}


# =======================================================
# Extraction
# =======================================================

FOOD_WORDS_PATTERN = r"\b(" + "|".join(
    sorted(DISH_ICONS.keys(), key=len, reverse=True)
) + r")\b"


def _article_prefix_fr() -> str:
    return r"(?:la|le|les|des|un|une|du|de\s+la|de\s+l[’']|d['’])"


def _article_prefix_en() -> str:
    return r"(?:the|a|an)"


def split_sentences(text: str) -> list:
    """Split en phrases. Si le texte est tronqué (exactement 250 chars,
    hard limit d'Apify), on ignore la dernière phrase (incomplete)."""
    if not text:
        return []
    text = text.strip()
    # Détection tronqué Apify (250 chars hard limit, sans ponctuation finale)
    is_truncated = len(text) >= 249 and not re.search(r"[.!?…]$", text)
    parts = re.split(r"[.!?\n]+", text)
    parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 5]
    if is_truncated and parts:
        parts = parts[:-1]  # retire la dernière phrase qui est forcément incomplète
    return parts


def clean_phrase(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^[,.;:!?\-–—()\s]+", "", s)
    s = re.sub(r"[,.;:!?\-–—()\s]+$", "", s)
    # Supprime les connecteurs parasites en début
    s = re.sub(r"^(?:et|and|mais|but|avec|with|aussi|also|or|ou)\s+", "", s, flags=re.IGNORECASE)
    return s


def truncate_clean(s: str, max_len: int = 90) -> str:
    """Tronque sans couper un mot en plein milieu. Gère aussi les mots déjà
    coupés en fin (reviews Apify tronquées à 250 chars)."""
    if not s:
        return s
    # Si le texte se termine par un mot tronqué (pas de ponctuation + dernier "mot" court)
    # → coupe jusqu'au dernier espace
    stripped = s.rstrip()
    if stripped and not re.search(r"[.!?…]$", stripped):
        # Dernier mot
        last_space = stripped.rfind(" ")
        if last_space > 0:
            last_word = stripped[last_space + 1:]
            # Mot probablement tronqué si : très court ET dernier char n'est pas ponctuation
            if len(last_word) <= 3 and not re.search(r"[.!?,;:]", last_word):
                stripped = stripped[:last_space].rstrip(",;:-–—")
                s = stripped + "…"
    # Puis truncation "soft" si trop long
    if len(s) <= max_len:
        return s
    cut = s.rfind(" ", 0, max_len)
    if cut <= max_len // 2:
        cut = max_len
    return s[:cut].rstrip(",;:-–—") + "…"


def capitalize_first(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


def extract_dish_phrases(reviews: list) -> list:
    """
    Pour chaque food word trouvé dans les reviews, capture une "clause"
    (phrase/sous-phrase) qui l'entoure avec contexte.
    Retourne une liste rankée par fréquence + spécificité.
    """
    variants = defaultdict(Counter)
    icon_total = Counter()

    for txt in reviews:
        if not txt:
            continue
        # On split d'abord sur les séparateurs forts (. ! ? \n)
        # Puis on splitte sur les virgules/tirets pour obtenir des clauses courtes
        for sent in split_sentences(txt):
            sl = sent.lower()
            if re.search(r"\b(pas\s+(?:bon|terrible)|not\s+(?:good|great)|d[ée]çu|disappointed|awful|terrible|horrible)\b", sl):
                continue

            # On détecte chaque food word et on prend la clause l'entourant
            # Une clause = portion délimitée par ponctuation forte OU connecteurs
            # On splitte sur : , ; — – ( )
            clauses = re.split(r"[,;()–—]|\s+(?:mais|but|cependant|however)\s+", sent)
            for clause in clauses:
                clause = clause.strip()
                if not clause:
                    continue
                cl = clause.lower()
                for m in re.finditer(FOOD_WORDS_PATTERN, cl, flags=re.IGNORECASE):
                    word = m.group(1).lower()
                    icon = DISH_ICONS.get(word)
                    if not icon:
                        continue

                    phrase = clean_phrase(clause)
                    if len(phrase) < 8:
                        continue
                    # Rejet des phrases qui sont clairement juste le mot + article
                    words_in_phrase = phrase.split()
                    if len(words_in_phrase) < 3:
                        continue

                    phrase = truncate_clean(phrase, 110)
                    variants[icon][phrase] += 1
                    icon_total[icon] += 1
                    break  # 1 mot/clause suffit

    # Pour chaque icône, choisit la meilleure phrase (spécificité + fréquence)
    out = []
    used_keys = set()
    for icon, n_total in icon_total.most_common(6):
        # Sélectionne la phrase la plus descriptive parmi les variantes
        best = None
        best_score = -1
        for phrase, count in variants[icon].items():
            words = phrase.split()
            nw = len(words)
            # Score : favorise phrases riches (4-10 mots) + compteur
            # Pénalise les phrases trop courtes (juste le mot)
            if nw < 2:
                length_bonus = 0
            elif nw < 4:
                length_bonus = 1
            elif nw <= 10:
                length_bonus = 3
            else:
                length_bonus = 2
            score = count * 2 + length_bonus * 3
            if score > best_score:
                best_score = score
                best = phrase
        if not best:
            continue
        best = capitalize_first(best)
        # Dedup : si déjà une phrase très similaire dans le pool, skip
        key = re.sub(r"\W+", "", best.lower())[:40]
        is_dup = any(k in key or key in k for k in used_keys)
        if is_dup:
            continue
        used_keys.add(key)
        out.append({"icon": icon, "phrase": best, "mentions": n_total})
        if len(out) >= 4:
            break

    return out


# =======================================================
# Signature phrase : 1 phrase distinctive par resto
# =======================================================

DISTINCTIVE_PATTERNS = [
    # Le chef
    (r"(?:le\s+)?chef\s+(?:[a-zéèêàâîïôûùç]+\s+)?(?:s['’]?exprime|se\s+livre|fait\s+preuve|met\s+l['’]?âme|nous\s+surprend|propose|prépare|cuisine|offre|sublime|sort\s+de\s+sa\s+cuisine|signe)[^.!?\n]{10,80}", 3),
    (r"(?:the\s+)?chef\s+(?:really\s+)?(?:knows|goes|puts|surprises|showcases|delivers|sends\s+out|brings)[^.!?\n]{10,80}", 3),
    # Le lieu
    (r"(?:un|une|the)\s+(?:endroit|lieu|spot|place|restaurant)\s+(?:où|qui|that|where)[^.!?\n]{15,90}", 2),
    # Ambiance unique
    (r"(?:l['’]?ambiance|the\s+atmosphere|the\s+vibe)\s+(?:est|was|is|feels?)[^.!?\n]{10,80}", 2),
    # "On a l'impression de"
    (r"on\s+(?:a\s+)?(?:l['’]?impression|se\s+sent)\s+(?:de\s+|d['’])?[^.!?\n]{10,70}", 2),
    # "Feels like..."
    (r"feels?\s+(?:like|as\s+if)[^.!?\n]{10,70}", 2),
    # Mention spéciale / signature
    (r"mention\s+sp[ée]ciale[^.!?\n]{10,90}", 3),
    (r"la\s+(?:vraie\s+)?star\s+(?:ici|c['’]?est)[^.!?\n]{5,70}", 4),
    (r"(?:highlight|star)\s+of\s+the\s+(?:meal|evening|night)[^.!?\n]{5,70}", 3),
    # "Coup de cœur"
    (r"coup\s+de\s+c[oœ]ur\s+(?:pour|sur|[àa])[^.!?\n]{5,70}", 4),
    # Concept
    (r"(?:cuisine|plats?|food|menu)\s+(?:qui|that)\s+(?:m[ée]lange|combine|unit|blend|mixes?|brings?|takes?)[^.!?\n]{10,90}", 3),
    # On reviendra
    (r"(?:on\s+(?:y\s+)?reviendra|we['’]?ll\s+(?:definitely\s+)?(?:be\s+back|return))[^.!?\n]{0,60}", 2),
]


def extract_signature_phrase(reviews: list) -> str:
    """Cherche UNE phrase distinctive qui capture l'essence du resto.
    Retourne la phrase complète (jusqu'au point), jamais tronquée mid-mot."""
    scored = []
    for txt in reviews:
        if not txt:
            continue
        for sent in split_sentences(txt):
            sl = sent.lower()
            if len(sent) < 25 or len(sent) > 200:
                continue
            if re.search(r"\b(pas\s+(?:bon|terrible)|déçu|disappointed|awful|horrible|worst)\b", sl):
                continue
            for pattern, weight in DISTINCTIVE_PATTERNS:
                if re.search(pattern, sl, re.IGNORECASE):
                    scored.append((weight + len(sent) // 30, sent))
                    break
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    best = clean_phrase(scored[0][1])
    # Tronque proprement à la virgule/mot si > 160 chars
    best = truncate_clean(best, 160)
    best = capitalize_first(best)
    return best


# =======================================================
# Main
# =======================================================

def process(path: Path) -> int:
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
        if not texts:
            continue

        # 1. Plats signature — overwrite toujours (nettoyer les anciens vestiges)
        sig_dishes = extract_dish_phrases(texts)
        if sig_dishes:
            r["signature_dishes"] = sig_dishes
            updated += 1
        elif "signature_dishes" in r:
            del r["signature_dishes"]

        # 2. Phrase signature
        sig_phrase = extract_signature_phrase(texts)
        if sig_phrase:
            r["signature_phrase"] = sig_phrase
        elif "signature_phrase" in r:
            del r["signature_phrase"]

    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return updated


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            n = process(p)
            print(f"{p.name}: {n} restos enrichis avec signature_dishes")
