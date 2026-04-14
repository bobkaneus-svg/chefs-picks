#!/usr/bin/env python3
"""
Apify Trending Scraper — Hôtels (même règle v3 que les restos).

Usage:
  python3 src/apify_trending_hotels.py "Nice,Antibes,Cannes"
  python3 src/apify_trending_hotels.py --estimate-only "Nice"

Règle v3 adaptée hôtels :
- rating ≥ 4.5
- reviews ≥ 100 (seuil + haut pour hôtels vs 50 pour restos)
- Catégories: hotel, boutique hotel, guest house, resort, inn
- 60% des 15 derniers avis en 5★
- Dernières 3 reviews ≥ 4★
- Pas 2 négatifs consécutifs non corrigés
"""
import json
import os
import re
import sys
from datetime import datetime
from collections import defaultdict
from apify_client import ApifyClient

TOKEN = os.getenv("APIFY_API_TOKEN")
if not TOKEN:
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith("APIFY_API_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip()
                break
if not TOKEN:
    print("ERROR: APIFY_API_TOKEN absent")
    sys.exit(1)
client = ApifyClient(TOKEN)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "dashboard/data.json")
CACHE_FILE = os.path.join(ROOT, "data/raw/cache_placeids_hotels.json")

CITY_BBOX = {
    "nice": {"lat": (43.6, 43.8), "lng": (7.18, 7.35)},
    "antibes": {"lat": (43.55, 43.65), "lng": (7.10, 7.20)},
    "cannes": {"lat": (43.5, 43.6), "lng": (6.95, 7.10)},
    "monaco": {"lat": (43.7, 43.78), "lng": (7.4, 7.5)},
    "paris": {"lat": (48.7, 49.0), "lng": (2.2, 2.5)},
    "marseille": {"lat": (43.18, 43.40), "lng": (5.20, 5.55)},
}

HOTEL_CATEGORIES = [
    # FR
    "hôtel", "hotel", "résidence hôtelière", "residence hoteliere",
    "complexe hôtelier", "complexe hotelier", "hôtel bien-être",
    "auberge", "chambre d'hôtes", "village de vacances",
    # EN
    "boutique hotel", "luxury hotel", "guest house", "inn",
    "bed & breakfast", "b&b", "resort", "lodging", "suite", "aparthotel",
    "hostel",
]


def in_bbox(lat, lng, city):
    if lat is None or lng is None:
        return False
    bbox = CITY_BBOX.get(city.lower())
    if not bbox:
        return True
    return bbox["lat"][0] <= lat <= bbox["lat"][1] and bbox["lng"][0] <= lng <= bbox["lng"][1]


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE))
        except:
            pass
    return {"places": {}}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    json.dump(cache, open(CACHE_FILE, "w"), indent=2)


# ─────────────────────────────────────────
# PASS 1 : Places hôtels en batch
# ─────────────────────────────────────────
def scrape_hotels_batch(cities, max_per_city=60):
    """1 run Apify pour plusieurs villes → économise les frais fixes."""
    print(f"  [Pass 1] Scraping hôtels de {len(cities)} ville(s) en 1 run...")
    search_strings = [f"hotels {c}, France" for c in cities]
    run = client.actor("compass/crawler-google-places").call(
        run_input={
            "searchStringsArray": search_strings,
            "maxCrawledPlacesPerSearch": max_per_city,
            "language": "fr",
            "countryCode": "fr",
            "includeWebResults": False,
        },
        timeout_secs=600,
    )
    cost = run.get("usageTotalUsd", 0) or 0
    by_city = {c: [] for c in cities}
    seen = set()
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        pid = item.get("placeId", "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        if item.get("permanentlyClosed") or item.get("temporarilyClosed"):
            continue
        cat = (item.get("categoryName") or "").lower()
        if not any(k in cat for k in HOTEL_CATEGORIES):
            continue
        # Détermine la ville via searchString
        ss = (item.get("searchString") or "").lower()
        city_match = next((c for c in cities if c.lower() in ss), None)
        if not city_match:
            addr = (item.get("address") or "").lower()
            city_match = next((c for c in cities if c.lower() in addr), None)
        if not city_match:
            continue
        by_city[city_match].append({
            "name": item.get("title", ""),
            "address": item.get("address", ""),
            "rating": item.get("totalScore") or 0,
            "reviews_count": item.get("reviewsCount") or 0,
            "lat": (item.get("location") or {}).get("lat"),
            "lng": (item.get("location") or {}).get("lng"),
            "placeId": pid,
            "url": item.get("url", ""),
            "categoryName": item.get("categoryName", ""),
            "price_level": item.get("price", ""),
            "photo_url": item.get("imageUrl", ""),
            "phone": item.get("phone", ""),
            "website": item.get("website", ""),
        })
    total = sum(len(v) for v in by_city.values())
    print(f"    → {total} hôtels trouvés, coût ${cost:.3f}")
    return by_city, cost


# ─────────────────────────────────────────
# PASS 2 : Pre-filter
# ─────────────────────────────────────────
def prefilter(places, existing_ids, city, max_candidates=15):
    rejected_geo = 0
    candidates = []
    for p in places:
        if p["rating"] < 4.5 or p["reviews_count"] < 100:
            continue
        if p["placeId"] in existing_ids:
            continue
        if not in_bbox(p.get("lat"), p.get("lng"), city):
            rejected_geo += 1
            continue
        candidates.append(p)
    if rejected_geo:
        print(f"    ⚠️  {rejected_geo} candidats hors bbox {city}")
    candidates.sort(key=lambda p: (p["rating"], p["reviews_count"]), reverse=True)
    return candidates[:max_candidates]


# ─────────────────────────────────────────
# PASS 3 : Reviews
# ─────────────────────────────────────────
def scrape_reviews(place_ids, max_reviews_per_place=15):
    if not place_ids:
        return [], 0
    print(f"  [Pass 3] Scraping {max_reviews_per_place} avis × {len(place_ids)} hôtels...")
    run = client.actor("compass/google-maps-reviews-scraper").call(
        run_input={
            "placeIds": place_ids,
            "maxReviews": max_reviews_per_place,
            "reviewsSort": "newest",
            "language": "fr",
        },
        timeout_secs=600,
    )
    cost = run.get("usageTotalUsd", 0) or 0
    reviews = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"    → {len(reviews)} avis, coût ${cost:.3f}")
    return reviews, cost


# ─────────────────────────────────────────
# PASS 4 : Règle v3 adaptée hôtels
# ─────────────────────────────────────────
def apply_rule_v3(candidate, recent_reviews):
    if len(recent_reviews) < 10:
        return False, "moins de 10 avis"
    last15 = recent_reviews[:15]
    stars = [r.get("stars") or 0 for r in last15]
    n_5stars = sum(1 for s in stars if s == 5)
    if n_5stars / len(stars) < 0.55:  # 55% pour hôtels (vs 60% pour restos)
        return False, f"{n_5stars}/{len(stars)} en 5★ seulement"
    last3 = stars[:3]
    if any(s < 4 for s in last3):
        return False, "dernières 3 reviews contiennent du <4★"
    # Pas 2 négatifs consécutifs (<4★) dans les 10 derniers
    prev = None
    for s in stars[:10]:
        if s and s < 4 and prev and prev < 4:
            return False, "2 négatifs consécutifs"
        prev = s
    return True, {"n_5stars": n_5stars, "total": len(last15)}


# ─────────────────────────────────────────
# Merge dans data.json
# ─────────────────────────────────────────
def merge_into_data(validated):
    if not validated:
        return 0
    d = json.load(open(DATA_FILE))
    existing_ids = {r["id"] for r in d}
    existing_keys = {(r["name"].lower().strip(), r.get("city", "").lower().strip()) for r in d}

    def make_id(n, c):
        s = re.sub(r"[^a-z0-9]+", "-", n.lower().strip()).strip("-")
        cc = re.sub(r"[^a-z0-9]+", "-", c.lower().strip()).strip("-")
        return "hotel-" + s + "-" + cc

    price_map = {"Inexpensive": "€", "Moderate": "€€", "Expensive": "€€€", "Very Expensive": "€€€€"}
    added = 0
    for p in validated:
        city = p["_city"]
        rid = make_id(p["name"], city)
        key = (p["name"].lower().strip(), city.lower().strip())
        if rid in existing_ids or key in existing_keys:
            continue
        d.append({
            "id": rid,
            "entity_type": "hotel",
            "name": p["name"],
            "address": p["address"],
            "city": city,
            "country": "France",
            "coordinates": {"lat": p.get("lat"), "lng": p.get("lng")},
            "cuisine_type": p.get("categoryName", "Hôtel"),
            "price_range": price_map.get(p.get("price_level", ""), "€€€"),
            "vibe": "hotel",
            "tags": [],
            "recommendations": [],
            "recommendation_count": 0,
            "confidence_score": int(p["rating"] * 20),
            "last_updated": datetime.now().isoformat()[:10],
            "source_type": "trending",
            "google_rating": p["rating"],
            "reviews_count_google": p["reviews_count"],
            "google_maps_url": p.get("url", ""),
            "photo_url": p.get("photo_url", ""),
            "phone": p.get("phone", ""),
            "website": p.get("website", ""),
            "top_recent_quotes": p["_top_quotes"],
        })
        added += 1

    json.dump(d, open(DATA_FILE, "w"), ensure_ascii=False, indent=2)
    json.dump(d, open(os.path.join(ROOT, "data/restaurants.json"), "w"), ensure_ascii=False, indent=2)
    return added


def estimate_cost(cities):
    n = len(cities)
    # Places batch : 1 run fixe + ~60 places × $0.007/place
    places_cost = 0.20 + n * 60 * 0.007
    # Reviews batch : 1 run + ~15 places × 15 avis
    reviews_cost = 0.20 + n * 15 * 15 * 0.001
    total = places_cost + reviews_cost
    print(f"💰 Estimation pour {n} ville(s) : ~${total:.2f}")
    print(f"   (Places: ~${places_cost:.2f} | Reviews: ~${reviews_cost:.2f})")
    return total


# ─────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    estimate_only = "--estimate-only" in args
    cities_arg = [a for a in args if not a.startswith("--")][0] if args else "Nice,Antibes,Cannes"
    cities = [c.strip() for c in cities_arg.split(",")]

    print("=" * 60)
    print("  APIFY TRENDING SCRAPER — HÔTELS")
    print("=" * 60)
    estimate_cost(cities)

    if estimate_only:
        print("\n[--estimate-only] Pas de scraping lancé.")
        sys.exit(0)

    cache = load_cache()
    total_cost = {"places": 0, "reviews": 0}

    # Pass 1
    print(f"\n🚀 PASS 1 : Places hôtels")
    by_city, cost1 = scrape_hotels_batch(cities, max_per_city=60)
    total_cost["places"] += cost1

    # Pass 2 : pre-filter
    existing_ids = set(cache.get("places", {}).keys())
    all_candidates = []
    print(f"\n🚀 PASS 2 : Pre-filter (rating ≥4.5, reviews ≥100, coords valides)")
    for city, places in by_city.items():
        c = prefilter(places, existing_ids, city, max_candidates=15)
        all_candidates.extend([(city, p) for p in c])
        print(f"    {city}: {len(c)} candidats sur {len(places)} hôtels")

    if not all_candidates:
        print("\n  ⚠️  Aucun candidat éligible.")
        sys.exit(0)

    # Pass 3 : reviews
    print(f"\n🚀 PASS 3 : Reviews ({len(all_candidates)} hôtels × 15 avis)")
    all_pids = [c[1]["placeId"] for c in all_candidates]
    reviews, cost2 = scrape_reviews(all_pids)
    total_cost["reviews"] += cost2

    by_pid = defaultdict(list)
    for rev in reviews:
        by_pid[rev.get("placeId", "")].append(rev)
    for pid in by_pid:
        by_pid[pid].sort(key=lambda r: r.get("publishedAtDate", "") or "", reverse=True)

    # Pass 4 : règle v3
    print(f"\n🚀 PASS 4 : Règle v3")
    validated = []
    for city, candidate in all_candidates:
        recs = by_pid.get(candidate["placeId"], [])
        ok, info = apply_rule_v3(candidate, recs)
        if not ok:
            print(f"    ❌ {candidate['name']} ({city}): {info}")
            continue
        top_quotes = sorted(
            [r for r in recs[:15] if (r.get("stars") or 0) == 5 and r.get("text")],
            key=lambda r: len(r.get("text", "")), reverse=True
        )[:5]
        candidate["_top_quotes"] = [
            {"date": (q.get("publishedAtDate", "") or "")[:10], "stars": q.get("stars"),
             "text": (q.get("text") or "")[:250], "author": q.get("name", "")}
            for q in top_quotes
        ]
        candidate["_city"] = city
        validated.append(candidate)
        print(f"    ✅ {candidate['name']} ({city})")

    # Merge
    for city, candidate in all_candidates:
        cache.setdefault("places", {})[candidate["placeId"]] = {
            "scraped_at": datetime.now().isoformat(), "city": city
        }
    save_cache(cache)

    added = merge_into_data(validated)
    total = total_cost["places"] + total_cost["reviews"]
    print("\n" + "=" * 60)
    print(f"📊 RAPPORT FINAL")
    print(f"  Hôtels validés: {len(validated)}")
    print(f"  Ajoutés à data.json: {added}")
    print(f"  Coût total: ${total:.3f}")
    if added:
        print(f"  Coût/hôtel ajouté: ${total/added:.3f}")
