"""
Script d'orchestration du pipeline de scraping.
Lance les agents Claude Code dans le bon ordre.

Usage:
    cd chefs-recommandations
    claude --agent agents/orchestrator.md

Ou étape par étape :
    claude --agent agents/chef-finder.md
    claude --agent agents/scraper-presse.md
    claude --agent agents/scraper-social.md
    claude --agent agents/scraper-podcasts.md
    claude --agent agents/consolidator.md
    claude --agent agents/quality-checker.md
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
LOGS_DIR = DATA_DIR / "logs"


def check_prerequisites():
    """Vérifie que les dossiers nécessaires existent."""
    for d in [DATA_DIR, RAW_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    print("✓ Dossiers vérifiés")


def check_phase_output(phase_name: str, expected_file: str) -> bool:
    """Vérifie qu'une phase a produit son output."""
    path = RAW_DIR / expected_file
    if path.exists():
        data = json.loads(path.read_text())
        count = len(data) if isinstance(data, list) else 0
        print(f"✓ {phase_name}: {count} entrées dans {expected_file}")
        return True
    else:
        print(f"✗ {phase_name}: {expected_file} manquant")
        return False


def print_final_stats():
    """Affiche les stats du fichier final."""
    final = DATA_DIR / "restaurants.json"
    if not final.exists():
        print("✗ Fichier final restaurants.json non trouvé")
        return

    data = json.loads(final.read_text())
    restaurants = data if isinstance(data, list) else []

    chefs = set()
    cities = set()
    countries = set()
    for r in restaurants:
        cities.add(r.get("city", ""))
        countries.add(r.get("country", ""))
        for rec in r.get("recommendations", []):
            chefs.add(rec.get("chef_name", ""))

    print("\n" + "=" * 50)
    print("RÉSULTATS FINAUX")
    print("=" * 50)
    print(f"Restaurants : {len(restaurants)}")
    print(f"Chefs       : {len(chefs)}")
    print(f"Villes      : {len(cities)}")
    print(f"Pays        : {len(countries)}")

    # Top restaurants
    top = sorted(restaurants, key=lambda r: r.get("recommendation_count", 0), reverse=True)[:10]
    if top:
        print("\nTop 10 restaurants les plus recommandés :")
        for i, r in enumerate(top, 1):
            print(f"  {i}. {r['name']} ({r.get('city', '?')}) - {r.get('recommendation_count', 0)} chefs")


if __name__ == "__main__":
    check_prerequisites()

    print("\nVérification des outputs par phase :")
    check_phase_output("Phase 1 - Chefs", "chefs_list.json")
    check_phase_output("Phase 2a - Presse", "presse_recommendations.json")
    check_phase_output("Phase 2b - Social", "social_recommendations.json")
    check_phase_output("Phase 2c - Podcasts", "podcasts_recommendations.json")

    print_final_stats()
