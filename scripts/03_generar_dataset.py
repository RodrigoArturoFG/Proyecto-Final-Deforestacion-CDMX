"""
03_generar_dataset.py
=====================
Genera los datasets de entrenamiento .ppm para el clasificador kNN.
Lee WorldCover y Sentinel-2 en memoria, extrae parches 16x16,
y los guarda como .ppm en las carpetas forest/ y deforestation/.

Este script solo se ejecuta UNA VEZ para preparar el entrenamiento.

Uso:
    python scripts/03_generar_dataset.py
"""

import random
import numpy as np
import rasterio
from pathlib import Path
from typing import Tuple, List
from dataclasses import dataclass

from config import PATHS, CONFIG


# ── ESTRUCTURAS ───────────────────────────────────────────────
@dataclass
class Parche:
    """Parche de imagen RGB de 16x16 píxeles con su clase."""
    datos: np.ndarray
    clase: str
    fila: int
    col: int


# ── GUARDAR COMO PPM ──────────────────────────────────────────
def guardar_ppm(parche: np.ndarray, ruta: Path) -> None:
    """Guarda un array NumPy (H x W x 3, uint8) como archivo .ppm texto plano."""
    h, w, _ = parche.shape
    with open(ruta, "w") as f:
        f.write("P3\n")
        f.write(f"{w} {h}\n")
        f.write("255\n")
        for fila in parche:
            for r, g, b in fila:
                f.write(f"{int(r)} {int(g)} {int(b)} ")
            f.write("\n")


# ── NORMALIZAR BANDA SENTINEL-2 A 0-255 ──────────────────────
def normalizar_banda(banda: np.ndarray) -> np.ndarray:
    """Convierte una banda Sentinel-2 de uint16 a uint8 (0-255)."""
    banda_clip = np.clip(banda, 0, 3000)
    return ((banda_clip / 3000.0) * 255).astype(np.uint8)


# ── ENCONTRAR POSICIONES POR CLASE EN WORLDCOVER ─────────────
def encontrar_posiciones(
    worldcover_data: np.ndarray,
    clases: set,
    tamano_parche: int,
    margen: int = 5
) -> List[Tuple[int, int]]:
    """Encuentra posiciones válidas en WorldCover para una clase dada."""
    h, w = worldcover_data.shape
    mitad = tamano_parche // 2
    borde = mitad + margen

    mascara = np.isin(worldcover_data, list(clases))
    mascara[:borde, :]  = False
    mascara[-borde:, :] = False
    mascara[:, :borde]  = False
    mascara[:, -borde:] = False

    filas, cols = np.where(mascara)
    return list(zip(filas.tolist(), cols.tolist()))


# ── EXTRAER PARCHE RGB ────────────────────────────────────────
def extraer_parche_rgb(
    sentinel_rgb: np.ndarray,
    fila: int,
    col: int,
    tamano: int
) -> np.ndarray:
    """Extrae un parche cuadrado de la imagen RGB en la posición dada."""
    mitad = tamano // 2
    return sentinel_rgb[fila - mitad : fila + mitad,
                        col  - mitad : col  + mitad, :]


# ── MAIN ──────────────────────────────────────────────────────
def main() -> None:
    """Genera los datasets de entrenamiento .ppm."""
    random.seed(CONFIG["semilla"])
    np.random.seed(CONFIG["semilla"])

    tamano_parche = CONFIG["block_size"]
    n_muestras    = CONFIG["n_muestras"]

    print("=" * 60)
    print("GENERACIÓN DE DATASET DE ENTRENAMIENTO")
    print(f"  Parches: {tamano_parche}x{tamano_parche} px")
    print(f"  Muestras por clase: {n_muestras}")
    print(f"  Destino bosque:    {PATHS['forest_dir']}")
    print(f"  Destino no-bosque: {PATHS['deforest_dir']}")
    print("=" * 60)

    # ── PASO 1: Cargar todo en memoria ────────────────────────
    print("\n[1/4] Cargando imágenes en memoria...")

    with rasterio.open(PATHS["sentinel_2015"]) as src:
        b4 = normalizar_banda(src.read(1).astype(np.float32))
        b3 = normalizar_banda(src.read(2).astype(np.float32))
        b2 = normalizar_banda(src.read(3).astype(np.float32))

    sentinel_rgb = np.stack([b4, b3, b2], axis=2)
    print(f"  Sentinel-2 2015: {sentinel_rgb.shape} — {sentinel_rgb.nbytes / 1e6:.1f} MB en RAM")

    with rasterio.open(PATHS["worldcover"]) as src:
        worldcover_data = src.read(1)

    print(f"  WorldCover:      {worldcover_data.shape} — {worldcover_data.nbytes / 1e6:.1f} MB en RAM")

    # ── PASO 2: Encontrar posiciones válidas ──────────────────
    print("\n[2/4] Buscando posiciones de muestreo en WorldCover...")

    posiciones_bosque   = encontrar_posiciones(worldcover_data, CONFIG["clases_bosque"],   tamano_parche)
    posiciones_nobosque = encontrar_posiciones(worldcover_data, CONFIG["clases_nobosque"], tamano_parche)

    print(f"  Posiciones bosque disponibles:    {len(posiciones_bosque):,}")
    print(f"  Posiciones no-bosque disponibles: {len(posiciones_nobosque):,}")

    if len(posiciones_bosque) < n_muestras or len(posiciones_nobosque) < n_muestras:
        raise ValueError(
            f"No hay suficientes posiciones. Reduce n_muestras en config.py o amplía la región en GEE."
        )

    muestras_bosque   = random.sample(posiciones_bosque,   n_muestras)
    muestras_nobosque = random.sample(posiciones_nobosque, n_muestras)

    # ── PASO 3: Extraer y guardar parches .ppm ────────────────
    print(f"\n[3/4] Generando {n_muestras} parches de BOSQUE...")
    for i, (fila, col) in enumerate(muestras_bosque):
        parche = extraer_parche_rgb(sentinel_rgb, fila, col, tamano_parche)
        guardar_ppm(parche, PATHS["forest_dir"] / f"forest_{i:04d}.ppm")

    print(f"[4/4] Generando {n_muestras} parches de NO-BOSQUE...")
    for i, (fila, col) in enumerate(muestras_nobosque):
        parche = extraer_parche_rgb(sentinel_rgb, fila, col, tamano_parche)
        guardar_ppm(parche, PATHS["deforest_dir"] / f"deforestation_{i:04d}.ppm")

    # ── RESUMEN ───────────────────────────────────────────────
    archivos_bosque   = len(list(PATHS["forest_dir"].glob("*.ppm")))
    archivos_nobosque = len(list(PATHS["deforest_dir"].glob("*.ppm")))

    print("\n" + "=" * 60)
    print("DATASET GENERADO:")
    print(f"  {PATHS['forest_dir']}/   → {archivos_bosque} archivos .ppm")
    print(f"  {PATHS['deforest_dir']}/ → {archivos_nobosque} archivos .ppm")
    print(f"  Total: {archivos_bosque + archivos_nobosque} muestras de entrenamiento")
    print("\n  Siguiente paso: python scripts/02_pipeline.py")
    print("=" * 60)


if __name__ == "__main__":
    main()