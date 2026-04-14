"""
Reprise du run Apify hôtels déjà exécuté (pour éviter de re-scraper les places).
Lit le dataset, applique le filtre corrigé, lance reviews + rule v3, merge.
"""
import os
import sys
from collections import defaultdict
from apify_client import ApifyClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apify_trending_hotels import (
    HOTEL_CATEGORIES, in_bbox, prefilter, scrape_reviews,
    apply_rule_v3, merge_into_data, load_cache, save_cache,
)

TOKEN = os.getenv("APIFY_API_TOKEN")
if not TOKEN:
    for line in open(".env"):
        if line.startswith("APIFY_API_TOKEN="):
            TOKEN = line.split("=", 1)[1].strip(); break
client = ApifyClient(TOKEN)

RUN_ID = "spv9ZfhC2yUPE9fHT"  # le run places hôtels déjà exécuté
CITIES = ["Nice", "Antibes", "Cannes"]


def extract_places_from_run(run_id):
    run_info = client.run(run_id).get()
    items = list(client.dataset(run_info["defaultDatasetId"]).iterate_items())
    print(f"  {len(items)} places dans le run")

    by_city = {c: [] for c in CITIES}
    seen = set()
    for item in items:
        pid = item.get("placeId", "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        if item.get("permanentlyClosed") or item.get("temporarilyClosed"):
            continue
        cat = (item.get("categoryName") or "").lower()
        if not any(k in cat for k in HOTEL_CATEGORIES):
            continue
        ss = (item.get("searchString") or "").lower()
        addr = (item.get("address") or "").lower()
        city_match = None
        for c in CITIES:
            if c.lower() in ss or c.lower() in addr:
                city_match = c
                break
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
    return by_city


if __name__ == "__main__":
    print("=== REPRISE RUN HÔTELS ===")
    by_city = extract_places_from_run(RUN_ID)
    cache = load_cache()
    existing_ids = set(cache.get("places", {}).keys())

    all_candidates = []
    for city, places in by_city.items():
        c = prefilter(places, existing_ids, city, max_candidates=15)
        all_candidates.extend([(city, p) for p in c])
        print(f"  {city}: {len(c)} candidats sur {len(places)} hôtels")

    if not all_candidates:
        print("Rien à traiter.")
        sys.exit(0)

    from datetime import datetime
    # Pass 3 : reviews (coût Apify)
    print(f"\n🚀 Reviews pour {len(all_candidates)} hôtels...")
    all_pids = [c[1]["placeId"] for c in all_candidates]
    reviews, cost = scrape_reviews(all_pids)
    print(f"  Coût reviews: ${cost:.3f}")

    by_pid = defaultdict(list)
    for rev in reviews:
        by_pid[rev.get("placeId", "")].append(rev)
    for pid in by_pid:
        by_pid[pid].sort(key=lambda r: r.get("publishedAtDate", "") or "", reverse=True)

    # Pass 4 : règle v3
    validated = []
    for city, candidate in all_candidates:
        recs = by_pid.get(candidate["placeId"], [])
        ok, info = apply_rule_v3(candidate, recs)
        if not ok:
            print(f"    ❌ {candidate['name']}: {info}")
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
        print(f"    ✅ {candidate['name']} ({city}) — {candidate['rating']}★ {candidate['reviews_count']} avis")

    for city, candidate in all_candidates:
        cache.setdefault("places", {})[candidate["placeId"]] = {
            "scraped_at": datetime.now().isoformat(), "city": city
        }
    save_cache(cache)

    added = merge_into_data(validated)
    print(f"\n✅ {added} hôtels ajoutés à data.json (coût: ${cost:.3f})")
