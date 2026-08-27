"""Dissolve i comuni nelle NUOVE province e produce i layer per la mappa.

Output in data/processed/:
  - new_provinces.geojson : 110 province ridisegnate (dissolve su new_cod_uts)
  - old_provinces.geojson : 110 province ISTAT attuali (riferimento)
  - regioni.geojson       : 20 regioni ISTAT (sfondo invariato)
  - province_stats.csv    : statistiche per provincia (n_comuni, cambi, area)
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROV_SHP, REG_SHP, DATA_PROCESSED, CRS_SOURCE, CRS_TARGET


def main() -> None:
    com = gpd.read_file(DATA_PROCESSED / "comuni_assigned.geojson")  # 4326

    # --- nuove province (dissolve su new_cod_uts) ---
    com["n"] = 1
    com["n_changed"] = com["changed"].astype(int)
    com["n_changed_reg"] = com["changed_region"].astype(int)

    agg = {
        "new_prov": "first",
        "new_sigla": "first",
        "new_capoluogo": "first",
        "new_cod_reg": "first",
        "DEN_REG": lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0],  # regione dominante (per i casi cross-region)
        "n": "sum",
        "n_changed": "sum",
        "n_changed_reg": "sum",
    }
    new_prov = com.dissolve(by="new_cod_uts", aggfunc=agg).reset_index()
    new_prov = new_prov.rename(columns={"n": "n_comuni", "DEN_REG": "dominant_reg"})
    new_prov["pct_changed"] = (100 * new_prov["n_changed"] / new_prov["n_comuni"]).round(1)

    # area in km² (riproiettando in UTM32N metrico)
    new_prov_area = new_prov.to_crs(CRS_SOURCE)
    new_prov["area_km2"] = (new_prov_area.geometry.area / 1e6).round(0)
    new_prov = new_prov.to_crs(CRS_TARGET)

    cols = [
        "new_cod_uts", "new_prov", "new_sigla", "new_capoluogo", "new_cod_reg",
        "dominant_reg", "n_comuni", "n_changed", "n_changed_reg", "pct_changed",
        "area_km2", "geometry",
    ]
    new_prov = new_prov[cols]
    new_prov.to_file(DATA_PROCESSED / "new_provinces.geojson", driver="GeoJSON")

    # --- province attuali (riferimento) ---
    old = gpd.read_file(PROV_SHP, encoding="utf-8").to_crs(CRS_TARGET)
    old_area = old.to_crs(CRS_SOURCE)
    old["area_km2"] = (old_area.geometry.area / 1e6).round(0)
    old = old[["COD_UTS", "DEN_UTS", "SIGLA", "TIPO_UTS", "area_km2", "geometry"]]
    old = old.rename(columns={"COD_UTS": "cod_uts", "DEN_UTS": "prov_name", "SIGLA": "sigla"})
    old.to_file(DATA_PROCESSED / "old_provinces.geojson", driver="GeoJSON")

    # --- regioni ---
    reg = gpd.read_file(REG_SHP, encoding="utf-8").to_crs(CRS_TARGET)
    reg = reg[["COD_REG", "DEN_REG", "geometry"]].rename(
        columns={"COD_REG": "cod_reg", "DEN_REG": "reg_name"}
    )
    reg.to_file(DATA_PROCESSED / "regioni.geojson", driver="GeoJSON")

    # --- statistiche ---
    stats = new_prov.drop(columns="geometry").sort_values("n_comuni", ascending=False)
    stats.to_csv(DATA_PROCESSED / "province_stats.csv", index=False)

    print(f"Nuove province: {len(new_prov)}")
    print(f"Province attuali: {len(old)}")
    print(f"Regioni: {len(reg)}")
    print(f"\nTop 10 nuove province per n° comuni:")
    print(stats.head(10)[["new_prov", "new_sigla", "n_comuni", "n_changed", "pct_changed", "area_km2"]].to_string(index=False))
    print(f"\nTop 10 province che più si 'espandono' (n_comuni):")
    # confronto n_comuni nuovo vs area province attuali
    old_n = old.groupby("cod_uts")["sigla"].count()  # sempre 1, solo per struttura
    print(stats.nlargest(10, "n_comuni")[["new_prov", "new_sigla", "n_comuni", "area_km2"]].to_string(index=False))
    # province a maggioranza cross-regione
    cross = new_prov[new_prov["n_changed_reg"] > 0].nlargest(8, "n_changed_reg")[
        ["new_prov", "new_sigla", "n_comuni", "n_changed_reg", "dominant_reg"]
    ]
    print(f"\nProvince con più comuni in altra regione (capoluogo cross-regione):")
    print(cross.to_string(index=False))


if __name__ == "__main__":
    main()
