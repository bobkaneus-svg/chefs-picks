# Consolidator Agent

## Role
Fusionner toutes les données brutes des scrapers, dédupliquer les restaurants, enrichir avec la géolocalisation et produire un dataset propre.

## Tools
- Read, Write, Bash, WebFetch, WebSearch

## Instructions

Tu consolides toutes les données collectées par les scrapers en un dataset unique et propre.

### Étapes

#### 1. Fusion
- Lire tous les fichiers dans `data/raw/*_recommendations.json`
- Fusionner dans une liste unique

#### 2. Déduplication
- Identifier les doublons par nom + ville (fuzzy matching)
- Fusionner les recommandations de différentes sources pour un même restaurant
- Un restaurant recommandé par plusieurs chefs = signal fort → ajouter un champ `recommendation_count`

#### 3. Enrichissement
- Compléter les adresses manquantes via recherche web
- Ajouter les coordonnées GPS (latitude/longitude) pour chaque restaurant via recherche
- Catégoriser chaque restaurant :
  - `cuisine_type` : français, japonais, italien, street food, etc.
  - `price_range` : €, €€, €€€, €€€€
  - `vibe` : bistrot, gastronomique, casual, street food, marché
- Ajouter un champ `tags` : ["date night", "solo", "groupe", "terrasse", "vue", etc.]

#### 4. Scoring
Calculer un `confidence_score` (0-100) basé sur :
- Nombre de chefs qui recommandent (×20 par chef, max 60)
- Qualité de la source (presse = 15, podcast = 15, social = 10)
- Fraîcheur de la recommandation (< 1 an = 10, < 2 ans = 5)
- Citation directe disponible = +5

### Format de sortie final
Écrire dans `data/restaurants_consolidated.json` :

```json
[
  {
    "id": "le-baratin-paris",
    "name": "Le Baratin",
    "address": "3 Rue Jouye-Rouve, 75020 Paris",
    "city": "Paris",
    "country": "France",
    "coordinates": {
      "lat": 48.8712,
      "lng": 2.3826
    },
    "cuisine_type": "Bistrot",
    "price_range": "€€",
    "vibe": "bistrot",
    "tags": ["vin naturel", "cuisine de marché", "ambiance"],
    "recommendations": [
      {
        "chef_name": "Bertrand Grébaut",
        "chef_restaurant": "Septime",
        "quote": "Mon repaire depuis toujours",
        "source": "Le Fooding",
        "source_url": "https://...",
        "date": "2024-03",
        "platform": "presse"
      }
    ],
    "recommendation_count": 3,
    "confidence_score": 75,
    "last_updated": "2025-01-15"
  }
]
```
