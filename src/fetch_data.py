"""Scarica ed estrae i confini amministrativi ISTAT (versione generalizzata)."""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_RAW, ISTAT_URL, ZIP_PATH, COMUNI_SHP, PROV_SHP, REG_SHP


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"[skip] già presente: {dest.name}")
        return
    print(f"[download] {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"  salvato {dest.stat().st_size / 1e6:.1f} MB")


def extract(zip_path: Path) -> None:
    import zipfile

    marker = COMUNI_SHP
    if marker.exists():
        print(f"[skip] già estratto: {marker.relative_to(DATA_RAW)}")
        return
    print(f"[extract] {zip_path.name}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(DATA_RAW)


def verify() -> None:
    import geopandas as gpd

    for name, path in [("Comuni", COMUNI_SHP), ("Province", PROV_SHP), ("Regioni", REG_SHP)]:
        gdf = gpd.read_file(path, encoding="utf-8")
        print(f"  {name}: {len(gdf)} feature, CRS={gdf.crs.to_string()}")


def main() -> None:
    download(ISTAT_URL, ZIP_PATH)
    extract(ZIP_PATH)
    print("[verify]")
    verify()
    print("OK: dati pronti in", DATA_RAW)


if __name__ == "__main__":
    main()
