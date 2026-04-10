"""
Consolidation de toutes les données brutes en un fichier restaurants.json unique.
Déduplique, normalise, ajoute des coordonnées GPS approximatives par ville.
"""

import json
import os
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"

# Coordonnées GPS approximatives par ville (centre-ville)
CITY_COORDS = {
    "Paris": (48.8566, 2.3522),
    "Marseille": (43.2965, 5.3698),
    "Nice": (43.7102, 7.2620),
    "Lyon": (45.7640, 4.8357),
    "Bordeaux": (44.8378, -0.5792),
    "Toulouse": (43.6047, 1.4442),
    "Aix-en-Provence": (43.5297, 5.4474),
    "Avignon": (43.9493, 4.8055),
    "Arles": (43.6767, 4.6278),
    "Menton": (43.7764, 7.5048),
    "Cannes": (43.5528, 7.0174),
    "Antibes": (43.5808, 7.1239),
    "Saint-Tropez": (43.2727, 6.6406),
    "Ramatuelle": (43.2165, 6.6404),
    "Cassis": (43.2142, 5.5378),
    "Bandol": (43.1357, 5.7525),
    "Toulon": (43.1242, 5.9280),
    "Rennes": (48.1173, -1.6778),
    "Saint-Malo": (48.6493, -2.0070),
    "Cancale": (48.6736, -1.8514),
    "Brest": (48.3904, -4.4861),
    "Carnac": (47.5839, -3.0781),
    "Biarritz": (43.4832, -1.5586),
    "Bayonne": (43.4933, -1.4748),
    "Saint-Jean-de-Luz": (43.3857, -1.6601),
    "Hasparren": (43.3840, -1.3070),
    "Ahetze": (43.4200, -1.5600),
    "Roquebrune-Cap-Martin": (43.7600, 7.4700),
    "Le Cannet": (43.5772, 7.0194),
    "Belcastel": (44.3892, 2.3351),
    "Montreuil-sur-Mer": (50.4633, 1.7653),
    "La Rochelle": (46.1603, -1.1511),
    "Kaysersberg": (48.1400, 7.2636),
    "Saint-Martin-de-Belleville": (45.3833, 6.5167),
    "Florence": (43.7696, 11.2558),
    "Londres": (51.5074, -0.1278),
    "New York": (40.7128, -74.0060),
    "Tokyo": (35.6762, 139.6503),
    "Bruxelles": (50.8503, 4.3517),
    "Carhaix": (48.2770, -3.5727),
}

# Petit offset pour éviter que les pins se superposent
import random
random.seed(42)

def make_id(name, city):
    """Crée un ID unique à partir du nom et de la ville."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip())
    slug = slug.strip('-')
    city_slug = re.sub(r'[^a-z0-9]+', '-', city.lower().strip()).strip('-')
    return f"{slug}-{city_slug}"

def normalize_price(price):
    """Normalise la gamme de prix."""
    if not price:
        return "€€"
    # Count euro signs or $ signs
    euros = price.count('€') + price.count('$')
    if euros >= 4:
        return "€€€€"
    elif euros == 3:
        return "€€€"
    elif euros <= 1:
        return "€"
    return "€€"

def get_vibe(cuisine, price, tags_str=""):
    """Détermine le vibe du restaurant."""
    s = (cuisine + " " + tags_str).lower()
    if any(w in s for w in ["street food", "street", "pita", "sandwich", "panini", "falafel"]):
        return "street food"
    if any(w in s for w in ["gastronomique", "fine dining", "étoile", "omakase"]):
        return "gastronomique"
    if any(w in s for w in ["bar à vin", "bar a vin", "wine bar", "cave", "tapas"]):
        return "bar à vins"
    if any(w in s for w in ["bistrot", "bistro", "bouchon", "troquet", "cantine"]):
        return "bistrot"
    if any(w in s for w in ["boulangerie", "café", "cafe", "patisserie", "pâtisserie"]):
        return "café"
    return "casual"

def get_coords(city, existing_coords=None):
    """Retourne les coordonnées GPS avec un petit offset aléatoire."""
    if existing_coords:
        return existing_coords
    base = CITY_COORDS.get(city)
    if not base:
        # Essayer une correspondance partielle
        for k, v in CITY_COORDS.items():
            if k.lower() in city.lower() or city.lower() in k.lower():
                base = v
                break
    if not base:
        base = (46.6034, 1.8883)  # Centre de la France par défaut
    # Petit offset aléatoire pour éviter la superposition
    lat = base[0] + random.uniform(-0.008, 0.008)
    lng = base[1] + random.uniform(-0.008, 0.008)
    return {"lat": round(lat, 4), "lng": round(lng, 4)}

def extract_tags(cuisine, vibe, price, name):
    """Extrait des tags depuis les infos disponibles."""
    tags = []
    s = cuisine.lower() if cuisine else ""
    tag_map = {
        "pizza": "pizza", "pho": "pho", "sushi": "sushi", "ramen": "ramen",
        "huître": "huîtres", "huitre": "huîtres", "poisson": "poisson",
        "vin natur": "vin naturel", "wine": "vin", "crêpe": "crêpes",
        "socca": "socca", "tapas": "tapas", "burger": "burger",
        "boulang": "boulangerie", "pâtiss": "pâtisserie", "patiss": "pâtisserie",
        "végét": "végétarien", "veget": "végétarien", "marché": "cuisine de marché",
        "provençal": "provençal", "méditerran": "méditerranéen", "basque": "basque",
        "vietnamien": "vietnamien", "japonais": "japonais", "italien": "italien",
        "chinois": "chinois", "coréen": "coréen", "mexicain": "mexicain",
        "israel": "israélien", "libanais": "libanais",
    }
    for key, tag in tag_map.items():
        if key in s:
            tags.append(tag)
    return tags[:5]  # Max 5 tags

def load_raw_files():
    """Charge tous les fichiers bruts."""
    all_entries = []
    for f in sorted(RAW_DIR.iterdir()):
        if f.suffix == '.json':
            try:
                data = json.loads(f.read_text())
                for entry in data:
                    entry['_source_file'] = f.name
                all_entries.extend(data)
            except Exception as e:
                print(f"  Erreur {f.name}: {e}")
    return all_entries

def normalize_entry(raw):
    """Normalise une entrée brute (format variable) en format standard."""
    # Les fichiers bruts ont des clés variées
    name = raw.get('restaurant') or raw.get('name') or raw.get('restaurant_name', '')
    if not name:
        return None

    city = raw.get('ville') or raw.get('city', 'Paris')
    country = raw.get('pays') or raw.get('country', 'France')
    address = raw.get('adresse') or raw.get('address', '')
    cuisine = raw.get('type_cuisine') or raw.get('cuisine_type', '')
    price = raw.get('gamme_prix') or raw.get('price_range', '€€')

    chef = raw.get('chef_qui_recommande') or raw.get('chef_name', '')
    chef_resto = raw.get('restaurant_du_chef') or raw.get('chef_restaurant', '')
    quote = raw.get('citation') or raw.get('quote', '')
    source = raw.get('source') or raw.get('source_name', '')
    source_url = raw.get('url_source') or raw.get('source_url')
    date = raw.get('date_approximative') or raw.get('date', '')
    platform = raw.get('plateforme') or raw.get('platform', 'presse')

    # Normaliser la plateforme
    platform_lower = platform.lower() if platform else ''
    if any(w in platform_lower for w in ['instagram', 'tiktok', 'twitter', 'social', 'réseaux']):
        platform = 'social'
    elif any(w in platform_lower for w in ['podcast', 'radio', 'inter']):
        platform = 'podcast'
    else:
        platform = 'presse'

    return {
        'name': name.strip(),
        'city': city.strip(),
        'country': country.strip(),
        'address': address.strip(),
        'cuisine_type': cuisine.strip(),
        'price_range': normalize_price(price),
        'chef_name': chef.strip(),
        'chef_restaurant': chef_resto.strip(),
        'quote': quote.strip(),
        'source': source.strip(),
        'source_url': source_url if source_url else None,
        'date': str(date).strip() if date else '',
        'platform': platform,
    }

def consolidate():
    """Pipeline de consolidation."""
    print("=== Consolidation ===\n")

    # 1. Charger les données brutes
    raw_entries = load_raw_files()
    print(f"Entrées brutes chargées: {len(raw_entries)}")

    # 2. Charger les existantes
    existing_file = DATA_DIR / "restaurants.json"
    existing = []
    if existing_file.exists():
        existing = json.loads(existing_file.read_text())
        print(f"Existantes chargées: {len(existing)}")

    # 3. Normaliser les entrées brutes
    normalized = []
    for raw in raw_entries:
        entry = normalize_entry(raw)
        if entry and entry['name']:
            normalized.append(entry)
    print(f"Entrées normalisées: {len(normalized)}")

    # 4. Grouper par restaurant (dédupliquer)
    restaurants = {}

    # D'abord les existants
    for r in existing:
        rid = r.get('id', make_id(r['name'], r['city']))
        restaurants[rid] = r

    # Puis les nouvelles entrées
    for entry in normalized:
        rid = make_id(entry['name'], entry['city'])

        if rid not in restaurants:
            vibe = get_vibe(entry['cuisine_type'], entry['price_range'])
            tags = extract_tags(entry['cuisine_type'], vibe, entry['price_range'], entry['name'])
            restaurants[rid] = {
                'id': rid,
                'name': entry['name'],
                'address': entry['address'],
                'city': entry['city'],
                'country': entry['country'],
                'coordinates': get_coords(entry['city']),
                'cuisine_type': entry['cuisine_type'],
                'price_range': entry['price_range'],
                'vibe': vibe,
                'tags': tags,
                'recommendations': [],
                'recommendation_count': 0,
                'confidence_score': 0,
                'last_updated': '2025-01-15',
            }

        r = restaurants[rid]

        # Vérifier si cette recommandation existe déjà
        chef_exists = any(
            rec.get('chef_name') == entry['chef_name']
            for rec in r['recommendations']
        )

        if not chef_exists and entry['chef_name']:
            r['recommendations'].append({
                'chef_name': entry['chef_name'],
                'chef_restaurant': entry['chef_restaurant'],
                'quote': entry['quote'],
                'source': entry['source'],
                'source_url': entry['source_url'],
                'date': entry['date'],
                'platform': entry['platform'],
            })

    # 5. Calculer les scores
    for rid, r in restaurants.items():
        r['recommendation_count'] = len(r['recommendations'])

        score = 0
        for rec in r['recommendations']:
            score += 20  # par chef
            if rec.get('platform') == 'presse':
                score += 15
            elif rec.get('platform') == 'podcast':
                score += 15
            elif rec.get('platform') == 'social':
                score += 10
            if rec.get('quote'):
                score += 5
            if rec.get('source_url'):
                score += 5

        r['confidence_score'] = min(score, 100)

    # 6. Trier par score décroissant
    result = sorted(restaurants.values(), key=lambda r: r['confidence_score'], reverse=True)

    # 7. Stats
    chefs = set()
    cities = set()
    countries = set()
    for r in result:
        cities.add(r['city'])
        countries.add(r['country'])
        for rec in r['recommendations']:
            chefs.add(rec['chef_name'])

    print(f"\n=== Résultats ===")
    print(f"Restaurants uniques: {len(result)}")
    print(f"Chefs uniques: {len(chefs)}")
    print(f"Villes: {len(cities)}")
    print(f"Pays: {len(countries)}")

    multi = [r for r in result if r['recommendation_count'] >= 2]
    print(f"\nRecommandés par 2+ chefs: {len(multi)}")
    for r in multi[:10]:
        chef_names = ', '.join(rec['chef_name'] for rec in r['recommendations'])
        print(f"  {r['name']} ({r['city']}) — {r['recommendation_count']} chefs: {chef_names}")

    print(f"\nTop villes:")
    from collections import Counter
    city_counts = Counter(r['city'] for r in result)
    for city, count in city_counts.most_common(15):
        print(f"  {city}: {count}")

    # 8. Sauvegarder
    output = DATA_DIR / "restaurants.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nFichier sauvegardé: {output} ({len(result)} restaurants)")

if __name__ == "__main__":
    consolidate()
