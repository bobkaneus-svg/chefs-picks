"""
Scraping via Apify pour trouver des recommandations de restaurants par des chefs.

Actors utilisés :
1. Google Search Scraper — recherche d'articles avec recommandations
2. Instagram Scraper — posts de chefs taggant des restaurants
3. Google Maps Scraper — enrichir les restaurants avec coordonnées/photos

Usage:
    python3 src/apify_scraper.py google   # Scrape Google pour des articles
    python3 src/apify_scraper.py instagram # Scrape Instagram de chefs
    python3 src/apify_scraper.py enrich    # Enrichir les restos existants via Google Maps
    python3 src/apify_scraper.py all       # Tout lancer
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

TOKEN = os.getenv("APIFY_API_TOKEN")
client = ApifyClient(TOKEN)

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"

# ═══════════════════════════════════════
# GOOGLE SEARCH — trouver des articles
# ═══════════════════════════════════════

GOOGLE_QUERIES = [
    # France - général
    "restaurants préférés des chefs étoilés France",
    "où mangent les chefs quand ils ne travaillent pas",
    "adresses secrètes des chefs étoilés",
    "cantines préférées des chefs Paris",
    "where do French chefs eat",
    # PACA
    "restaurants préférés chefs Marseille",
    "où mangent les chefs Nice Côte d'Azur",
    "bonnes adresses chefs Aix-en-Provence Provence",
    "restaurants recommandés chefs Antibes Cannes",
    "cantines chefs étoilés sud France",
    # Lyon / Bordeaux
    "bouchons préférés des chefs Lyon",
    "restaurants préférés chefs Bordeaux",
    # Bretagne / Normandie / Sud-Ouest
    "restaurants préférés chefs Bretagne",
    "où mangent les chefs Pays Basque Biarritz",
    "tables secrètes chefs Toulouse",
    # Chefs spécifiques
    "Mory Sacko restaurant préféré",
    "Cyril Lignac adresses préférées",
    "Hélène Darroze restaurant favori",
    "Alexandre Mazzia bonnes adresses",
    "Thierry Marx restaurant recommandé",
    "Bertrand Grébaut restaurants préférés Paris",
    "Pierre Gagnaire adresses secrètes",
    "Jean-François Piège restaurant préféré",
    "Philippe Etchebest restaurant préféré Bordeaux",
    "Mauro Colagreco restaurant favori",
    # International
    "where chefs eat in France",
    "best restaurants recommended by French chefs",
    "chef's favorite restaurants France hidden gems",
]


def scrape_google():
    """Lance le Google Search Scraper pour trouver des articles."""
    print(f"🔍 Google Search: {len(GOOGLE_QUERIES)} requêtes...")

    run = client.actor("apify/google-search-scraper").call(
        run_input={
            "queries": "\n".join(GOOGLE_QUERIES),
            "maxPagesPerQuery": 2,
            "resultsPerPage": 10,
            "languageCode": "fr",
            "countryCode": "fr",
            "mobileResults": False,
        },
        timeout_secs=300,
    )

    results = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        organic = item.get("organicResults", [])
        for r in organic:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
                "query": item.get("searchQuery", {}).get("term", ""),
            })

    output = RAW_DIR / "apify_google_results.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"✅ {len(results)} résultats Google sauvegardés dans {output}")
    return results


# ═══════════════════════════════════════
# INSTAGRAM — posts de chefs
# ═══════════════════════════════════════

CHEF_INSTAGRAM_HANDLES = [
    "morysacko", "cyabordeaux", "helenrdarroze", "alexandremazzia",
    "thierrymarx", "pierregagnaire", "juanarbelaez", "juliensebbag",
    "septime_charonne", "tatiana_levha", "david.toutain",
    "gregmarchand", "pierresangboyer", "jfrancoispiege",
    "yvescamdeborde", "brunobverjus", "christianlesquer",
    "philippeetchebest", "chefglennviel", "simone.tondo",
]


def scrape_instagram():
    """Scrape les posts Instagram de chefs pour trouver des mentions de restaurants."""
    print(f"📸 Instagram: {len(CHEF_INSTAGRAM_HANDLES)} comptes...")

    run = client.actor("apify/instagram-post-scraper").call(
        run_input={
            "username": CHEF_INSTAGRAM_HANDLES,
            "resultsLimit": 30,  # 30 derniers posts par chef
        },
        timeout_secs=600,
    )

    results = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        caption = item.get("caption", "") or ""
        location = item.get("locationName", "") or ""
        mentions = item.get("mentions", []) or []

        # Filtrer: on veut des posts qui mentionnent un lieu/restaurant
        if location or any(w in caption.lower() for w in [
            "restaurant", "bistrot", "table", "manger", "dîner", "déjeuner",
            "adresse", "recommande", "favori", "préféré", "pépite", "cantine",
            "eating", "dinner", "lunch", "favorite",
        ]):
            results.append({
                "chef_handle": item.get("ownerUsername", ""),
                "caption": caption[:500],
                "location": location,
                "mentions": mentions,
                "hashtags": item.get("hashtags", []),
                "url": item.get("url", ""),
                "timestamp": item.get("timestamp", ""),
                "likes": item.get("likesCount", 0),
            })

    output = RAW_DIR / "apify_instagram_posts.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"✅ {len(results)} posts Instagram pertinents sauvegardés dans {output}")
    return results


# ═══════════════════════════════════════
# GOOGLE MAPS — enrichir les restaurants
# ═══════════════════════════════════════

def enrich_with_google_maps():
    """Enrichit les restaurants existants avec des données Google Maps."""
    restaurants_file = DATA_DIR / "restaurants.json"
    if not restaurants_file.exists():
        print("❌ Pas de restaurants.json trouvé")
        return

    restaurants = json.loads(restaurants_file.read_text())

    # Préparer les requêtes de recherche
    queries = []
    for r in restaurants:
        q = f"{r['name']} {r.get('address', '')} {r['city']}"
        queries.append(q)

    print(f"🗺️  Google Maps: enrichissement de {len(queries)} restaurants...")

    # Batch par 50 pour ne pas exploser le quota
    batch_size = 50
    all_results = []

    for i in range(0, min(len(queries), 200), batch_size):
        batch = queries[i:i + batch_size]
        print(f"  Batch {i // batch_size + 1}: {len(batch)} requêtes...")

        run = client.actor("compass/crawler-google-places").call(
            run_input={
                "searchStringsArray": batch,
                "maxCrawledPlacesPerSearch": 1,
                "language": "fr",
                "countryCode": "fr",
            },
            timeout_secs=300,
        )

        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            all_results.append({
                "name": item.get("title", ""),
                "address": item.get("address", ""),
                "phone": item.get("phone", ""),
                "website": item.get("website", ""),
                "rating": item.get("totalScore", 0),
                "reviews_count": item.get("reviewsCount", 0),
                "lat": item.get("location", {}).get("lat"),
                "lng": item.get("location", {}).get("lng"),
                "categories": item.get("categories", []),
                "photo_url": item.get("imageUrl", ""),
                "opening_hours": item.get("openingHours", []),
                "price_level": item.get("price", ""),
                "google_maps_url": item.get("url", ""),
            })

    output = RAW_DIR / "apify_gmaps_enrichment.json"
    output.write_text(json.dumps(all_results, ensure_ascii=False, indent=2))
    print(f"✅ {len(all_results)} fiches Google Maps sauvegardées dans {output}")
    return all_results


# ═══════════════════════════════════════
# MAIN
# ═══════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "google":
        scrape_google()
    elif cmd == "instagram":
        scrape_instagram()
    elif cmd == "enrich":
        enrich_with_google_maps()
    elif cmd == "all":
        scrape_google()
        scrape_instagram()
        enrich_with_google_maps()
    else:
        print(f"Usage: python3 {sys.argv[0]} [google|instagram|enrich|all]")
