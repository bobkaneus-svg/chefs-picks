"""
Extrait un guide "première visite" pour chaque resto trending depuis les vrais avis :
- Plats exacts recommandés (phrases extraites des reviews)
- Conseils sur l'endroit où s'asseoir (table, terrasse...)
- Conseils sur le moment (midi, soir, saison)
- Conseils de réservation
- Autres astuces (menu dégustation, accords...)

Produit pour chaque resto un champ `first_visit` :
{
  "order": ["les gnocchi à la truffe", "le steak de Black Angus"],
  "tips": [
    {"icon": "🪑", "text": "Demande une table en terrasse, la vue est magnifique"},
    {"icon": "📅", "text": "Réserve 2-3 jours à l'avance, c'est souvent complet"},
    {"icon": "👨‍🍳", "text": "Prends le menu dégustation pour ta première visite"}
  ]
}
"""
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]


# =======================================================
# PASS 1 : Extraction des plats commandés (phrases réelles)
# =======================================================

# Verbes "prendre/commander/goûter/avoir testé" en FR/EN/ES/IT
ORDER_VERBS_FR = r"(?:j['’]?\s*ai\s+(?:pris|commandé|goûté|adoré|testé|mangé)|nous\s+avons\s+(?:pris|commandé|mangé|testé|eu|partagé|goûté)|on\s+a\s+(?:pris|commandé|mangé|testé|eu|partagé|goûté|choisi|adoré)|elle\s+a\s+(?:pris|goûté)|il\s+a\s+(?:pris|goûté)|ma\s+femme\s+a\s+(?:pris|goûté)|mon\s+mari\s+a\s+(?:pris|goûté))"
ORDER_VERBS_EN = r"(?:we\s+(?:had|tried|ordered|tasted|shared|got)|i\s+(?:had|tried|ordered|tasted|got|enjoyed)|my\s+\w+\s+had)"
ORDER_VERBS_ES = r"(?:pedimos|pedí|probamos|probé|tomamos|tomé|tuvimos|tuve|compartimos)"
ORDER_VERBS_IT = r"(?:abbiamo\s+(?:preso|ordinato|provato|mangiato|condiviso)|ho\s+(?:preso|ordinato|provato|mangiato))"

# "Je recommande X" / "must try X"
RECO_VERBS_FR = r"(?:je\s+recommande|je\s+conseille|incontournable|à\s+(?:goûter|prendre|essayer|commander)|il\s+faut\s+(?:prendre|goûter|essayer|commander)|ne\s+ratez\s+pas)"
RECO_VERBS_EN = r"(?:must[\s-]?try|don['’]?t\s+miss|highly\s+recommend|definitely\s+(?:get|try|order)|make\s+sure\s+to\s+(?:get|try|order)|we\s+recommend)"
RECO_VERBS_ES = r"(?:imprescindible|(?:muy\s+)?recomendable|no\s+te\s+pierdas|hay\s+que\s+probar)"

# Mots de plats / aliments usuels
FOOD_WORDS = r"(?:plat|entrée|dessert|pâtes?|pasta|pizza|risotto|gnocchi|ravioli|carbonara|amatriciana|steak|entrecôte|bœuf|boeuf|beef|magret|canard|duck|poisson|fish|saumon|salmon|thon|tuna|bar|loup|daurade|poulpe|octopus|pulpo|polpo|calamar|seiche|crevette|gambas|prawn|shrimp|huître|oyster|ostra|bouillabaisse|ceviche|sushi|sashimi|tartare|carpaccio|burrata|mozzarella|ricotta|parmesan|fromage|cheese|soup|soupe|salade|salad|ensalada|risotto|truffe|truffle|tiramisu|tiramisù|panna\s+cotta|fondant|mousse|cheesecake|brownie|crêpe|gaufre|socca|farcis|daube|ravioli\s+niçois|salade\s+niçoise|pissaladière|pho|bo\s+bun|ramen|udon|bento|gyoza|wonton|dim\s+sum|bao|curry|couscous|tajine|kebab|falafel|hummus|mezze|mézzé|brunch|tapas|paella|tortilla|fideuà|croqueta|jambon|charcuterie|cochon|agneau|lamb|veau|veal|foie\s+gras|homard|lobster|langouste|crabe|crab|bisque|cocktail|menu\s+dégustation|tasting\s+menu|plat\s+du\s+jour)"

# Adjectifs positifs courts
POSITIVE_ADJ = r"(?:délicieux|succulent|excellent|incroyable|fantastique|parfait|sublime|divin|à\s+tomber|amazing|delicious|incredible|perfect|wonderful|heavenly|outstanding|superbe|magnifique|exquis|exceptional|exquisite)"


def clean_sentence(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^[,.;:!?\-–—\s]+", "", s)
    s = re.sub(r"[,.;:!?\-–—\s]+$", "", s)
    return s


def split_sentences(text: str) -> list:
    # Split sur . ! ? \n
    parts = re.split(r"[.!?\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def extract_order_snippets(reviews: list) -> list:
    """Cherche dans les reviews les phrases mentionnant un plat + contexte positif/reco.
    Retourne la phrase complète nettoyée (max 160 chars)."""
    candidates = Counter()
    any_verb = "|".join([ORDER_VERBS_FR, ORDER_VERBS_EN, ORDER_VERBS_ES, ORDER_VERBS_IT,
                          RECO_VERBS_FR, RECO_VERBS_EN, RECO_VERBS_ES])
    any_reco = "|".join([RECO_VERBS_FR, RECO_VERBS_EN, RECO_VERBS_ES])

    for txt in reviews:
        if not txt:
            continue
        for sent in split_sentences(txt):
            sent_l = sent.lower()
            if not re.search(FOOD_WORDS, sent_l, re.IGNORECASE):
                continue
            has_verb = re.search(any_verb, sent_l, re.IGNORECASE)
            has_positive = re.search(POSITIVE_ADJ, sent_l, re.IGNORECASE)
            has_reco = re.search(any_reco, sent_l, re.IGNORECASE)
            # Filtre : il faut au moins (verbe de commande + positif) OU (verbe de reco)
            if not (has_reco or (has_verb and has_positive)):
                continue
            snippet = clean_sentence(sent)
            # Trim longueur
            if len(snippet) < 25:
                continue
            if len(snippet) > 160:
                # Essaye de couper à une virgule proche de 140
                cut = snippet.rfind(",", 80, 150)
                if cut > 80:
                    snippet = snippet[:cut]
                else:
                    snippet = snippet[:157] + "…"
            # Capitalise la première lettre
            snippet = snippet[0].upper() + snippet[1:] if snippet else snippet
            candidates[snippet] += 1

    # Dédup par similarité (ignore quasi-doublons)
    top = []
    seen_sigs = set()
    for snip, _ in candidates.most_common(20):
        sig = re.sub(r"\s+", " ", snip.lower())[:50]
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        top.append(snip)
        if len(top) >= 3:
            break
    return top


# =======================================================
# PASS 2 : Conseils pratiques (table, timing, réservation)
# =======================================================

TIP_PATTERNS = [
    # Seating / table
    ("🪑", "Demande une table en terrasse, la vue vaut le détour", [
        r"table\s+en\s+terrasse", r"terrasse\s+avec\s+vue", r"vue\s+(?:imprenable|magnifique|incroyable|[àa]\s+couper)\s+(?:depuis|de\s+la)\s+terrasse",
        r"terrace\s+(?:view|seating)", r"on\s+the\s+terrace",
    ]),
    ("🌊", "Demande une table avec vue sur la mer", [
        r"vue\s+sur\s+(?:la\s+)?mer", r"sea\s+view", r"face\s+à\s+la\s+mer", r"face\s+mer",
        r"view\s+of\s+the\s+(?:sea|ocean|water|port|harbour|harbor)", r"vue\s+sur\s+le\s+port",
        r"overlook\w*\s+the\s+(?:sea|ocean|port|harbour)",
    ]),
    ("🏔️", "Opte pour une table près de la baie vitrée", [
        r"baie\s+vitr[ée]e?", r"window\s+seat", r"près\s+de\s+la\s+fenêtre",
    ]),
    ("🔥", "Installe-toi près de la cheminée en hiver", [
        r"chemin[ée]e", r"(?:by|near)\s+the\s+fireplace", r"fireside",
    ]),
    ("🌳", "Réserve une table dans le jardin / patio", [
        r"(?:jolie?|joli\s+|beau\s+|magnifique\s+)?jardin\s+(?:magnifique|cach[ée]|caché|intérieur)?",
        r"patio", r"cour\s+intérieure", r"courtyard", r"garden\s+(?:seating|table)",
    ]),
    # Timing
    ("🌇", "Viens plutôt pour le dîner, l'ambiance est magique le soir", [
        r"(?:le\s+)?(?:dîner|d[îi]ner|soir)\s+(?:est|c['’]?est)\s+(?:magique|g[ée]nial|incroyable|au\s+top|mieux)",
        r"much\s+better\s+(?:at|for)\s+(?:dinner|night)", r"evening\s+is\s+(?:magical|amazing|better)",
        r"dinner\s+is\s+(?:magical|amazing|the\s+best)",
    ]),
    ("☀️", "Préfère le déjeuner en terrasse au soleil", [
        r"midi\s+(?:en\s+terrasse|au\s+soleil)", r"lunch\s+on\s+the\s+terrace",
        r"d[ée]jeuner\s+en\s+terrasse",
    ]),
    ("📅", "Hors saison, c'est l'expérience la plus authentique", [
        r"hors\s+saison", r"off[- ]?season", r"pas\s+en\s+haute\s+saison",
        r"[àa]\s+éviter\s+l['’]?été", r"fuera\s+de\s+temporada",
    ]),
    # Booking
    ("📞", "Réserve plusieurs jours à l'avance, c'est souvent complet", [
        r"r[ée]serve[rz]?\s+(?:[àa]\s+l[’']avance|en\s+avance|tôt|vite|plusieurs\s+jours|[0-9]+\s+jours?)",
        r"pens(?:e[rz]?|ons?)\s+[àa]\s+r[ée]serv",
        r"toujours\s+(?:plein|bond[ée]|complet|difficile\s+d['’]?avoir)",
        r"(?:impossible\s+d['’]?|pas\s+facile\s+d['’]?)avoir\s+(?:une\s+)?table",
        r"book\s+(?:well\s+)?in\s+advance", r"reservation\s+(?:is\s+)?(?:essential|recommended|required|a\s+must)",
        r"siempre\s+(?:est[áa]\s+)?lleno", r"hay\s+que\s+reservar",
        r"(?:always|usually)\s+(?:full|packed|booked)",
    ]),
    ("👨‍🍳", "Prends le menu dégustation pour découvrir le chef", [
        r"menu\s+d[ée]gustation", r"tasting\s+menu", r"men[uú]\s+(?:de\s+)?degustaci[oó]n",
    ]),
    ("🗣️", "Laisse-toi guider par le patron ou le chef", [
        r"(?:le\s+)?(?:patron|patronne|propri[ée]taire|chef)\s+(?:vous|nous)\s+(?:conseille|guide|recommande)",
        r"laissez?[- ]?vous\s+(?:guider|tenter|conseiller)",
        r"let\s+(?:them|the\s+chef|the\s+owner)\s+(?:guide|recommend|choose)",
        r"(?:let|ask)\s+the\s+(?:chef|owner|waiter)\s+to\s+(?:recommend|choose)",
    ]),
    ("🍷", "Fais-toi conseiller sur les accords mets & vins", [
        r"accord(?:s)?\s+mets?[- ]?(?:et\s+)?vins?",
        r"wine\s+pairing", r"(?:excellent|great|superb)\s+sommelier",
        r"sommelier\s+(?:au\s+top|excellent|g[ée]nial|formidable|formidable)",
    ]),
    ("🎯", "Goûte absolument le plat du jour, il est souvent bluffant", [
        r"plat\s+du\s+jour\s+(?:est|était|toujours)\s+(?:incroyable|g[ée]nial|au\s+top|excellent|d[ée]licieux|\u00e0\s+tomber)",
        r"(?:daily|today['’]?s)\s+special\s+(?:is|was)\s+(?:amazing|incredible|great)",
        r"plato\s+del\s+d[ií]a",
    ]),
    ("🍞", "Garde de la place pour le pain maison", [
        r"pain\s+(?:maison|fait\s+maison)", r"homemade\s+bread",
    ]),
    ("🍰", "Ne pars pas sans un dessert", [
        r"desserts?\s+(?:[àa]\s+tomber|incroyables?|divins?|sublimes?|exceptionnels?)",
        r"desserts?\s+maison", r"(?:amazing|incredible|divine|heavenly)\s+desserts?",
        r"(?:ne\s+)?ratez?\s+pas\s+(?:les\s+)?desserts?",
    ]),
    ("👥", "Viens en petit comité, le lieu est intime", [
        r"petit(?:e)?\s+(?:salle|endroit|lieu|espace)", r"intime", r"intimate",
        r"small\s+(?:restaurant|venue|space)", r"cozy", r"cosy",
    ]),
    ("💰", "Reste raisonnable, le rapport qualité-prix est excellent", [
        r"(?:excellent|super|très\s+bon|incroyable)\s+rapport\s+qualit[ée][- /]+prix",
        r"great\s+value\s+(?:for\s+money)?", r"worth\s+every\s+(?:penny|euro)",
        r"precio\s+(?:muy\s+)?(?:bueno|razonable|justo)",
    ]),
]


def extract_tips(reviews: list) -> list:
    """Retourne max 4 conseils pratiques rankés par nombre de mentions."""
    if not reviews:
        return []
    corpus = " ".join(reviews).lower()
    scored = []
    for icon, text, patterns in TIP_PATTERNS:
        count = 0
        for p in patterns:
            count += len(re.findall(p, corpus, flags=re.IGNORECASE))
        if count >= 1:
            scored.append((count, icon, text))
    scored.sort(key=lambda x: -x[0])
    # Déduplique par emoji (1 seul conseil par famille)
    seen_icons = set()
    out = []
    for count, icon, text in scored:
        if icon in seen_icons:
            continue
        seen_icons.add(icon)
        out.append({"icon": icon, "text": text})
        if len(out) >= 4:
            break
    return out


# =======================================================
# Main
# =======================================================

def build_first_visit(reviews: list) -> dict:
    order = extract_order_snippets(reviews)
    tips = extract_tips(reviews)
    if not order and not tips:
        return None
    out = {}
    if order:
        out["order"] = order
    if tips:
        out["tips"] = tips
    return out


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
        fv = build_first_visit(texts)
        if fv:
            r["first_visit"] = fv
            updated += 1
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return updated


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            n = process(p)
            print(f"{p.name}: {n} restos enrichis avec first_visit")
