"""
config.py
=========
Rutas absolutas del proyecto calculadas dinámicamente desde la ubicación
de este archivo. Importar en todos los scripts para garantizar que las
rutas funcionen independientemente del directorio de ejecución.

Uso:
    from config import PATHS
    imagen = rasterio.open(PATHS["sentinel_2015"])
"""

import os
from pathlib import Path

# Directorio de este archivo: .../Proyecto-Final-Deforestacion-CDMX/scripts/
SCRIPTS_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# Raíz del proyecto: .../Proyecto-Final-Deforestacion-CDMX/
ROOT_DIR = SCRIPTS_DIR.parent

# ── Directorios principales ───────────────────────────────────
DATA_RAW_DIR     = ROOT_DIR / "data" / "raw"
DATA_OUTPUTS_DIR = ROOT_DIR / "data" / "outputs"
FOREST_DIR       = ROOT_DIR / "forest"
DEFOREST_DIR     = ROOT_DIR / "deforestation"

# Crear directorios si no existen
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
FOREST_DIR.mkdir(exist_ok=True)
DEFOREST_DIR.mkdir(exist_ok=True)

# ── Archivos de entrada ───────────────────────────────────────
PATHS = {
    # Imágenes Sentinel-2
    "sentinel_2015":   DATA_RAW_DIR / "sentinel2_cdmx_2015.tif",
    "sentinel_actual": DATA_RAW_DIR / "sentinel2_cdmx_actual.tif",
    "worldcover":      DATA_RAW_DIR / "worldcover_cdmx.tif",

    # Shapefile alcaldías INEGI
    "alcaldias_shp":   DATA_RAW_DIR / "alcaldias_cdmx.shp",

    # Credenciales Google Drive
    "credentials":     ROOT_DIR / "credentials.json",
    "token":           ROOT_DIR / "token.json",

    # Carpetas dataset de entrenamiento kNN
    "forest_dir":      FOREST_DIR,
    "deforest_dir":    DEFOREST_DIR,

    # Archivos de salida
    "output_2015":         DATA_OUTPUTS_DIR / "output_2015.ppm",
    "output_actual":       DATA_OUTPUTS_DIR / "output_actual.ppm",
    "mapa_png":            DATA_OUTPUTS_DIR / "mapa_deforestacion.png",
    "reporte_csv":         DATA_OUTPUTS_DIR / "reporte_alcaldias.csv",
}

# ── Parámetros del pipeline ───────────────────────────────────
CONFIG = {
    "k_value":          16,   # Vecinos del clasificador kNN
    "block_size":       16,   # Tamaño de bloque en px (igual al tamaño de los .ppm)
    "min_area_px":      10,   # Área mínima de parche (10 px = 0.1 ha)
    "n_muestras":       300,  # Muestras por clase para el dataset de entrenamiento
    "semilla":          42,   # Semilla aleatoria para reproducibilidad
    "drive_folder":     "deforestacion_cdmx",  # Nombre de la carpeta en Google Drive
    "drive_files": [          # Archivos a descargar de Drive
        "sentinel2_cdmx_2015.tif",
        "sentinel2_cdmx_actual.tif",
        "worldcover_cdmx.tif",
    ],
    # Clases WorldCover
    "clases_bosque":    {10},            # Tree cover
    "clases_nobosque":  {30, 40, 50, 60} # Grassland, Cropland, Built-up, Bare
}
