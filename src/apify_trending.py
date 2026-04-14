#!/usr/bin/env python3
"""
Apify Trending Scraper — Optimized for low cost.

Stratégie 3-pass :
1. Places (1 query, 100 places, ~$0.10)
2. Pre-filter local (gratuit) → top 15 candidats max
3. Reviews (15 avis × top 15 places, ~$0.10)
→ Coût par ville : ~$0.20 (vs $0.50 avant)

Usage:
  python3 src/apify_trending.py "Nice"
  python3 src/apify_trending.py "Marseille,Lyon,Bordeaux"
  python3 src/apify_trending.py --estimate-only "Cannes"
"""
import json, os, re, sys, time
from datetime import datetime
from collections import defaultdict
from apify_client import ApifyClient

TOKEN = os.getenv("APIFY_API_TOKEN")
if not TOKEN:
    # Fallback: try .env file
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith("APIFY_API_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip()
                break
if not TOKEN:
    print("ERROR: Set APIFY_API_TOKEN env var or create .env file")
    sys.exit(1)
client = ApifyClient(TOKEN)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "dashboard/data.json")
CACHE_FILE = os.path.join(ROOT, "data/raw/cache_placeids.json")
RAW_DIR = os.path.join(ROOT, "data/raw")

# ─────────────────────────────────────────
# Cache pour éviter de re-scraper
# ─────────────────────────────────────────
def load_cache():
    if os.path.exists(CACHE_FILE):
        try: return json.load(open(CACHE_FILE))
        except: pass
    return {"places": {}, "reviews": {}}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    json.dump(cache, open(CACHE_FILE, "w"), indent=2)

def get_existing_place_ids():
    """Récupère les placeIds déjà dans data.json pour éviter doublons."""
    if not os.path.exists(DATA_FILE): return set()
    d = json.load(open(DATA_FILE))
    ids = set()
    for r in d:
        # Try to extract from google_maps_url
        url = r.get('google_maps_url', '')
        m = re.search(r'place_id=([\w-]+)', url)
        if m: ids.add(m.group(1))
        # Or from existing cached
    return ids

# ─────────────────────────────────────────
# PASS 1: Places — MULTIPLEX (1 run pour N villes)
# ─────────────────────────────────────────
# Bbox approximative par ville pour valider les coords (anti-bogus)
CITY_BBOX = {
    "paris": {"lat": (48.7, 49.0), "lng": (2.2, 2.5)},
    "nice": {"lat": (43.6, 43.8), "lng": (7.18, 7.35)},
    "monaco": {"lat": (43.7, 43.78), "lng": (7.4, 7.5)},
    "cannes": {"lat": (43.5, 43.6), "lng": (6.95, 7.10)},
    "antibes": {"lat": (43.55, 43.65), "lng": (7.10, 7.20)},
    "marseille": {"lat": (43.18, 43.40), "lng": (5.20, 5.55)},
    "lyon": {"lat": (45.70, 45.82), "lng": (4.78, 4.92)},
    "bordeaux": {"lat": (44.78, 44.92), "lng": (-0.65, -0.50)},
    "toulouse": {"lat": (43.55, 43.68), "lng": (1.38, 1.50)},
    "nantes": {"lat": (47.18, 47.28), "lng": (-1.62, -1.48)},
}


def in_bbox(lat, lng, city):
    """Valide que les coords sont bien dans la ville déclarée."""
    if lat is None or lng is None:
        return False
    bbox = CITY_BBOX.get(city.lower())
    if not bbox:
        return True  # Pas de référence → on accepte
    return bbox["lat"][0] <= lat <= bbox["lat"][1] and bbox["lng"][0] <= lng <= bbox["lng"][1]


def scrape_places_batch(cities, max_places_per_city=50):
    """Scrape plusieurs villes en 1 seul run pour économiser les frais fixes (~$0.20/run).
    Ajoute ', France' au search query pour éviter les matches sur Paris,TX / Monaco→Munich."""
    print(f"  [Pass 1 BATCH] Scraping {len(cities)} villes en 1 run...")
    # Toujours préciser le pays pour éviter les ambiguïtés Paris→TX, Monaco→Munich, etc.
    search_strings = []
    for c in cities:
        if "," not in c:
            search_strings.append(f"restaurants {c}, France")
        else:
            search_strings.append(f"restaurants {c}")
    run = client.actor("compass/crawler-google-places").call(
        run_input={
            "searchStringsArray": search_strings,
            "maxCrawledPlacesPerSearch": max_places_per_city,
            "language": "en",
            "includeWebResults": False,
        },
        timeout_secs=600,
    )
    cost = run.get("usageTotalUsd", 0) or 0
    by_city = {c: [] for c in cities}
    seen = set()
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        pid = item.get("placeId", "")
        if not pid or pid in seen: continue
        seen.add(pid)
        if item.get("permanentlyClosed") or item.get("temporarilyClosed"): continue
        cat = (item.get("categoryName") or "").lower()
        if not any(k in cat for k in ["restaurant","bistro","brasserie","trattoria","pizz","sushi","tapas","cafe","bakery","gastro"]):
            continue
        # Find which city this belongs to (from search query)
        search_term = (item.get("searchString") or item.get("searchQuery") or "").lower()
        city_match = None
        for c in cities:
            if c.lower() in search_term:
                city_match = c
                break
        if not city_match:
            # Fallback: use address
            addr = (item.get("address") or "").lower()
            for c in cities:
                if c.lower() in addr:
                    city_match = c
                    break
        if not city_match: city_match = cities[0]
        by_city[city_match].append({
            "name": item.get("title", ""),
            "address": item.get("address", ""),
            "rating": item.get("totalScore", 0) or 0,
            "reviews_count": item.get("reviewsCount", 0) or 0,
            "lat": (item.get("location") or {}).get("lat"),
            "lng": (item.get("location") or {}).get("lng"),
            "placeId": pid,
            "url": item.get("url", ""),
            "categoryName": item.get("categoryName", ""),
            "price_level": item.get("price", ""),
            "photo_url": item.get("imageUrl", ""),
        })
    total_places = sum(len(v) for v in by_city.values())
    print(f"    → {total_places} places (réparties sur {len([c for c in by_city if by_city[c]])} villes), coût: ${cost:.3f}")
    print(f"    → Coût/ville: ${cost/len(cities):.3f}")
    return by_city, cost

# Backward compat
def scrape_places(city, max_places=100):
    by_city, cost = scrape_places_batch([city], max_places_per_city=max_places)
    return by_city.get(city, []), cost

# ─────────────────────────────────────────
# PASS 2: Pre-filter local (gratuit)
# ─────────────────────────────────────────
def prefilter(places, existing_ids, max_candidates=15, city=None):
    """Garder uniquement les meilleurs candidats avec critères stricts.
    Si `city` est fourni, valide aussi que les coords sont dans la bbox de la ville
    (évite d'importer des restos US/Allemagne quand on cherche Paris/Monaco)."""
    rejected_geo = 0
    candidates = []
    for p in places:
        if not (p["rating"] >= 4.5 and p["reviews_count"] >= 50):
            continue
        if p["placeId"] in existing_ids:
            continue
        if city and not in_bbox(p.get("lat"), p.get("lng"), city):
            rejected_geo += 1
            continue
        candidates.append(p)
    if rejected_geo:
        print(f"    ⚠️  {rejected_geo} candidats rejetés (coords hors {city})")
    candidates.sort(key=lambda p: (p["rating"], p["reviews_count"]), reverse=True)
    return candidates[:max_candidates]

# ─────────────────────────────────────────
# PASS 3: Reviews ciblées
# ─────────────────────────────────────────
def scrape_reviews(place_ids, max_reviews_per_place=15):
    if not place_ids: return [], 0
    print(f"  [Pass 3] Scraping {max_reviews_per_place} reviews × {len(place_ids)} places...")
    run = client.actor("compass/google-maps-reviews-scraper").call(
        run_input={
            "placeIds": place_ids,
            "maxReviews": max_reviews_per_place,
            "reviewsSort": "newest",
            "language": "en",
            "personalData": True,
        },
        timeout_secs=600,
    )
    cost = run.get("usageTotalUsd", 0) or 0
    reviews = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"    → {len(reviews)} reviews, coût: ${cost:.3f}")
    return reviews, cost

# ─────────────────────────────────────────
# PASS 4: Règle v3 (gratuit, local)
# ─────────────────────────────────────────
TODAY = datetime.now()

def parse_date(s):
    try: return datetime.fromisoformat((s or "").replace("Z","+00:00"))
    except: return None

def analyze_season(recs):
    dates = [parse_date(r.get("publishedAtDate","")) for r in recs]
    dates = [d for d in dates if d]
    if not dates: return {"last_review_date":"","last_review_days_ago":None,"seasonal":False,"currently_open_season":False}
    last = dates[0]
    days_since = (TODAY - last.replace(tzinfo=None)).days
    months = set((d.year, d.month) for d in dates)
    winter = {(2025,11),(2025,12),(2026,1),(2026,2),(2026,3)}
    summer = {(2025,6),(2025,7),(2025,8),(2025,9)}
    return {
        "last_review_date": last.isoformat()[:10],
        "last_review_days_ago": days_since,
        "seasonal": any(m in months for m in summer) and not any(m in months for m in winter),
        "currently_open_season": days_since < 30,
    }

def apply_rule_v3(place, recs):
    """Règle trending v3 : 60% des 15 derniers = 5★, 3 derniers ≥ 4★, pas 2 négatifs consécutifs (sauf corrigés), saisonnalité."""
    if len(recs) < 15: return False, "<15 avis"
    if place["reviews_count"] < 30: return False, "<30 avis totaux"
    season = analyze_season(recs)
    last15, last3 = recs[:15], recs[:3]
    if not season["seasonal"] and (season["last_review_days_ago"] or 999) > 60:
        return False, f"Pas d'avis depuis {season['last_review_days_ago']}j"
    if not all((r.get("stars") or 0) >= 4 for r in last3):
        return False, "3 derniers pas tous ≥4★"
    stars = [(r.get("stars") or 0) for r in last15]
    five_stars = sum(1 for s in stars if s == 5)
    if five_stars < 9: return False, f"{five_stars}/15 en 5★"
    for i in range(len(stars)-1):
        if stars[i] < 4 and stars[i+1] < 4:
            positive_since = sum(1 for s in stars[:i] if s >= 4)
            if positive_since < 5: return False, "2 avis <4★ non corrigés"
    return True, season

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def process_city(city, cache, total_cost):
    print(f"\n🏙️  Processing: {city}")
    existing_ids = get_existing_place_ids() | set(cache.get("places", {}).keys())

    places, cost1 = scrape_places(city)
    total_cost["places"] += cost1

    candidates = prefilter(places, existing_ids, max_candidates=15, city=city)
    print(f"  [Pass 2] Pre-filter: {len(candidates)} candidats sur {len(places)} places (≥4.5★, ≥50 avis, non doublons)")

    if not candidates:
        print(f"  ⚠️  Aucun candidat éligible pour {city}")
        return [], 0

    reviews, cost2 = scrape_reviews([c["placeId"] for c in candidates])
    total_cost["reviews"] += cost2

    # Group reviews by place
    by_place = defaultdict(list)
    for r in reviews:
        by_place[r.get("placeId", "")].append(r)
    for pid in by_place:
        by_place[pid].sort(key=lambda r: r.get("publishedAtDate","") or "", reverse=True)

    # Apply rule v3
    validated = []
    for c in candidates:
        recs = by_place.get(c["placeId"], [])
        ok, info = apply_rule_v3(c, recs)
        if not ok: continue
        season = info if isinstance(info, dict) else {}
        texts = [r.get("text") or "" for r in recs[:15]]
        top_quotes = sorted([r for r in recs[:15] if (r.get("stars") or 0) == 5 and r.get("text")],
                           key=lambda r: len(r.get("text","")), reverse=True)[:3]
        c["_validation"] = info if isinstance(info, str) else f"{sum(1 for s in [(r.get('stars') or 0) for r in recs[:15]] if s==5)}/15 en 5★"
        c["_season"] = season
        c["_authenticity"] = {
            "with_text": sum(1 for t in texts if len(t) > 30),
            "with_photos": sum(1 for r in recs[:15] if r.get("reviewImageUrls")),
        }
        c["_top_quotes"] = [{"date": q.get("publishedAtDate","")[:10], "stars": q.get("stars"),
                             "text": (q.get("text") or "")[:250], "author": q.get("name","")} for q in top_quotes]
        c["_city"] = city
        validated.append(c)

    # Update cache
    for p in candidates:
        cache.setdefault("places", {})[p["placeId"]] = {"scraped_at": datetime.now().isoformat(), "city": city}

    print(f"  ✅ {len(validated)} restos validés pour {city}")
    return validated, cost1 + cost2

def merge_into_data(all_validated):
    if not all_validated: return 0
    d = json.load(open(DATA_FILE))
    existing_ids = {r["id"] for r in d}
    existing_keys = {(r["name"].lower().strip(), r["city"].lower().strip()) for r in d}

    def make_id(n, c):
        s = re.sub(r'[^a-z0-9]+','-', n.lower().strip()).strip('-')
        c2 = re.sub(r'[^a-z0-9]+','-', c.lower().strip()).strip('-')
        return s + '-' + c2

    price_map = {"Inexpensive":"€","Moderate":"€€","Expensive":"€€€","Very Expensive":"€€€€"}
    added = 0
    for p in all_validated:
        city = p["_city"]
        rid = make_id(p["name"], city)
        key = (p["name"].lower().strip(), city.lower().strip())
        if rid in existing_ids or key in existing_keys: continue
        season = p.get("_season", {})
        d.append({
            "id": rid,
            "name": p["name"],
            "address": p["address"],
            "city": city,
            "country": "France",  # à adapter selon ville
            "coordinates": {"lat": p.get("lat"), "lng": p.get("lng")},
            "cuisine_type": p.get("categoryName", "Restaurant"),
            "price_range": price_map.get(p.get("price_level",""), "€€€"),
            "vibe": "casual",
            "tags": [],
            "recommendations": [],
            "recommendation_count": 0,
            "confidence_score": int(p["rating"] * 20),
            "last_updated": datetime.now().isoformat()[:10],
            "source_type": "trending",
            "google_rating": p["rating"],
            "reviews_count_google": p["reviews_count"],
            "latest_review_date": season.get("last_review_date",""),
            "is_seasonal": season.get("seasonal", False),
            "currently_open": season.get("currently_open_season", True),
            "google_maps_url": p.get("url", ""),
            "photo_url": p.get("photo_url", ""),
            "top_recent_quotes": p["_top_quotes"]
        })
        added += 1

    json.dump(d, open(DATA_FILE, "w"), ensure_ascii=False)
    json.dump(d, open(os.path.join(ROOT, "data/restaurants.json"), "w"), ensure_ascii=False, indent=2)
    return added

def estimate_cost(cities):
    """Estime le coût avant de lancer."""
    n = len(cities)
    estimated_min = n * 0.10
    estimated_max = n * 0.20
    print(f"💰 Estimation pour {n} ville(s) : ${estimated_min:.2f} - ${estimated_max:.2f}")
    print(f"   (Plan Starter $29 → reste ~{int(29/0.15)} villes possibles)")
    return estimated_max

# ─────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    estimate_only = "--estimate-only" in args
    cities_arg = [a for a in args if not a.startswith("--")][0] if args else "Cannes"
    cities = [c.strip() for c in cities_arg.split(",")]

    print("=" * 60)
    print("  APIFY TRENDING SCRAPER — Optimized")
    print("=" * 60)
    estimate_cost(cities)

    if estimate_only:
        print("\n[--estimate-only] Pas de scraping lancé.")
        sys.exit(0)

    cache = load_cache()
    all_validated = []
    total_cost = {"places": 0, "reviews": 0}

    # ── BATCH MODE: 1 places run pour toutes les villes ──
    print(f"\n🚀 BATCH MODE: {len(cities)} ville(s) en 1 run places")
    by_city, cost1 = scrape_places_batch(cities, max_places_per_city=50)
    total_cost["places"] += cost1

    # Pre-filter et collect placeIds pour 1 run reviews global
    existing_ids = get_existing_place_ids() | set(cache.get("places", {}).keys())
    all_candidates = []
    candidates_by_city = {}
    for city, places in by_city.items():
        c = prefilter(places, existing_ids, max_candidates=15, city=city)
        candidates_by_city[city] = c
        all_candidates.extend([(city, p) for p in c])
        print(f"    {city}: {len(c)} candidats")

    if not all_candidates:
        print("\n  ⚠️  Aucun candidat éligible.")
        sys.exit(0)

    # ── 1 SEUL run reviews pour tous les candidats ──
    print(f"\n🚀 BATCH MODE: {len(all_candidates)} restos × 15 reviews en 1 run")
    all_pids = [c[1]["placeId"] for c in all_candidates]
    reviews, cost2 = scrape_reviews(all_pids)
    total_cost["reviews"] += cost2

    # Group reviews
    by_pid = defaultdict(list)
    for rev in reviews:
        by_pid[rev.get("placeId", "")].append(rev)
    for pid in by_pid:
        by_pid[pid].sort(key=lambda r: r.get("publishedAtDate","") or "", reverse=True)

    # Apply rule v3 per city
    for city, candidate in all_candidates:
        recs = by_pid.get(candidate["placeId"], [])
        ok, info = apply_rule_v3(candidate, recs)
        if not ok: continue
        season = info if isinstance(info, dict) else {}
        texts = [r.get("text") or "" for r in recs[:15]]
        top_quotes = sorted([r for r in recs[:15] if (r.get("stars") or 0) == 5 and r.get("text")],
                           key=lambda r: len(r.get("text","")), reverse=True)[:3]
        candidate["_validation"] = info if isinstance(info, str) else f"{sum(1 for s in [(r.get('stars') or 0) for r in recs[:15]] if s==5)}/15 en 5★"
        candidate["_season"] = season
        candidate["_authenticity"] = {
            "with_text": sum(1 for t in texts if len(t) > 30),
            "with_photos": sum(1 for r in recs[:15] if r.get("reviewImageUrls")),
        }
        candidate["_top_quotes"] = [{"date": q.get("publishedAtDate","")[:10], "stars": q.get("stars"),
                                     "text": (q.get("text") or "")[:250], "author": q.get("name","")} for q in top_quotes]
        candidate["_city"] = city
        all_validated.append(candidate)

    # Update cache
    for city, candidate in all_candidates:
        cache.setdefault("places", {})[candidate["placeId"]] = {"scraped_at": datetime.now().isoformat(), "city": city}

    save_cache(cache)
    added = merge_into_data(all_validated)

    total = total_cost["places"] + total_cost["reviews"]
    print("\n" + "=" * 60)
    print(f"📊 RAPPORT FINAL")
    print("=" * 60)
    print(f"  Villes traitées: {len(cities)}")
    print(f"  Restos validés: {len(all_validated)}")
    print(f"  Restos ajoutés à la base: {added}")
    print(f"\n💰 COÛT")
    print(f"  Places scraping: ${total_cost['places']:.3f}")
    print(f"  Reviews scraping: ${total_cost['reviews']:.3f}")
    print(f"  TOTAL: ${total:.3f}")
    print(f"  Coût moyen/ville: ${total/len(cities):.3f}")
    if added > 0:
        print(f"  Coût moyen/resto ajouté: ${total/added:.3f}")
