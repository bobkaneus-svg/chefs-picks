"""
Traduit les contenus éditoriaux (reviews, signature_dishes, signature_phrase)
vers le français pour les items `in_selection`. Ajoute les champs *_fr à côté
des originaux (préserve l'original).

Utilise Google Translate via deep-translator (free, pas d'API key requise).
"""
import json
import time
from pathlib import Path
from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]

translator = GoogleTranslator(source="auto", target="fr")


def looks_french(text: str) -> bool:
    """Heuristique rapide : si le texte contient des mots/caractères typiquement français,
    on considère qu'il est déjà en FR (évite d'appeler Google pour rien)."""
    if not text or len(text) < 15:
        return True
    tl = text.lower()
    fr_markers = [" le ", " la ", " les ", " un ", " une ", " des ", " de ", " du ",
                  " avec ", " pour ", " est ", " très ", " nous ", " c'est ",
                  "ç", "très", "déjà", "déli", "mais", "pour"]
    score = sum(1 for m in fr_markers if m in tl)
    # Si 3+ marqueurs FR → probablement déjà en français
    return score >= 3


def translate_text(text: str, max_retries: int = 2) -> str:
    """Traduit en FR. Retourne '' si erreur ou si déjà en FR."""
    if not text or looks_french(text):
        return ""
    for attempt in range(max_retries):
        try:
            result = translator.translate(text)
            if result and result != text:
                return result
            return ""
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"  ⚠️ Translation failed: {str(e)[:80]}")
                return ""
    return ""


def process(path: Path):
    with open(path) as f:
        data = json.load(f)

    total_translated = 0
    total_skipped = 0

    items = [r for r in data if r.get("in_selection") is True]
    print(f"  {len(items)} items in_selection à traiter")

    for idx, r in enumerate(items):
        if idx > 0 and idx % 10 == 0:
            print(f"  Progression: {idx}/{len(items)}")

        # 1) top_recent_quotes
        for q in r.get("top_recent_quotes", []) or []:
            if not isinstance(q, dict):
                continue
            txt = q.get("text", "")
            if not txt or q.get("text_fr"):
                continue  # déjà traduit ou vide
            if looks_french(txt):
                total_skipped += 1
                continue
            translated = translate_text(txt)
            if translated:
                q["text_fr"] = translated
                total_translated += 1

        # 2) signature_dishes
        for d in r.get("signature_dishes", []) or []:
            if not isinstance(d, dict):
                continue
            phrase = d.get("phrase", "")
            if not phrase or d.get("phrase_fr"):
                continue
            if looks_french(phrase):
                total_skipped += 1
                continue
            translated = translate_text(phrase)
            if translated:
                d["phrase_fr"] = translated
                total_translated += 1

        # 3) signature_phrase
        sp = r.get("signature_phrase")
        if sp and not r.get("signature_phrase_fr") and not looks_french(sp):
            translated = translate_text(sp)
            if translated:
                r["signature_phrase_fr"] = translated
                total_translated += 1

    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  {path.name}:")
    print(f"    Traduits: {total_translated}")
    print(f"    Skipped (déjà FR): {total_skipped}")


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            print(f"\n=== {p.name} ===")
            process(p)
