"""
Enrichit les restos 'chef' sans photo en requêtant Google Maps via Apify.

Usage:
    python3 src/enrich_chef_photos.py [LIMIT]
    python3 src/enrich_chef_photos.py 50       # Top 50 (test)
    python3 src/enrich_chef_photos.py 300      # Top 300 restos
    python3 src/enrich_chef_photos.py all      # Tous les 921 restos

Coût estimé (actor compass/crawler-google-places):
    - ~$0.20 fixe par run
    - ~$0.005 par place retournée
    - Batch de 100 queries/run pour amortir

    50 restos  ≈ $0.75  (1 run)
    300 restos ≈ $2     (3 runs)
    all (~920) ≈ $6     (10 runs)

Priorité: les restos avec le plus de recos chefs passent en premier.
"""
import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

TOKEN = os.getenv("APIFY_API_TOKEN")
if not TOKEN:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("APIFY_API_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip().strip('"')
                break

client = ApifyClient(TOKEN)

ROOT = Path(__file__).resolve().parent.parent
DATA_PATHS = [ROOT / "dashboard" / "data.json", ROOT / "data" / "restaurants.json"]
BATCH_SIZE = 100  # requêtes par run Apify


def normalize_key(name: str, city: str) -> str:
    s = (name + " " + city).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def pick_candidates(limit):
    """Retourne les restos chef sans photo, rankés par priorité (recos desc)."""
    with open(DATA_PATHS[0]) as f:
        data = json.load(f)
    chef_no_photo = [
        r for r in data
        if r.get("source_type") == "chef" and not r.get("photo_url")
    ]
    chef_no_photo.sort(
        key=lambda r: (
            -(r.get("recommendation_count") or 0),
            -(r.get("confidence_score") or 0),
        )
    )
    if isinstance(limit, int):
        chef_no_photo = chef_no_photo[:limit]
    return chef_no_photo


def scrape_photos(candidates):
    """Pour chaque candidat, exécute une recherche Google Maps et retourne un dict name+city → fields."""
    enriched = {}
    total_cost = 0.0

    for batch_start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[batch_start:batch_start + BATCH_SIZE]
        queries = []
        query_to_key = {}
        for r in batch:
            q = f"{r['name']}, {r.get('address', '')}, {r.get('city', '')}"
            q = re.sub(r"\s+", " ", q).strip(", ")
            queries.append(q)
            query_to_key[q] = normalize_key(r["name"], r.get("city", ""))

        print(f"\n[Run {batch_start // BATCH_SIZE + 1}] Scraping {len(queries)} restos...")
        run = client.actor("compass/crawler-google-places").call(
            run_input={
                "searchStringsArray": queries,
                "maxCrawledPlacesPerSearch": 1,
                "language": "fr",
                "countryCode": "fr",
                "includeWebResults": False,
            },
            timeout_secs=600,
        )
        cost = run.get("usageTotalUsd", 0) or 0
        total_cost += cost
        n_matched = 0
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            name = item.get("title", "")
            addr = item.get("address", "") or ""
            city_match = None
            # Essayer de matcher via la searchString retournée
            ss = (item.get("searchString") or item.get("searchQuery") or "").strip()
            key = query_to_key.get(ss)
            if not key:
                # Fallback: match par nom approximatif
                for q, k in query_to_key.items():
                    if name and name.lower() in q.lower():
                        key = k
                        break
            if not key:
                continue
            n_matched += 1
            enriched[key] = {
                "photo_url": item.get("imageUrl", "") or "",
                "google_maps_url": item.get("url", "") or "",
                "rating": item.get("totalScore") or 0,
                "reviews_count": item.get("reviewsCount") or 0,
                "phone": item.get("phone", "") or "",
                "coordinates": {
                    "lat": (item.get("location") or {}).get("lat"),
                    "lng": (item.get("location") or {}).get("lng"),
                },
            }
        print(f"  → {n_matched} matches, coût ${cost:.3f}")

    print(f"\n💰 Coût total: ${total_cost:.3f}")
    return enriched, total_cost


def apply_enrichment(enriched):
    """Merge les données enrichies dans data.json + restaurants.json."""
    total_updated = 0
    for path in DATA_PATHS:
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        updated = 0
        for r in data:
            if r.get("source_type") != "chef":
                continue
            key = normalize_key(r["name"], r.get("city", ""))
            if key not in enriched:
                continue
            e = enriched[key]
            if e.get("photo_url") and not r.get("photo_url"):
                r["photo_url"] = e["photo_url"]
                updated += 1
            if e.get("google_maps_url") and not r.get("google_maps_url"):
                r["google_maps_url"] = e["google_maps_url"]
            if e.get("rating") and not r.get("rating"):
                r["rating"] = e["rating"]
            if e.get("reviews_count") and not r.get("reviews_count"):
                r["reviews_count"] = e["reviews_count"]
            if e.get("phone") and not r.get("phone"):
                r["phone"] = e["phone"]
            # Corrige coords uniquement si actuellement null
            if e["coordinates"].get("lat") and (not r.get("coordinates") or not r["coordinates"].get("lat")):
                r["coordinates"] = e["coordinates"]
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  {path.name}: {updated} restos enrichis avec photo")
        total_updated = max(total_updated, updated)
    return total_updated


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "50"
    limit = None if arg == "all" else int(arg)

    candidates = pick_candidates(limit)
    print(f"📸 {len(candidates)} restos chef sans photo à enrichir")
    print(f"   Top recos: " + ", ".join(f"{r['name']}({r.get('recommendation_count',1)})" for r in candidates[:5]))

    est_runs = (len(candidates) + BATCH_SIZE - 1) // BATCH_SIZE
    est_cost = est_runs * 0.20 + len(candidates) * 0.007
    print(f"   Coût estimé: ~${est_cost:.2f} ({est_runs} runs)")
    print()

    if not TOKEN:
        print("❌ APIFY_API_TOKEN introuvable dans .env")
        sys.exit(1)

    enriched, cost = scrape_photos(candidates)
    apply_enrichment(enriched)
    print(f"\n✅ Enrichissement terminé (${cost:.3f})")
