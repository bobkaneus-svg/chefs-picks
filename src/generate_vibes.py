"""
Génère des "vibes" humanisées pour les restaurants trending à partir
de leurs avis Google récents. Remplace les tags génériques par des
phrases inspirantes façon "conseiller culinaire".
"""
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]

# Patterns multilingues (FR / EN / ES / IT / CA) → vibe humanisée
VIBES = [
    ("🌟 Une vraie pépite à découvrir", [
        r"p[ée]pite", r"tr[ée]sor", r"hidden\s+gem", r"joya", r"gem\b",
        r"coup\s+de\s+cœur", r"(?:une\s+)?(?:vraie\s+|belle\s+)?(?:r[ée]v[ée]lation|d[ée]couverte)",
        r"que\s+du\s+bonheur", r"inoubliable", r"incroyable", r"exceptionnelle?",
        r"magnifique(?:\s+exp[ée]rience)?", r"unforgettable", r"amazing\s+experience",
    ]),
    ("👨‍🍳 Un chef qui met de l'âme dans l'assiette", [
        r"chef\s+(?:au\s+top|talentueux|passionn[ée]|g[ée]nial|incroyable)",
        r"(?:le\s+)?chef\s+(?:est|nous)\s+(?:vient|venu|sort|passe)",
        r"signature\s+du\s+chef", r"passion\s+du\s+chef",
        r"(?:un|the)\s+(?:vrai|true)\s+chef", r"talent\s+du\s+chef",
        r"chef\s+is\s+(?:amazing|talented|passionate)",
    ]),
    ("🤗 Un accueil chaleureux comme à la maison", [
        r"accueil\s+(?:chaleureux|adorable|top|au\s+top|formidable|exceptionnel|super|parfait|g[ée]nial)",
        r"tr[èe]s\s+bien\s+accueilli", r"comme\s+[aà]\s+la\s+maison",
        r"propri[ée]taire\s+(?:adorable|charmant|super|sympa)",
        r"(?:patron|patronne)\s+(?:adorable|au\s+top|g[ée]nial|sympa)",
        r"warm\s+welcome", r"feels?\s+like\s+home", r"home[- ]?made\s+feeling",
        r"super\s+amable", r"muy\s+amable", r"equipo\s+encantador",
        r"personnel\s+(?:adorable|charmant|aux\s+petits\s+soins|au\s+top)",
        r"(?:l[’']?|the\s+)?[ée]quipe\s+(?:est\s+)?(?:adorable|au\s+top|g[ée]niale|g[ée]nial|formidable)",
    ]),
    ("🎨 Une cuisine créative qui surprend", [
        r"(?:cuisine|plats?)\s+(?:cr[ée]ative?s?|inventive?s?|originale?s?|surprenante?s?|audacieuse?s?)",
        r"originalit[ée]", r"saveurs?\s+(?:surprenantes?|inattendues?|nouvelles?)",
        r"(?:association|mariage)\s+de\s+saveurs",
        r"creative\s+(?:cuisine|food|dishes|menu)", r"innovative",
        r"cocina\s+creativa", r"toque\s+de\s+innovaci[oó]n",
        r"revisit[ée]e?", r"twist", r"inspir[ée]e?",
    ]),
    ("🌊 Une vue qui coupe le souffle", [
        r"vue\s+(?:imprenable|magnifique|[àa]\s+couper\s+le\s+souffle|exceptionnelle?|incroyable|sublime|splendide)",
        r"vue\s+(?:sur\s+la\s+mer|sur\s+le\s+port|sur\s+les\s+montagnes|panoramique)",
        r"terrasse\s+(?:magnifique|avec\s+vue|sublime|sur\s+le\s+port)",
        r"rooftop", r"panoramic\s+view", r"stunning\s+view", r"breathtaking\s+view",
        r"vista(?:s)?\s+(?:espectacular|impresionante|maravillosa)",
    ]),
    ("🐟 Des produits ultra-frais, choisis avec soin", [
        r"(?:produits?|ingr[ée]dients?)\s+(?:frais|ultra[- ]?frais|de\s+qualit[ée]|d'?excellente\s+qualit[ée]|locaux)",
        r"poissons?\s+(?:frais|du\s+jour|du\s+march[ée])",
        r"(?:du|au)\s+march[ée]\s+du\s+jour", r"circuit\s+court",
        r"producteurs?\s+locaux", r"fermes?\s+(?:du\s+coin|locales?)",
        r"fresh\s+(?:fish|seafood|ingredients|produce)",
        r"producto\s+(?:fresco|local|de\s+calidad|de\s+temporada)",
        r"local\s+produce", r"farm[- ]?to[- ]?table",
    ]),
    ("🍷 Une carte des vins qui fait voyager", [
        r"(?:carte|s[ée]lection)\s+(?:des?\s+)?vins?\s+(?:sublime|magnifique|au\s+top|exceptionnelle?|top|superbe|impressionnante?|extraordinaire)",
        r"vins?\s+naturels?", r"vins?\s+nature\b", r"(?:belle|magnifique)\s+cave",
        r"accord(?:s)?\s+mets?[- ]et[- ]vins?", r"accord\s+mets?[- ]vins?",
        r"wine\s+(?:list|selection|pairing)\s+(?:is\s+)?(?:great|amazing|excellent|superb)",
        r"natural\s+wines?", r"sommelier",
        r"cava\s+con\s+(?:buenos?|excelentes?)\s+vinos?",
    ]),
    ("💎 Un rapport qualité-prix imbattable", [
        r"rapport\s+qualit[ée][/\s-]+prix\s+(?:imbattable|excellent|top|exceptionnel|incroyable|au\s+top|g[ée]nial)",
        r"prix\s+(?:tr[èe]s\s+)?(?:raisonnables?|corrects?|accessibles?|doux)",
        r"(?:c'?est|qui\s+est)\s+(?:vraiment\s+)?(?:donn[ée]|pas\s+cher)",
        r"excellent\s+value", r"great\s+value\s+for\s+money", r"worth\s+every\s+(?:penny|euro)",
        r"precio\s+(?:justo|razonable|muy\s+bueno)", r"muy\s+asequible",
        r"generous\s+portion", r"portions?\s+g[ée]n[ée]reuses?",
    ]),
    ("🎉 Une ambiance qui rend la soirée magique", [
        r"ambiance\s+(?:magique|incroyable|top|chaleureuse?|festive|conviviale|unique|au\s+top|g[ée]niale|extraordinaire|feutr[ée]e?|sympa|cosy|cozy)",
        r"atmosph[èe]re\s+(?:magique|unique|chaleureuse?|feutr[ée]e?|cosy|cozy)",
        r"(?:tr[èe]s\s+)?(?:cosy|cozy)", r"endroit\s+(?:magique|unique|charmant|cosy)",
        r"soir[ée]e\s+(?:magique|inoubliable|parfaite)",
        r"cozy\s+(?:atmosphere|spot|place)", r"lovely\s+atmosphere",
        r"ambiente\s+(?:acogedor|encantador|m[aá]gico|especial)",
        r"cadre\s+(?:magnifique|splendide|exceptionnel|enchanteur|charmant|unique)",
    ]),
    ("🏡 Une cuisine locale qui raconte le terroir", [
        r"cuisine\s+(?:locale|du\s+march[ée]|du\s+terroir|r[ée]gionale|traditionnelle|typique)",
        r"recettes?\s+(?:traditionnelles?|du\s+terroir|de\s+grand[- ]?m[èe]re)",
        r"sp[ée]cialit[ée]s?\s+(?:locales?|r[ée]gionales?|du\s+coin)",
        r"produits?\s+du\s+terroir", r"authentic\s+(?:local|traditional)\s+(?:cuisine|food)",
        r"cocina\s+(?:tradicional|local|catalana|valenciana|mediterr[aá]nea)",
        r"niçoise", r"proven[çc]ale", r"mediterran[ée]enne?",
    ]),
    ("✨ Un moment d'exception à vivre absolument", [
        r"meilleur\s+(?:restaurant|repas|d[îi]ner|exp[ée]rience)",
        r"l[’']?un\s+des?\s+meilleurs?", r"(?:un\s+des\s+)?meilleurs?\s+de\s+(?:la\s+ville|nice|antibes|paris|marseille)",
        r"tout\s+[ée]tait\s+parfait", r"exp[ée]rience\s+(?:parfaite|5\s*[ée]toiles|exceptionnelle)",
        r"best\s+(?:restaurant|meal|dinner|experience)", r"a\s+must", r"must[- ]try",
        r"perfect\s+experience", r"highly\s+recommend",
        r"muy\s+recomendable", r"imprescindible", r"altamente\s+recomendable",
        r"on\s+reviendra", r"we['’]ll\s+be\s+back", r"can['’]t\s+wait\s+to\s+(?:go\s+)?back",
    ]),
    ("💕 L'endroit parfait pour un dîner à deux", [
        r"romantique", r"d[îi]ner\s+(?:aux\s+chandelles|en\s+amoureux)",
        r"pour\s+(?:un\s+)?(?:d[îi]ner\s+)?en\s+amoureux", r"tête[- ]à[- ]tête",
        r"romantic", r"candle\s*lit", r"date\s+night",
    ]),
    ("🍝 Des pâtes maison à tomber", [
        r"p[âa]tes?\s+(?:maison|fra[îi]ches?|fait(?:es)?\s+maison|artisanales?)",
        r"(?:fresh|homemade|house[- ]?made)\s+pasta", r"pasta\s+(?:is\s+)?(?:amazing|incredible|fantastic)",
        r"gnocchi\s+(?:maison|fait\s+maison)", r"ravioli\s+(?:maison|fait\s+maison)",
        r"pasta\s+fresca", r"pasta\s+artigianale", r"pasta\s+hecha\s+a\s+mano",
    ]),
    ("🔥 Des petits plats à partager qu'on s'arrache", [
        r"(?:assiettes?|plats?|tapas)\s+(?:[àa]\s+partager|de\s+partage)",
        r"small\s+plates?", r"sharing\s+plates?", r"(?:raciones?|tapas)\s+para\s+compartir",
        r"(?:on\s+picore|[àa]\s+grignoter|petits?\s+plats?\s+[àa]\s+grignoter)",
    ]),
]


def normalize(text: str) -> str:
    return text.lower() if text else ""


def score_vibes(reviews: list) -> list:
    """Retourne les vibes pertinentes (max 3) en les rankant par score."""
    if not reviews:
        return []
    corpus = " ".join(normalize(r) for r in reviews)
    scores = []
    for label, patterns in VIBES:
        count = 0
        for p in patterns:
            count += len(re.findall(p, corpus))
        if count >= 1:
            scores.append((label, count))
    scores.sort(key=lambda x: -x[1])
    return [lbl for lbl, _ in scores[:3]]


def process_file(path: Path) -> int:
    with open(path) as f:
        data = json.load(f)

    updated = 0
    for r in data:
        if r.get("source_type") not in ("trending", "both"):
            continue

        texts = []
        for q in r.get("top_recent_quotes", []) or []:
            if isinstance(q, dict):
                txt = q.get("text", "")
            else:
                txt = q
            if txt:
                texts.append(txt)

        # Ajouter top_dishes et top_qualities au corpus pour enrichir les signaux
        for d in r.get("top_dishes", []) or []:
            texts.append(str(d))
        for q in r.get("top_qualities", []) or []:
            texts.append(str(q))

        vibes = score_vibes(texts)
        if vibes:
            r["vibes"] = vibes
            updated += 1
        elif "vibes" in r:
            # On garde éventuellement les anciennes vibes si pas de nouveau match
            pass

    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return updated


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            n = process_file(p)
            print(f"{p.name}: {n} restos enrichis avec des vibes")
