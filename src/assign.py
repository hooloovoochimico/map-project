"""Assegna ogni comune al capoluogo di provincia più vicino (Voronoi su capoluoghi).

Per ogni comune calcola, in linea d'aria (haversine):
  - new_cod_uts / new_prov / new_sigla : provincia del capoluogo più vicino
  - dist_new  : distanza al capoluogo più vicino
  - dist_old  : distanza al capoluogo della provincia di appartenenza attuale
  - changed        : la provincia è cambiata?
  - changed_region : il nuovo capoluogo è in un'altra regione?
Output: data/processed/comuni_assigned.geojson (poligoni in WGS84).
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import COMUNI_SHP, PROV_SHP, REG_SHP, DATA_PROCESSED, CRS_SOURCE, CRS_TARGET

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * np.arcsin(np.sqrt(a)) * EARTH_RADIUS_KM


def main() -> None:
    comuni = gpd.read_file(COMUNI_SHP, encoding="utf-8")  # UTM32N
    cap = gpd.read_file(DATA_PROCESSED / "capoluoghi.geojson")  # 4326 points
    prov = gpd.read_file(PROV_SHP, encoding="utf-8")
    reg = gpd.read_file(REG_SHP, encoding="utf-8")

    # representative point di ogni comune, in WGS84
    rep = gpd.GeoSeries(comuni.geometry.representative_point(), crs=CRS_SOURCE).to_crs(CRS_TARGET)
    com_lat, com_lon = rep.y.values, rep.x.values

    # capoluoghi: array (lat, lon) in radianti
    cap_lat, cap_lon = cap["lat"].values, cap["lon"].values
    cap_rad = np.radians(np.column_stack([cap_lat, cap_lon]))
    com_rad = np.radians(np.column_stack([com_lat, com_lon]))

    # nearest capoluogo (Voronoi) via BallTree haversine
    tree = BallTree(cap_rad, metric="haversine")
    dist_new_rad, idx = tree.query(com_rad, k=1)
    dist_new_km = dist_new_rad.ravel() * EARTH_RADIUS_KM
    nearest = idx.ravel()

    # distanza al capoluogo della provincia ATTUALE del comune
    cap_index_by_uts = pd.Series(np.arange(len(cap)), index=cap["cod_uts"])
    old_idx = comuni["COD_UTS"].map(cap_index_by_uts).values
    if np.isnan(old_idx).any():
        missing = comuni.loc[np.isnan(old_idx), "COMUNE"].tolist()
        raise RuntimeError(f"Comuni senza capoluogo noto per COD_UTS: {missing[:5]}")
    old_idx = old_idx.astype(int)
    dist_old_km = haversine_km(
        com_lat, com_lon, cap_lat[old_idx], cap_lon[old_idx]
    )

    # composizione attributi
    new_cod_uts = cap["cod_uts"].values[nearest]
    new_prov = cap["prov_name"].values[nearest]
    new_sigla = cap["sigla"].values[nearest]
    new_cap = cap["capoluogo"].values[nearest]
    new_reg = cap["cod_reg"].values[nearest]

    # nomi originali (province e regione) per tooltip
    prov_attr = prov[["COD_UTS", "DEN_UTS", "SIGLA"]].rename(
        columns={"DEN_UTS": "old_prov", "SIGLA": "old_sigla"}
    )
    reg_attr = reg[["COD_REG", "DEN_REG"]]

    out = comuni.copy()
    out = out.merge(prov_attr, on="COD_UTS", how="left").merge(reg_attr, on="COD_REG", how="left")
    out["new_cod_uts"] = new_cod_uts
    out["new_prov"] = new_prov
    out["new_sigla"] = new_sigla
    out["new_capoluogo"] = new_cap
    out["new_cod_reg"] = new_reg
    out["dist_new_km"] = np.round(dist_new_km, 2)
    out["dist_old_km"] = np.round(dist_old_km, 2)
    out["changed"] = new_cod_uts != out["COD_UTS"].values
    out["changed_region"] = new_reg != out["COD_REG"].values
    out["delta_km"] = np.round(dist_old_km - dist_new_km, 2)

    cols = [
        "PRO_COM", "COMUNE", "COD_REG", "DEN_REG",
        "COD_UTS", "old_prov", "old_sigla",
        "new_cod_uts", "new_prov", "new_sigla", "new_capoluogo", "new_cod_reg",
        "dist_new_km", "dist_old_km", "delta_km", "changed", "changed_region",
        "geometry",
    ]
    out = out[cols].to_crs(CRS_TARGET)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "comuni_assigned.geojson"
    out.to_file(out_path, driver="GeoJSON")

    # --- verifica ---
    print(f"Comuni assegnati: {len(out)}")
    print(f"Cambiano provincia: {int(out['changed'].sum())} ({out['changed'].mean()*100:.1f}%)")
    print(f"Cambiano regione (capoluogo in altra regione): {int(out['changed_region'].sum())} "
          f"({out['changed_region'].mean()*100:.1f}%)")
    # test Robbio
    r = out[out["COMUNE"] == "Robbio"].iloc[0]
    print(f"\n[Robbio] {r['old_prov']} ({r['old_sigla']}) -> {r['new_prov']} ({r['new_sigla']}) | "
          f"dist_old={r['dist_old_km']}km dist_new={r['dist_new_km']}km changed_region={r['changed_region']}")
    ok = r["new_prov"] == "Vercelli"
    print(f"  test Robbio->Vercelli: {'PASS' if ok else 'FAIL'}")
    # ogni capoluogo è assegnato a sé stesso? (dist_new ≈ 0)
    cap_names = cap[["cod_uts", "capoluogo"]].rename(columns={"cod_uts": "COD_UTS", "capoluogo": "COMUNE"})
    cap_rows = out.merge(cap_names, on=["COMUNE", "COD_UTS"], how="inner")
    self_ok = (cap_rows["new_cod_uts"] == cap_rows["COD_UTS"]).all()
    print(f"\n[check] {len(cap_rows)} capoluoghi auto-assegnati alla propria provincia: "
          f"{'PASS' if self_ok else 'FAIL'}")

    # top spostamenti (delta_km positivo grande, changed True)
    top = out[out["changed"]].nlargest(8, "delta_km")[
        ["COMUNE", "old_prov", "new_prov", "dist_old_km", "dist_new_km", "delta_km"]
    ]
    print("\nTop spostamenti (risparmio km al capoluogo):")
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
