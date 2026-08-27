"""Estrae un capoluogo per ogni UTS (provincia) con le coordinate del CENTRO CITTADINO.

Per le 8 UTS a capoluogo multiplo usa un override; per le altre prende l'unico
comune flaggato CC_UTS=1. Le coordinate sono geocodificate via Wikidata SPARQL
(una singola richiesta batch): per ogni nome di capoluogo recupera le coordinate
dell'entità che è capitale (P36) di un'unità amministrativa italiana. Questo
dà il centro cittadino reale e disambigua automaticamente omonimi (es. Massa).
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    COMUNI_SHP,
    PROV_SHP,
    REG_SHP,
    DATA_PROCESSED,
    CRS_SOURCE,
    CRS_TARGET,
    MULTI_CAPOLUOGO,
)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "map-project-voronoi-province/1.0 (personal project)"
GEOCACHE = DATA_PROCESSED / "capoluoghi_geocache.csv"

# Alias: nome ISTAT -> label Wikidata (per i rari mismatch)
ALIASES = {
    "Reggio di Calabria": "Reggio Calabria",
    "Bolzano/Bozen": "Bolzano",
    "Reggio nell'Emilia": "Reggio Emilia",
}


def pick_capoluoghi(comuni: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Un capoluogo (riga di comune) per ogni COD_UTS."""
    caps = comuni[comuni["CC_UTS"] == 1]
    chosen_idx = []
    for uts, group in caps.groupby("COD_UTS"):
        if uts in MULTI_CAPOLUOGO:
            match = group[group["COMUNE"] == MULTI_CAPOLUOGO[uts]]
            row = match.iloc[0] if not match.empty else group.sort_values("Shape_Area", ascending=False).iloc[0]
        elif len(group) == 1:
            row = group.iloc[0]
        else:  # fallback difensivo: comune con area maggiore
            row = group.sort_values("Shape_Area", ascending=False).iloc[0]
        chosen_idx.append(row.name)
    return comuni.loc[chosen_idx].copy()


def sparql_geocode(names: list[str]) -> dict[str, tuple[float, float]]:
    """Una query SPARQL: per ogni nome (label IT) le coordinate del capoluogo
    di un'unità amministrativa italiana. Disambigua omonimi tramite P36 inverso."""
    vals = " ".join(f'"{n}"@it' for n in names)
    query = f"""SELECT DISTINCT ?name ?lat ?lon WHERE {{
  VALUES ?name {{ {vals} }}
  ?cap rdfs:label ?name .
  ?cap ^wdt:P36 ?prov .
  ?prov wdt:P17 wd:Q38 .
  ?cap p:P625 ?stmt .
  ?stmt psv:P625 ?c .
  ?c wikibase:geoLatitude ?lat .
  ?c wikibase:geoLongitude ?lon .
}}"""
    resp = requests.get(
        WIKIDATA_SPARQL,
        params={"query": query, "format": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=90,
    )
    resp.raise_for_status()
    bindings = resp.json().get("results", {}).get("bindings", [])
    out: dict[str, tuple[float, float]] = {}
    for b in bindings:
        name = b["name"]["value"]
        coord = (float(b["lat"]["value"]), float(b["lon"]["value"]))
        out.setdefault(name, coord)  # primo risultato vince (duplicati ~identici)
    return out


def main() -> None:
    comuni = gpd.read_file(COMUNI_SHP, encoding="utf-8")
    prov = gpd.read_file(PROV_SHP, encoding="utf-8")
    reg = gpd.read_file(REG_SHP, encoding="utf-8")

    cap = pick_capoluoghi(comuni)

    prov_attr = prov[["COD_UTS", "DEN_UTS", "DEN_CM", "SIGLA", "TIPO_UTS"]].rename(
        columns={"DEN_UTS": "prov_name", "SIGLA": "sigla", "TIPO_UTS": "tipo_uts"}
    )
    cap = cap.merge(prov_attr, on="COD_UTS", how="left")

    # nomi per la query (risolti tramite alias)
    query_names = sorted({ALIASES.get(n, n) for n in cap["COMUNE"]})
    print(f"Geocodifica {len(cap)} capoluoghi via Wikidata SPARQL...")
    coords = sparql_geocode(query_names)
    print(f"  {len(coords)} coordinate ottenute da Wikidata")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"capoluogo": k, "lat": v[0], "lon": v[1]} for k, v in coords.items()]
    ).to_csv(GEOCACHE, index=False)

    # fallback: representative_point del comune (in 4326)
    fallback_pts = gpd.GeoSeries(cap.geometry.representative_point(), crs=CRS_SOURCE).to_crs(CRS_TARGET)

    lats, lons, srcs = [], [], []
    for i, name in enumerate(cap["COMUNE"]):
        qn = ALIASES.get(name, name)
        if qn in coords:
            la, lo = coords[qn]
            src = "wikidata"
        else:
            pt = fallback_pts.iloc[i]
            la, lo = pt.y, pt.x
            src = "fallback"
            print(f"  [WARN] {name}: nessun risultato Wikidata, uso representative_point")
        lats.append(la)
        lons.append(lo)
        srcs.append(src)

    cap = cap.reset_index(drop=True).copy()
    cap["lat"] = lats
    cap["lon"] = lons
    cap["geocode_src"] = srcs
    cap = gpd.GeoDataFrame(
        cap, geometry=[Point(xy) for xy in zip(cap["lon"], cap["lat"])], crs=CRS_TARGET
    )

    out = cap[
        ["COD_UTS", "COMUNE", "prov_name", "sigla", "tipo_uts", "COD_REG",
         "lat", "lon", "geocode_src", "geometry"]
    ].rename(columns={"COMUNE": "capoluogo", "COD_UTS": "cod_uts", "COD_REG": "cod_reg"})

    out_path = DATA_PROCESSED / "capoluoghi.geojson"
    out.to_file(out_path, driver="GeoJSON")

    n_fb = int((out["geocode_src"] == "fallback").sum())
    print(f"\nCapoluoghi: {len(out)} (attesi 110), fallback rep_point: {n_fb}")
    print(f"Salvato: {out_path}")
    for uts, name in [(18, "Pavia"), (2, "Vercelli")]:
        row = out[out["cod_uts"] == uts]
        if not row.empty:
            print(f"  UTS {uts} ({name}) -> capoluogo {row.iloc[0]['capoluogo']} "
                  f"@ {row.iloc[0]['lat']:.4f},{row.iloc[0]['lon']:.4f}")


if __name__ == "__main__":
    main()
