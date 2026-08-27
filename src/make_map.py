"""Mappa interattiva (folium) con le nuove province ridisegnate.

Layer:
  - Province NUOVE (fill colorato) [ON]
  - Province VECCHIE (fill) [OFF, per confronto]
  - Confini province attuali (linee nere) [ON, overlay sul fill nuovo]
  - Confini regionali (linee rosse spesse) [ON]
  - Capoluoghi (marker) [ON]
  - Comuni che cambiano provincia (arancio, hover) [ON]
  - Tutti i comuni (outline, hover) [OFF]
Output: outputs/map.html
"""
import json
import random
import sys
from pathlib import Path
import colorsys

import folium
import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PROCESSED, OUTPUTS, ROOT

SIMPLIFY_TOL = 0.006  # gradi (~600m)


def load(name):
    return gpd.read_file(DATA_PROCESSED / name)


def to_geojson(gdf):
    return json.loads(gdf.to_json())


def palette(n):
    cols = []
    for i in range(n):
        h = i / n
        s = 0.55 + 0.35 * ((i % 3) / 2)
        v = 0.85 + 0.10 * ((i % 2))
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        cols.append("#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255)))
    random.Random(42).shuffle(cols)
    return cols


def main() -> None:
    new_prov = load("new_provinces.geojson")
    old_prov = load("old_provinces.geojson")
    regioni = load("regioni.geojson")
    capoluoghi = load("capoluoghi.geojson")
    comuni = load("comuni_assigned.geojson")

    # semplifica geometrie per leggerezza della mappa
    for g in (new_prov, old_prov, regioni):
        g["geometry"] = g.geometry.simplify(SIMPLIFY_TOL, preserve_topology=True)
    comuni["geometry"] = comuni.geometry.simplify(SIMPLIFY_TOL, preserve_topology=True)

    changed = comuni[comuni["changed"]].copy()

    # colori per le province (palette coerente nuovo/vecchio per sigla)
    all_sigle = sorted(set(new_prov["new_sigla"]) | set(old_prov["sigla"]))
    cols = palette(len(all_sigle))
    sig_color = {s: cols[i] for i, s in enumerate(all_sigle)}

    m = folium.Map(location=[42.5, 12.5], zoom_start=6, tiles="OpenStreetMap")

    # --- Province NUOVE (fill) ---
    def style_new(feat):
        c = sig_color.get(feat["properties"]["new_sigla"], "#888888")
        return {"fillColor": c, "color": "#444444", "weight": 0.6, "fillOpacity": 0.65}

    folium.GeoJson(
        to_geojson(new_prov),
        name="Province NUOVE (Voronoi)",
        style_function=style_new,
        tooltip=folium.GeoJsonTooltip(
            fields=["new_prov", "new_sigla", "new_capoluogo", "n_comuni",
                    "n_changed", "pct_changed", "area_km2"],
            aliases=["Provincia:", "Sigla:", "Capoluogo:", "N° comuni:",
                     "Comuni cambiati:", "% cambiati:", "Area km²:"],
            localize=True, sticky=False,
        ),
        highlight_function=lambda f: {"weight": 2, "color": "#000000"},
    ).add_to(m)

    # --- Province VECCHIE (fill, default off) ---
    def style_old(feat):
        c = sig_color.get(feat["properties"]["sigla"], "#888888")
        return {"fillColor": c, "color": "#444444", "weight": 0.6, "fillOpacity": 0.65}

    folium.GeoJson(
        to_geojson(old_prov),
        name="Province VECCHIE (attuali)",
        style_function=style_old,
        tooltip=folium.GeoJsonTooltip(
            fields=["prov_name", "sigla", "area_km2"],
            aliases=["Provincia:", "Sigla:", "Area km²:"],
            localize=True, sticky=False,
        ),
        show=False,
    ).add_to(m)

    # --- Confini province attuali (linee nere, overlay) ---
    folium.GeoJson(
        to_geojson(old_prov),
        name="Confini provinciali attuali",
        style_function=lambda f: {"fillColor": "#00000000", "color": "#000000",
                                  "weight": 1.0, "opacity": 0.55, "fillOpacity": 0},
        tooltip=folium.GeoJsonTooltip(fields=["prov_name", "sigla"],
                                      aliases=["Provincia:", "Sigla:"], sticky=False),
    ).add_to(m)

    # --- Confini regionali (linee rosse) ---
    folium.GeoJson(
        to_geojson(regioni),
        name="Confini regionali (attuali)",
        style_function=lambda f: {"fillColor": "#00000000", "color": "#b30000",
                                  "weight": 2.5, "opacity": 0.85, "fillOpacity": 0},
        tooltip=folium.GeoJsonTooltip(fields=["reg_name"], aliases=["Regione:"], sticky=False),
    ).add_to(m)

    # --- Capoluoghi (marker) ---
    cap_layer = folium.FeatureGroup(name="Capoluoghi (siti Voronoi)", show=True)
    for _, r in capoluoghi.iterrows():
        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=3.5,
            color="#1f78b4",
            fill=True,
            fill_color="#1f78b4",
            fill_opacity=0.9,
            weight=1,
            tooltip=f"{r['capoluogo']} ({r['sigla']}) — capoluogo di provincia",
        ).add_to(cap_layer)
    cap_layer.add_to(m)

    # --- Comuni che cambiano provincia (arancio, hover) ---
    def style_changed(feat):
        cross = feat["properties"].get("changed_region")
        col = "#e41a1c" if cross else "#ff7f00"
        return {"fillColor": col, "color": col, "weight": 0.4, "fillOpacity": 0.55}

    folium.GeoJson(
        to_geojson(changed),
        name="Comuni che cambiano provincia",
        style_function=style_changed,
        tooltip=folium.GeoJsonTooltip(
            fields=["COMUNE", "old_prov", "new_prov", "dist_old_km", "dist_new_km", "delta_km", "changed_region"],
            aliases=["Comune:", "Da prov.:", "A prov.:", "Km (vecchia):",
                     "Km (nuova):", "Risparmio km:", "Cambia regione:"],
            localize=True, sticky=True,
        ),
        highlight_function=lambda f: {"weight": 2, "color": "#000000"},
    ).add_to(m)

    # --- Tutti i comuni (outline, default off) ---
    folium.GeoJson(
        to_geojson(comuni),
        name="Tutti i comuni (outline)",
        style_function=lambda f: {"fillColor": "#00000000", "color": "#555555",
                                  "weight": 0.3, "opacity": 0.5, "fillOpacity": 0},
        tooltip=folium.GeoJsonTooltip(
            fields=["COMUNE", "old_prov", "new_prov", "changed", "changed_region"],
            aliases=["Comune:", "Prov. attuale:", "Prov. nuova:", "Cambia?", "Cambia regione?"],
            sticky=False,
        ),
        show=False,
    ).add_to(m)

    # --- legenda ---
    legend = """
    <div style="position:fixed;bottom:20px;left:20px;z-index:9999;font:13px/1.4 Arial;
                background:white;padding:10px 12px;border:1px solid #888;border-radius:6px;box-shadow:2px 2px 6px rgba(0,0,0,.3)">
      <b>Ridisegno delle province (Voronoi sui capoluoghi)</b><br>
      <span style="color:#ff7f00">■</span> comune che cambia provincia (stessa regione)<br>
      <span style="color:#e41a1c">■</span> comune che cambia provincia e regione<br>
      <span style="color:#000">━</span> confine provinciale attuale<br>
      <span style="color:#b30000">━</span> confine regionale<br>
      <span style="color:#1f78b4">●</span> capoluogo (sito Voronoi)<br>
      <small>Usa il controllo layer in alto a destra per vecchio/nuovo.</small>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend))

    nav_button = """
    <a href="infografica.html"
       style="position:fixed;bottom:20px;right:20px;z-index:9999;
              background:#ff7f00;color:#fff;padding:10px 18px;
              border-radius:8px;text-decoration:none;font:600 14px/1 Arial;
              box-shadow:2px 2px 6px rgba(0,0,0,.35);transition:background .2s"
       onmouseover="this.style.background='#e67300'"
       onmouseout="this.style.background='#ff7f00'">
       Stats &#8594;
    </a>"""
    m.get_root().html.add_child(folium.Element(nav_button))

    folium.LayerControl(collapsed=False).add_to(m)

    ROOT.mkdir(parents=True, exist_ok=True)
    out = ROOT / "index.html"
    m.save(str(out))
    print(f"Mappa salvata: {out} ({out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
