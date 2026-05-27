"""
02_pipeline.py
==============
Pipeline principal de detección de deforestación.
Lee los GeoTIFFs UNA SOLA VEZ y procesa TODO en memoria RAM.
Solo escribe en disco los resultados finales en data/outputs/.

Uso:
    python scripts/02_pipeline.py
"""

import sys
import csv
from math import sqrt
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field

import numpy as np
import rasterio
import rasterio.mask
import geopandas as gpd
from skimage import morphology, measure
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from config import PATHS, CONFIG


# ── ESTRUCTURAS ───────────────────────────────────────────────
@dataclass
class ResultadoAlcaldia:
    nombre: str
    area_bosque_2015_ha: float
    area_perdida_ha: float
    porcentaje_perdida: float
    n_parches: int

@dataclass
class PipelineState:
    rgb_2015:              Optional[np.ndarray] = None
    rgb_actual:            Optional[np.ndarray] = None
    transform:             Optional[object]     = None
    crs:                   Optional[object]     = None
    dataset:               List[List]           = field(default_factory=list)
    mascara_bosque_2015:   Optional[np.ndarray] = None
    mascara_bosque_actual: Optional[np.ndarray] = None
    mascara_perdida:       Optional[np.ndarray] = None
    mascara_refinada:      Optional[np.ndarray] = None
    etiquetas:             Optional[np.ndarray] = None
    resultados_alcaldias:  List[ResultadoAlcaldia] = field(default_factory=list)


# ── MÓDULO 1: CARGA EN MEMORIA ────────────────────────────────
def cargar_imagen_en_memoria(ruta) -> Tuple[np.ndarray, object, object]:
    """Carga un GeoTIFF Sentinel-2 completamente en RAM como array RGB uint8."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"GeoTIFF no encontrado: {ruta}\n"
            f"Ejecuta primero: python scripts/01_descarga_drive.py"
        )

    with rasterio.open(ruta) as src:
        b4 = src.read(1).astype(np.float32)
        b3 = src.read(2).astype(np.float32)
        b2 = src.read(3).astype(np.float32)
        transform = src.transform
        crs = src.crs

    def norm(banda):
        return (np.clip(banda, 0, 3000) / 3000 * 255).astype(np.uint8)

    rgb = np.stack([norm(b4), norm(b3), norm(b2)], axis=2)
    print(f"  [{ruta.name}] {rgb.shape} — {rgb.nbytes / 1e6:.1f} MB en RAM")
    return rgb, transform, crs


# ── MÓDULO 2: DATASET KNN EN MEMORIA ─────────────────────────
def cargar_dataset_knn(carpeta_f, carpeta_d) -> List[List]:
    """Carga todos los .ppm de entrenamiento en memoria como lista de vectores RGB."""
    dataset: List[List] = []

    for carpeta, clase in [(carpeta_f, 'f'), (carpeta_d, 'd')]:
        for archivo in sorted(carpeta.glob("*.ppm")):
            with open(archivo, 'r') as f:
                datos = f.read().replace('\n', ' ').split()
            valores = [int(x) for x in datos[4:]]
            r = valores[0::3]
            g = valores[1::3]
            b = valores[2::3]
            dataset.append([sum(r)/len(r), sum(g)/len(g), sum(b)/len(b), clase])

    return dataset


# ── MÓDULO 3: CLASIFICACIÓN KNN EN MEMORIA ───────────────────
def distancia_euclidiana(a: Tuple, b: List) -> float:
    return sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)


def clasificar_imagen_en_memoria(
    rgb: np.ndarray,
    dataset: List[List],
    k: int,
    block_size: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Clasifica una imagen RGB en bloques usando kNN, completamente en memoria."""
    h, w, _ = rgb.shape
    h_crop = (h // block_size) * block_size
    w_crop = (w // block_size) * block_size
    rgb = rgb[:h_crop, :w_crop]

    mascara_bosque   = np.zeros((h_crop, w_crop), dtype=bool)
    imagen_resultado = rgb.copy()

    k_adj = k - 1 if k % 2 == 0 else k
    k_adj = max(1, k_adj)

    total_bloques = (h_crop // block_size) * (w_crop // block_size)
    bloque_actual = 0

    for fila in range(0, h_crop, block_size):
        for col in range(0, w_crop, block_size):
            bloque = rgb[fila:fila+block_size, col:col+block_size]
            avg = (float(bloque[:,:,0].mean()), float(bloque[:,:,1].mean()), float(bloque[:,:,2].mean()))

            distancias = sorted(
                [(distancia_euclidiana(avg, item), item[3]) for item in dataset],
                key=lambda x: x[0]
            )

            votos_f = sum(1 for _, c in distancias[:k_adj] if c == 'f')
            votos_d = sum(1 for _, c in distancias[:k_adj] if c == 'd')

            if votos_f >= votos_d:
                mascara_bosque[fila:fila+block_size, col:col+block_size] = True
            else:
                imagen_resultado[fila:fila+block_size, col:col+block_size] = [255, 0, 0]

            bloque_actual += 1
            if bloque_actual % 500 == 0:
                print(f"    Progreso: {bloque_actual/total_bloques*100:.1f}% ({bloque_actual}/{total_bloques})", end='\r')

    print()
    return mascara_bosque, imagen_resultado


# ── MÓDULO 4: DIFERENCIA TEMPORAL ────────────────────────────
def calcular_mascara_perdida(bosque_2015, bosque_actual) -> np.ndarray:
    return bosque_2015 & ~bosque_actual


# ── MÓDULO 5: MORFOLOGÍA ──────────────────────────────────────
def refinar_mascara(mascara: np.ndarray) -> np.ndarray:
    mascara_limpia   = morphology.binary_opening(mascara, morphology.square(3))
    mascara_refinada = morphology.binary_closing(mascara_limpia, morphology.square(5))
    return mascara_refinada


# ── MÓDULO 6: COMPONENTES CONECTADOS ─────────────────────────
def etiquetar_componentes(mascara, min_area_px) -> Tuple[np.ndarray, List[Dict]]:
    etiquetas    = measure.label(mascara, connectivity=2)
    propiedades  = measure.regionprops(etiquetas)
    stats        = []

    for prop in propiedades:
        if prop.area < min_area_px:
            etiquetas[etiquetas == prop.label] = 0
            continue
        stats.append({
            "id":             prop.label,
            "area_ha":        round(prop.area * 0.01, 4),
            "centroide_fila": int(prop.centroid[0]),
            "centroide_col":  int(prop.centroid[1]),
        })

    return etiquetas, stats


# ── MÓDULO 7: REPORTE POR ALCALDÍA ───────────────────────────
def calcular_reporte_alcaldias(
    mascara_bosque_2015, mascara_perdida, transform, crs
) -> List[ResultadoAlcaldia]:

    if not PATHS["alcaldias_shp"].exists():
        print(f"  [!] Shapefile no encontrado: {PATHS['alcaldias_shp']}")
        print("      Generando reporte global (sin desglose por alcaldía)...")
        area_bosque_ha  = float(mascara_bosque_2015.sum()) * 0.01
        area_perdida_ha = float(mascara_perdida.sum()) * 0.01
        pct = (area_perdida_ha / area_bosque_ha * 100) if area_bosque_ha > 0 else 0
        return [ResultadoAlcaldia("CDMX (total)", round(area_bosque_ha, 2),
                                  round(area_perdida_ha, 2), round(pct, 2), 0)]

    alcaldias  = gpd.read_file(PATHS["alcaldias_shp"]).to_crs(crs)
    resultados = []

    for _, alcaldia in alcaldias.iterrows():
        nombre = alcaldia.get("NOMGEO") or alcaldia.get("NOM_MUN") or "Desconocida"

        from rasterio.features import geometry_mask
        geom       = [alcaldia.geometry.__geo_interface__]
        mascara_geo = ~geometry_mask(geom, transform=transform, invert=False,
                                     out_shape=mascara_bosque_2015.shape)

        bosque_en_alcaldia  = mascara_bosque_2015 & mascara_geo
        perdida_en_alcaldia = mascara_perdida      & mascara_geo

        area_bosque_ha  = float(bosque_en_alcaldia.sum())  * 0.01
        area_perdida_ha = float(perdida_en_alcaldia.sum()) * 0.01
        pct = (area_perdida_ha / area_bosque_ha * 100) if area_bosque_ha > 0 else 0.0

        etq_alcaldia = measure.label(perdida_en_alcaldia, connectivity=2)
        resultados.append(ResultadoAlcaldia(
            nombre, round(area_bosque_ha, 2), round(area_perdida_ha, 2),
            round(pct, 2), int(etq_alcaldia.max())
        ))

    return sorted(resultados, key=lambda r: r.porcentaje_perdida, reverse=True)


# ── MÓDULO 8: GUARDAR OUTPUTS FINALES ────────────────────────
def guardar_ppm(imagen: np.ndarray, ruta) -> None:
    h, w, _ = imagen.shape
    with open(ruta, 'w') as f:
        f.write(f"P3\n{w} {h}\n255\n")
        for fila in imagen:
            for r, g, b in fila:
                f.write(f"{int(r)} {int(g)} {int(b)} ")
            f.write("\n")


def guardar_mapa(rgb_actual, mascara_perdida, ruta) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    imagen_vis = rgb_actual.copy()
    h, w = mascara_perdida.shape
    imagen_vis = imagen_vis[:h, :w]
    imagen_vis[mascara_perdida, 0] = 255
    imagen_vis[mascara_perdida, 1] = 0
    imagen_vis[mascara_perdida, 2] = 0
    axes[0].imshow(imagen_vis)
    axes[0].set_title("Zonas Deforestadas Detectadas (rojo)", fontsize=13)
    axes[0].axis('off')
    axes[0].legend(handles=[mpatches.Patch(color='red', label='Área deforestada')],
                   loc='lower right', fontsize=10)
    axes[1].imshow(mascara_perdida, cmap='Reds')
    axes[1].set_title("Máscara de Pérdida de Cobertura Forestal", fontsize=13)
    axes[1].axis('off')
    plt.suptitle("Sistema de Detección de Deforestación CDMX\n"
                 "Análisis Multitemporal Sentinel-2 (2015 → Actual) + kNN",
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(ruta, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  [✓] Mapa guardado: {ruta}")


def guardar_csv(resultados: List[ResultadoAlcaldia], ruta) -> None:
    with open(ruta, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Alcaldía", "Bosque 2015 (ha)", "Área Perdida (ha)", "% Pérdida", "N° Parches"])
        for r in resultados:
            writer.writerow([r.nombre, r.area_bosque_2015_ha, r.area_perdida_ha,
                             r.porcentaje_perdida, r.n_parches])
    print(f"  [✓] CSV guardado: {ruta}")


# ── PIPELINE PRINCIPAL ────────────────────────────────────────
def main() -> None:
    estado = PipelineState()

    print("=" * 60)
    print("PIPELINE DE DETECCIÓN DE DEFORESTACIÓN — CDMX")
    print("Todo el procesamiento ocurre en memoria RAM")
    print("=" * 60)

    # ETAPA 1: Carga desde disco
    print("\n[ETAPA 1/7] Cargando GeoTIFFs en memoria...")
    estado.rgb_2015,   estado.transform, estado.crs = cargar_imagen_en_memoria(PATHS["sentinel_2015"])
    estado.rgb_actual, _,                _           = cargar_imagen_en_memoria(PATHS["sentinel_actual"])

    # ETAPA 2: Dataset kNN
    print("\n[ETAPA 2/7] Cargando dataset kNN en memoria...")
    if not any(PATHS["forest_dir"].glob("*.ppm")):
        print("  [!] Dataset no encontrado. Ejecuta: python scripts/03_generar_dataset.py")
        sys.exit(1)

    estado.dataset = cargar_dataset_knn(PATHS["forest_dir"], PATHS["deforest_dir"])
    n_f = sum(1 for x in estado.dataset if x[3] == 'f')
    n_d = sum(1 for x in estado.dataset if x[3] == 'd')
    print(f"  Dataset: {len(estado.dataset)} muestras ({n_f} bosque + {n_d} no-bosque)")

    k = CONFIG["k_value"]
    bs = CONFIG["block_size"]

    # ETAPA 3: Clasificación kNN
    print(f"\n[ETAPA 3/7] Clasificando con kNN (k={k}, bloque={bs}px)...")
    print("  Clasificando imagen 2015...")
    estado.mascara_bosque_2015, img_2015 = clasificar_imagen_en_memoria(estado.rgb_2015, estado.dataset, k, bs)
    print("  Clasificando imagen actual...")
    estado.mascara_bosque_actual, img_actual = clasificar_imagen_en_memoria(estado.rgb_actual, estado.dataset, k, bs)

    # ETAPA 4: Diferencia temporal
    print("\n[ETAPA 4/7] Calculando máscara de pérdida...")
    h = min(estado.mascara_bosque_2015.shape[0], estado.mascara_bosque_actual.shape[0])
    w = min(estado.mascara_bosque_2015.shape[1], estado.mascara_bosque_actual.shape[1])
    estado.mascara_perdida = calcular_mascara_perdida(
        estado.mascara_bosque_2015[:h, :w], estado.mascara_bosque_actual[:h, :w]
    )
    print(f"  Pérdida total detectada: {float(estado.mascara_perdida.sum()) * 0.01:.1f} ha")

    # ETAPA 5: Morfología
    print("\n[ETAPA 5/7] Refinamiento morfológico...")
    estado.mascara_refinada = refinar_mascara(estado.mascara_perdida)
    print(f"  Área refinada: {float(estado.mascara_refinada.sum()) * 0.01:.1f} ha")

    # ETAPA 6: Componentes conectados
    print("\n[ETAPA 6/7] Etiquetando componentes conectados...")
    estado.etiquetas, stats = etiquetar_componentes(estado.mascara_refinada, CONFIG["min_area_px"])
    print(f"  Parches detectados: {len(stats)}")

    # ETAPA 7: Reporte por alcaldía
    print("\n[ETAPA 7/7] Calculando reporte por alcaldía...")
    estado.resultados_alcaldias = calcular_reporte_alcaldias(
        estado.mascara_bosque_2015[:h, :w], estado.mascara_refinada,
        estado.transform, estado.crs
    )

    # Escritura final
    print("\n[OUTPUT] Guardando resultados en disco...")
    guardar_ppm(img_2015[:h, :w],    PATHS["output_2015"])
    guardar_ppm(img_actual[:h, :w],  PATHS["output_actual"])
    guardar_mapa(estado.rgb_actual,  estado.mascara_refinada, PATHS["mapa_png"])
    guardar_csv(estado.resultados_alcaldias, PATHS["reporte_csv"])

    # Resumen
    print("\n" + "=" * 60)
    print(f"  {'Alcaldía':<25} {'Bosque 2015':>12} {'Perdido':>10} {'%':>8}")
    print(f"  {'-'*25} {'-'*12} {'-'*10} {'-'*8}")
    for r in estado.resultados_alcaldias[:8]:
        print(f"  {r.nombre:<25} {r.area_bosque_2015_ha:>10.1f}ha "
              f"{r.area_perdida_ha:>8.1f}ha {r.porcentaje_perdida:>7.1f}%")
    print(f"\n  Resultados en: {PATHS['reporte_csv'].parent.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()