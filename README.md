# Redrawing Italy's Provinces

What if every Italian municipality belonged to the province whose capital is closest by straight-line distance?

This project uses a Voronoi-style approach on Italy's 110 provincial capitals to reassign all 7,896 municipalities ("comuni") to their nearest capoluogo. The result: **27% of municipalities would change province**, and **8.6% would also change region**.

## Live Demo

- [Interactive Map](https://chemickypes.github.io/map-project/) — toggle between old and new province boundaries, zoom into comuni that change
- [Stats & Infographic](https://chemickypes.github.io/map-project/infografica.html) — KPIs, top shifts, bar charts of gains/losses

## How It Works

1. **Fetch data** — downloads 2026 ISTAT administrative boundaries (shapefiles)
2. **Identify capitals** — selects one capoluogo per province, geocodes city centers via Wikidata SPARQL
3. **Assign comuni** — for each municipality, finds the nearest capital using haversine distance (scikit-learn BallTree)
4. **Dissolve boundaries** — merges comuni into new province polygons, computes statistics
5. **Generate outputs** — produces an interactive Leaflet map and a static infographic

## Key Findings

| Metric | Value |
|--------|-------|
| Total municipalities | 7,896 |
| Change province | 2,130 (27.0%) |
| Change region too | 682 (8.6%) |

**Biggest winner:** Biella (BI) — gains 116 comuni
**Biggest loser:** Cuneo (CN) — loses 102 comuni
**Most dramatic shift:** Castel di Lucio (Sicily) would save 81 km by moving to Enna

## Tech Stack

- **Python 3** — GeoPandas, Shapely, pyproj for geospatial processing
- **scikit-learn** — BallTree with haversine metric for nearest-neighbor search
- **Folium / Leaflet.js** — interactive map with toggleable layers
- **Wikidata SPARQL** — geocoding provincial capitals

## Running Locally

```bash
git clone https://github.com/chemickypes/map-project.git
cd map-project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

This runs the full pipeline and outputs `index.html` (map) and `infografica.html` (stats) at the repo root.

## Data Sources

- ISTAT administrative boundaries (2026 generalization)
- Wikidata for capital geocoding

## License

MIT
