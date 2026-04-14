"""
Applique un score éditorial à chaque resto/hôtel trending, gère le cap par ville
(15 restos max + 5 hôtels max), tag les ajouts récents avec freshness_badge='new'
et stampe selection_month + added_at.

Règle : les items visibles dans l'UI doivent tous passer un hard gate de qualité :
- signature_phrase présent
- signature_dishes (≥1)
- review_photos (≥3 idéalement, mais soft si absent)

Champ ajouté : `in_selection` (bool) → l'UI filtre là-dessus au rendu.
"""
import json
import math
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]

CAP_RESTO = 15  # restos trending max par ville
CAP_HOTEL = 5   # hôtels max par ville
TODAY = datetime.now()
FRESHNESS_DAYS = 30


def is_eligible(r: dict) -> tuple:
    """Gate de qualité éditoriale. Un item passe s'il a au moins DEUX des signaux suivants :
    - signature_phrase (phrase éditoriale extraite)
    - signature_dishes (≥1 plat spécifique identifié)
    - review_photos (≥3 photos de qualité)
    - top_recent_quotes avec ≥3 5★ récentes (prouve la qualité soutenue)
    - editorial_pitch non vide (au minimum, la fiche a un narratif structuré)

    Pour les hôtels, le gate est plus souple (pas de plats à extraire).
    """
    is_hotel = r.get("entity_type") == "hotel"

    signals = 0
    if r.get("signature_phrase"):
        signals += 1
    if r.get("signature_dishes"):
        signals += 1
    if len(r.get("review_photos") or []) >= 3:
        signals += 1
    five_stars = sum(1 for q in (r.get("top_recent_quotes") or []) if (q.get("stars") or 0) == 5)
    if five_stars >= 3:
        signals += 1

    # Hôtels : 1 signal suffit (pas de dishes attendus, photos pas scrapées systématiquement)
    # Restos : 2 signaux minimum (photo + phrase, ou phrase + dishes, etc.)
    threshold = 1 if is_hotel else 2
    if signals >= threshold:
        return True, "ok"
    return False, f"only_{signals}_signals"


def editorial_score(r: dict) -> float:
    """
    Score = rating × log10(reviews) × freshness_bonus × photo_bonus × content_bonus
    """
    rating = r.get("google_rating") or 0
    reviews = r.get("reviews_count_google") or r.get("reviews_count") or 1
    score = rating * math.log10(max(reviews, 10))

    # Freshness bonus si dernière 5★ récente (<30j)
    freshness_bonus = 1.0
    quotes = r.get("top_recent_quotes") or []
    recent_5 = [q for q in quotes if (q.get("stars") or 0) == 5 and q.get("date")]
    if recent_5:
        try:
            latest = max(datetime.fromisoformat(q["date"]) for q in recent_5)
            days = (TODAY - latest).days
            if days <= 30:
                freshness_bonus = 1.15
            elif days <= 90:
                freshness_bonus = 1.05
        except Exception:
            pass

    # Photo bonus
    photos = r.get("review_photos") or []
    photo_bonus = 1.0 + min(len(photos), 6) * 0.02  # +2% par photo jusqu'à 6

    # Content richness bonus
    content_bonus = 1.0
    if r.get("signature_phrase"):
        content_bonus += 0.05
    if (r.get("signature_dishes") or []) and len(r["signature_dishes"]) >= 2:
        content_bonus += 0.05
    if r.get("first_visit", {}).get("tips"):
        content_bonus += 0.03
    if r.get("occasion_tags"):
        content_bonus += 0.02

    return score * freshness_bonus * photo_bonus * content_bonus


def process(path: Path):
    with open(path) as f:
        data = json.load(f)

    # Étape 1 : identifie les trending + hôtels candidats
    candidates = []
    for r in data:
        if r.get("source_type") not in ("trending", "both") and r.get("entity_type") != "hotel":
            # Non candidat : reset in_selection
            if "in_selection" in r:
                r["in_selection"] = False
            continue
        candidates.append(r)

    # Étape 2 : évalue éligibilité + score
    now_iso = TODAY.strftime("%Y-%m-%d")
    month_iso = TODAY.strftime("%Y-%m")
    for r in candidates:
        eligible, reason = is_eligible(r)
        r["_eligible"] = eligible
        r["_reject_reason"] = reason
        if eligible:
            r["editorial_score"] = round(editorial_score(r), 3)
        else:
            r["editorial_score"] = 0

    # Étape 3 : applique le cap par ville + type
    by_city_type = defaultdict(list)
    for r in candidates:
        if not r["_eligible"]:
            continue
        city = (r.get("city") or "").strip()
        kind = "hotel" if r.get("entity_type") == "hotel" else "restaurant"
        by_city_type[(city, kind)].append(r)

    selected_ids = set()
    for (city, kind), items in by_city_type.items():
        items.sort(key=lambda x: -x["editorial_score"])
        cap = CAP_HOTEL if kind == "hotel" else CAP_RESTO
        for item in items[:cap]:
            selected_ids.add(item["id"])

    # Étape 4 : stamp selection_month + added_at (si pas déjà)
    # + freshness_badge si added_at récent (<30j)
    for r in candidates:
        if r["id"] in selected_ids:
            r["in_selection"] = True
            # Ne pas écraser un added_at existant
            if not r.get("added_at"):
                r["added_at"] = now_iso
                r["selection_month"] = month_iso
            # Freshness badge
            try:
                added = datetime.fromisoformat(r["added_at"])
                if (TODAY - added).days <= FRESHNESS_DAYS:
                    r["freshness_badge"] = "new"
                elif r.get("freshness_badge") == "new":
                    # Vieilli : on retire le badge
                    del r["freshness_badge"]
            except Exception:
                pass
        else:
            r["in_selection"] = False

    # Cleanup des champs temporaires
    for r in candidates:
        r.pop("_eligible", None)
        r.pop("_reject_reason", None)

    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Stats
    in_sel_rest = sum(1 for r in candidates if r.get("in_selection") and r.get("entity_type") != "hotel")
    in_sel_hot = sum(1 for r in candidates if r.get("in_selection") and r.get("entity_type") == "hotel")
    rejected = sum(1 for r in candidates if not r.get("in_selection"))
    new_badge = sum(1 for r in candidates if r.get("freshness_badge") == "new")

    print(f"{path.name}:")
    print(f"  Restos candidats: {sum(1 for r in candidates if r.get('entity_type')!='hotel')}")
    print(f"    → in_selection: {in_sel_rest}")
    print(f"  Hôtels candidats: {sum(1 for r in candidates if r.get('entity_type')=='hotel')}")
    print(f"    → in_selection: {in_sel_hot}")
    print(f"  Rejetés (pas in_selection): {rejected}")
    print(f"  Avec badge NEW: {new_badge}")

    # Répartition par ville
    by_city_sel = defaultdict(lambda: {"r": 0, "h": 0})
    for r in candidates:
        if not r.get("in_selection"):
            continue
        city = r.get("city") or "?"
        if r.get("entity_type") == "hotel":
            by_city_sel[city]["h"] += 1
        else:
            by_city_sel[city]["r"] += 1
    print(f"\n  Par ville (sélectionnés):")
    for city in sorted(by_city_sel, key=lambda c: -by_city_sel[c]["r"]):
        n = by_city_sel[city]
        if n["r"] or n["h"]:
            print(f"    {city}: {n['r']} restos, {n['h']} hôtels")


if __name__ == "__main__":
    for p in DATA_PATHS:
        if p.exists():
            process(p)
