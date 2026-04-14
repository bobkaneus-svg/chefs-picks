# Trending Scraper Optimized Agent

## Mission
Scraper et valider des restaurants "trending" via Google Maps avec un coût Apify minimal.

## Diagnostic des coûts actuels

D'après l'analyse des runs Apify précédents :

| Actor | Coût/run | Usage |
|-------|----------|-------|
| `compass/crawler-google-places` (Places) | $0.05-0.25 | Liste les restos d'une ville |
| `compass/google-maps-reviews-scraper` (Reviews) | $0.20-0.22 | Récupère les avis récents |

**Coût actuel moyen par ville** : ~$0.40-0.50
**Goulot d'étranglement** : le reviews scraper. On scrape 20 avis × 30+ places = 600 reviews/ville.

## Stratégie d'optimisation (3-pass)

### Pass 1 — Places light (économique)
- 1 seule recherche Google Maps par ville (pas 6 comme avant)
- maxCrawledPlacesPerSearch: 100 (au lieu de 250)
- Skip `permanentlyClosed` et `temporarilyClosed`
- Sauvegarde du placeId dans un cache pour éviter rescrape

### Pass 2 — Pre-filter agressif (gratuit, juste filtrage local)
- Garder uniquement : rating ≥ 4.5 ET reviews_count ≥ 50
- Exclure les placeIds déjà dans `data.json` (déjà connus)
- Limiter à top 15 candidats max par ville (au lieu de 30)
- Catégorie "restaurant"/"bistro"/"trattoria" uniquement (pas hôtels, bars sans cuisine)

### Pass 3 — Reviews ciblées
- 15 avis par place (au lieu de 20) — suffisant pour règle v3
- Sort by "newest" obligatoire
- Batch de 15 candidats max → 1 seul run au lieu de plusieurs

### Pass 4 — Application règle v3 (gratuit, local)
- 60% des 15 derniers en 5★
- 3 derniers ≥ 4★
- Pas 2 négatifs consécutifs (sauf si corrigés)
- Détection saisonnalité

## Économies estimées

| Approche | Coût/ville | Villes/$29 |
|----------|-----------|------------|
| Ancienne | $0.40-0.50 | 60-70 |
| **Optimisée** | **$0.10-0.18** | **160-290** |

## Cache & Anti-redondance

- Fichier `data/raw/cache_placeids.json` : tous les placeIds déjà scrapés
- Avant chaque scrape, vérifier le cache → éviter de payer 2x
- Cache des reviews aussi (TTL 30 jours pour éviter les données périmées)

## Workflow d'exécution

```bash
python3 src/apify_trending.py "Nice"
python3 src/apify_trending.py "Marseille,Lyon,Bordeaux"  # multi-villes
python3 src/apify_trending.py --estimate-only "Cannes"   # juste l'estimation
```

## Output
- Ajoute les nouveaux trending validés dans `dashboard/data.json` avec `source_type: trending`
- Update `data/raw/cache_placeids.json`
- Affiche un rapport de coût final
