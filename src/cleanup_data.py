"""
Nettoyage des données:
1. Détecte les coordonnées aberrantes (hors France/Espagne/Italie/Monaco)
   - TRENDING outliers → suppression (résultats Apify bogus, mauvaise ville matchée)
   - CHEF outliers → coordonnées nullifiées (visibles dans recherche mais pas sur carte)
2. Détecte et fusionne les doublons par adresse normalisée
3. Corrections manuelles connues (La Flibuste, Le Cap → BABA)
"""
import json
import re
import unicodedata
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]

# Bbox approximative par pays — pour vérifier que les coords matchent le country déclaré
COUNTRY_BBOX = {
    "france": {"lat_min": 41.0, "lat_max": 51.5, "lng_min": -5.5, "lng_max": 10.0},
    "monaco": {"lat_min": 43.7, "lat_max": 43.78, "lng_min": 7.4, "lng_max": 7.5},
    "espagne": {"lat_min": 35.0, "lat_max": 44.0, "lng_min": -10.0, "lng_max": 5.0},
    "spain": {"lat_min": 35.0, "lat_max": 44.0, "lng_min": -10.0, "lng_max": 5.0},
    "italie": {"lat_min": 36.5, "lat_max": 47.5, "lng_min": 6.5, "lng_max": 19.0},
    "italy": {"lat_min": 36.5, "lat_max": 47.5, "lng_min": 6.5, "lng_max": 19.0},
    "portugal": {"lat_min": 36.5, "lat_max": 42.5, "lng_min": -10.0, "lng_max": -5.5},
    "royaume-uni": {"lat_min": 49.5, "lat_max": 61.0, "lng_min": -8.5, "lng_max": 2.5},
    "uk": {"lat_min": 49.5, "lat_max": 61.0, "lng_min": -8.5, "lng_max": 2.5},
    "belgique": {"lat_min": 49.5, "lat_max": 51.6, "lng_min": 2.5, "lng_max": 6.5},
    "suisse": {"lat_min": 45.7, "lat_max": 47.9, "lng_min": 5.8, "lng_max": 10.6},
}

# Corrections manuelles (id ou nom → coords)
MANUAL_COORDS = {
    "La Flibuste": {"lat": 43.6326, "lng": 7.1325},  # Marina Baie des Anges, Villeneuve-Loubet
}

# Merges manuels: from_name → into_name (les recos sont fusionnées)
MANUAL_MERGES = [
    ("Le Cap - Restaurant de plage", "BABA"),  # Hotel a rebrandé Le Cap → BABA
]


def is_outlier(coords: dict, country: str = "", address: str = "") -> bool:
    """
    Outlier = coords ne correspondent pas au pays déclaré.
    Si pays non listé dans COUNTRY_BBOX → on accepte (pas d'outlier détecté,
    on fait confiance au scraper).
    """
    if not coords:
        return False
    lat, lng = coords.get("lat"), coords.get("lng")
    if lat is None or lng is None:
        return False
    bbox = COUNTRY_BBOX.get((country or "").lower())
    if not bbox:
        return False  # Pas de référence pour ce pays → on accepte
    return not (bbox["lat_min"] <= lat <= bbox["lat_max"] and bbox["lng_min"] <= lng <= bbox["lng_max"])


def normalize_addr(addr: str) -> str:
    if not addr:
        return ""
    s = unicodedata.normalize("NFKD", addr.lower()).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Remove common words
    for w in ("rue", "avenue", "av ", "boulevard", "bd ", "place", "pl ", "chemin", "chem ", "cours", "cr "):
        s = s.replace(" " + w, " ").replace(w + " ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def merge_recos(target: dict, source: dict):
    """Fusionne les recommandations de source dans target (dedup par chef_name)."""
    existing_chefs = {c.get("chef_name") for c in target.get("recommendations", [])}
    for c in source.get("recommendations", []) or []:
        if c.get("chef_name") not in existing_chefs:
            target.setdefault("recommendations", []).append(c)
            existing_chefs.add(c.get("chef_name"))
    target["recommendation_count"] = len(target.get("recommendations", []))
    # Si l'un est trending et l'autre chef → both
    s_src = source.get("source_type")
    s_tgt = target.get("source_type")
    if {s_src, s_tgt} & {"chef", "both"} and {s_src, s_tgt} & {"trending", "both"}:
        target["source_type"] = "both"


def process(path: Path):
    with open(path) as f:
        data = json.load(f)

    n_total = len(data)

    # === 1. Corrections manuelles de coords ===
    n_manual = 0
    for r in data:
        if r["name"] in MANUAL_COORDS:
            r["coordinates"] = MANUAL_COORDS[r["name"]]
            n_manual += 1

    # === 2. Merges manuels ===
    n_merged = 0
    for from_name, into_name in MANUAL_MERGES:
        target = next((r for r in data if r["name"] == into_name), None)
        sources = [r for r in data if r["name"] == from_name]
        if target and sources:
            for src in sources:
                merge_recos(target, src)
                data.remove(src)
                n_merged += 1

    # === 3. Détection doublons par adresse normalisée ===
    by_addr = defaultdict(list)
    for r in data:
        key = normalize_addr(r.get("address", ""))
        if key and len(key) > 10:
            by_addr[key].append(r)
    n_dup = 0
    duplicates_to_remove = []
    for addr, restos in by_addr.items():
        if len(restos) <= 1:
            continue
        # Garder celui qui a le plus de recos (ou le plus d'avis si égalité)
        restos.sort(key=lambda r: (
            -(r.get("recommendation_count") or 0),
            -(r.get("reviews_count") or 0),
        ))
        keeper = restos[0]
        for dup in restos[1:]:
            merge_recos(keeper, dup)
            duplicates_to_remove.append(id(dup))
            n_dup += 1
            print(f"  Dup: '{dup['name']}' → '{keeper['name']}' (addr: {addr[:60]})")
    data = [r for r in data if id(r) not in duplicates_to_remove]

    # === 4. Nettoyage outliers ===
    n_outliers_removed = 0
    n_outliers_nullified = 0
    cleaned = []
    for r in data:
        if is_outlier(r.get("coordinates"), r.get("country", ""), r.get("address", "")):
            src = r.get("source_type")
            if src == "trending":
                # Trending bogus → supprimer
                n_outliers_removed += 1
                print(f"  Outlier removed: {r['name']} ({r.get('city')}) @ {r.get('address')[:60]}")
                continue
            else:
                # Chef → nullifier coords
                r["coordinates"] = {"lat": None, "lng": None}
                n_outliers_nullified += 1
                print(f"  Outlier nullified: {r['name']} ({r.get('city')})")
        cleaned.append(r)

    with open(path, "w") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"\n{path.name}:")
    print(f"  Total avant: {n_total}, après: {len(cleaned)}")
    print(f"  Coords manuelles: {n_manual}")
    print(f"  Merges manuels: {n_merged}")
    print(f"  Doublons fusionnés: {n_dup}")
    print(f"  Outliers trending supprimés: {n_outliers_removed}")
    print(f"  Outliers chef nullifiés: {n_outliers_nullified}")


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            print(f"\n=== {p.name} ===")
            process(p)
