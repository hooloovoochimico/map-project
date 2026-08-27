"""Percorsi e costanti condivisi del progetto."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUTS = PROJECT_ROOT / "outputs"
ROOT = PROJECT_ROOT

# Sorgente ISTAT: confini amministrativi generalizzati al 1 gen 2026 (WGS84 UTM32N)
ISTAT_YEAR = 2026
ISTAT_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi/"
    f"generalizzati/{ISTAT_YEAR}/Limiti0101{ISTAT_YEAR}_g.zip"
)
ZIP_PATH = DATA_RAW / f"Limiti0101{ISTAT_YEAR}_g.zip"

# Layer estratti (nomi di cartella/file come da zip ISTAT)
COMUNI_SHP = DATA_RAW / f"Com0101{ISTAT_YEAR}_g" / f"Com0101{ISTAT_YEAR}_g_WGS84.shp"
PROV_SHP = DATA_RAW / f"ProvCM0101{ISTAT_YEAR}_g" / f"ProvCM0101{ISTAT_YEAR}_g_WGS84.shp"
REG_SHP = DATA_RAW / f"Reg0101{ISTAT_YEAR}_g" / f"Reg0101{ISTAT_YEAR}_g_WGS84.shp"

# CRS: sorgente ISTAT in UTM32N; lavoriamo in 4326 (lat/lon WGS84) per haversine e web map
CRS_SOURCE = "EPSG:32632"
CRS_TARGET = "EPSG:4326"

# Override capoluoghi per le 8 UTS a capoluogo multiplo (province a nome composto /
# liberi consorzi). Scegliamo il capoluogo effettivo / sede prefettizia.
MULTI_CAPOLUOGO = {
    40: "Forlì",        # Forlì-Cesena
    41: "Pesaro",       # Pesaro-Urbino
    45: "Massa",        # Massa-Carrara
    110: "Barletta",    # Barletta-Andria-Trani (nessun capoluogo ufficiale, scelto Barletta)
    113: "Olbia",       # Olbia-Tempio
    116: "Lanusei",     # Ogliastra
    117: "Villacidro",  # Medio Campidano
    119: "Carbonia",    # Carbonia-Iglesias
}
