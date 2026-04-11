# Chefs Recommandations Scraper

## Objectif
Scraper le web et les réseaux sociaux pour collecter les restaurants recommandés par de grands chefs cuisiniers. Pas leurs propres restaurants, mais les adresses moins connues qu'ils recommandent personnellement.

## Stack
- Python 3.11+
- Agents orchestrés via Claude Code Agent Teams (fichiers `.md` dans `/agents/`)
- Stockage des données en JSON (output dans `/data/`)
- Scraping: `requests`, `beautifulsoup4`, `playwright` (pour les pages JS)

## Structure
```
agents/          # Définitions des agents (Claude Code Agent Teams)
src/             # Code Python des scrapers
data/            # Données collectées (JSON)
```

## Conventions
- Toutes les données en JSON avec le schéma défini dans `src/schemas.py`
- Un fichier JSON par source scrapée dans `data/raw/`
- Le fichier consolidé final dans `data/restaurants.json`
- Logs dans `data/logs/`
