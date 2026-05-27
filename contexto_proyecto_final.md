# CONTEXTO — PROYECTO FINAL ANÁLISIS DE IMÁGENES
**Institución:** ESCOM-IPN · Ingeniería en Sistemas Computacionales · Grupo 7CM3
**Asignatura:** Análisis de Imágenes / Visión por Computadora
**Profesora:** M. en C. María Elena Cruz Meza
**Repo:** https://github.com/RodrigoArturoFG/Proyecto-Final-Deforestacion-CDMX

---

## PROYECTO: Sistema de Detección de Deforestación en la CDMX

**Descripción corta:** Análisis multitemporal de imágenes Sentinel-2 (2015 vs. actual) sobre la Ciudad de México, usando un clasificador kNN para detectar pérdida de cobertura forestal por alcaldía.

**ODS principal:** ODS 15 (Vida de Ecosistemas Terrestres) — indicador 15n.2.1 (Tasa de deforestación)
**ODS secundarios:** ODS 13 (indicador 13n.3.1), ODS 16 (indicadores 16.3.2, 16.6.2, 16n.5.1)

**Región:** Ciudad de México, desagregado por las 16 alcaldías (shapefile INEGI).
**Equipo:** ~10 integrantes con roles definidos (ver documento de actividades).

**Documentos de referencia en la raíz del proyecto:**
- `Proyecto_Final_Deforestacion_CDMX.docx` — Justificación, objetivos, algoritmo, roles y cronograma completos.
- `Actividades_por_Rol_Proyecto_Deforestacion.docx` — Actividades detalladas por cada uno de los 10 roles.
- `Flujo_Pipeline_Deforestacion_CDMX.docx` — Descripción técnica detallada del pipeline y decisiones de diseño.

---

## STACK TECNOLÓGICO

**Lenguaje:** Python 3.10+
**Librerías:**
```
rasterio==1.3.10       # lectura GeoTIFF
numpy==1.26.4          # operaciones en memoria
geopandas==0.14.4      # shapefile alcaldías
scikit-image==0.22.0   # morfología, componentes conectados, GLCM
opencv-python==4.9.0.80
matplotlib==3.8.4
google-auth==2.29.0
google-auth-oauthlib==1.2.0
google-api-python-client==2.126.0
tqdm==4.66.2
```
Instalar con: `pip install -r requirements.txt`

---

## ESTRUCTURA DEL PROYECTO

```
Proyecto-Final-Deforestacion-CDMX/
├── scripts/
│   ├── config.py                  # Rutas absolutas y parámetros centralizados
│   ├── 00_gee_export.js
│   └── 01_descarga_drive.py
│   └── 02_pipeline.py
│   └── 03_generar_dataset.py
├── requirements.txt
├── credentials.json           # No incluido en el repo (agregar a .gitignore)
├── contexto_SIODS.md          # Referencia completa de indicadores SIODS y Agenda 2030
├── how_to_clone_vs_code.md    # Guía de clonado y configuración para VS Code
├── data/
│   ├── raw/                   # GeoTIFFs + shapefile INEGI
│   └── outputs/               # Resultados generados
├── forest/                    # Dataset entrenamiento — bosque
└── deforestation/             # Dataset entrenamiento — no bosque
```

> `.gitignore` debe incluir: `credentials.json`, `token.json`, `data/raw/*.tif`, `forest/`, `deforestation/`, `contexto_proyecto_final_AI.md`

---

## ORDEN DE EJECUCIÓN

```
1. scripts/00_gee_export.js      → pegar en code.earthengine.google.com, correr Tasks
2. python scripts/01_descarga_drive.py  → descarga única ~1 GB a data/raw/
3. python scripts/03_generar_dataset.py → genera 600 .ppm de entrenamiento (una vez)
4. python scripts/02_pipeline.py        → análisis completo → data/outputs/
```

---

## FUENTES DE DATOS

| Fuente | Qué aporta | Cómo se obtiene |
|---|---|---|
| Sentinel-2 L2A | Imágenes multiespectrales 10m/px (2015 y actual) | GEE → Drive → disco |
| ESA WorldCover 10m | Etiquetas bosque/no-bosque para entrenar kNN | GEE → Drive → disco |
| INEGI shapefile alcaldías | Polígonos de las 16 alcaldías CDMX | Descarga manual INEGI |

**GeoTIFF es el formato de almacenamiento** porque: (1) georeferenciación embebida (CRS + affine transform), (2) soporta múltiples bandas en un archivo, (3) 16 bits sin pérdida, (4) formato nativo de GEE/Copernicus, (5) leído directamente por Rasterio/GDAL/GeoPandas.

---

## PIPELINE — RESUMEN TÉCNICO

**Principio clave:** los GeoTIFFs se leen UNA SOLA VEZ a RAM. Todo el procesamiento intermedio ocurre en arrays NumPy en memoria. Solo se escribe en disco en 4 momentos concretos.

### Los 4 momentos de contacto con disco:
1. `01_descarga_drive.py` → escribe `data/raw/*.tif`
2. `03_generar_dataset.py` → lee `data/raw/*.tif` una vez; escribe `forest/*.ppm` y `deforestation/*.ppm`
3. `02_pipeline.py` inicio → lee `data/raw/*.tif` y `forest/deforestation/*.ppm` una vez
4. `02_pipeline.py` final → escribe 4 archivos en `data/outputs/`

### Etapas del pipeline en memoria (02_pipeline.py):

**Etapa 1 — Carga GeoTIFF → RAM**
- `rasterio.open()` + `src.read(1,2,3)` → bandas B4, B3, B2 como float32
- Normalizar 0–3000 → uint8 (0–255)
- Resultado: `rgb_2015` y `rgb_actual` como `ndarray (H, W, 3)` en RAM
- Guardar `transform` (Affine) y `crs` para uso en módulo GIS

**Etapa 2 — Dataset kNN en RAM**
- Leer 600 archivos `.ppm` de `forest/` y `deforestation/`
- Calcular `avg_R, avg_G, avg_B` por imagen → vector `[R, G, B, clase]`
- Resultado: lista de 600 vectores en RAM

**Etapa 3 — Clasificación kNN en memoria**
- Recorrer imagen en bloques `BLOCK_SIZE × BLOCK_SIZE` (default 16×16 px = 160×160 m en terreno)
- Por bloque: calcular `avg_R, avg_G, avg_B` → distancia euclidiana contra los 600 vectores → votar k=16 vecinos
- Resultado: `mascara_bosque_2015` y `mascara_bosque_actual` como `ndarray (H, W) bool`

> **¿Por qué 16×16 y no 8×8?** El clasificador promedia todos los píxeles del bloque. 16×16 = 256 píxeles promediados → promedio más estable y representativo que 8×8 (64 px). Cubre 160×160 m de terreno, granularidad adecuada para alcaldías de la CDMX. El tamaño del bloque de entrenamiento y `BLOCK_SIZE` de clasificación deben ser iguales.

**Etapa 4 — Diferencia temporal**
- `mascara_perdida = mascara_bosque_2015 & ~mascara_bosque_actual`
- Píxeles que ERAN bosque en 2015 y YA NO lo son → deforestación

**Etapa 5 — Morfología matemática**
- `binary_opening(mascara_perdida, square(3))` → elimina ruido de sal
- `binary_closing(resultado, square(5))` → consolida parches reales
- Resultado: `mascara_refinada ndarray (H, W) bool`

**Etapa 6 — Componentes conectados**
- `skimage.measure.label()` → etiqueta única por parche (8-conectividad)
- `regionprops()` → área, centroide, bbox por componente
- Filtrar componentes < 10 px (< 0.1 ha; 1 px Sentinel-2 = 100 m² = 0.01 ha)

**Etapa 7 — Reporte por alcaldía**
- Leer shapefile alcaldías INEGI → GeoDataFrame → reproyectar a CRS de la imagen
- `geometry_mask()` por alcaldía → intersección booleana con máscaras en RAM
- Calcular: `area_bosque_2015_ha`, `area_perdida_ha`, `porcentaje`, `n_parches`

**Escritura final:**
- `output_2015.ppm` y `output_actual.ppm` (formato PPM compatible con repo joaotav)
- `mapa_deforestacion.png` (matplotlib: imagen RGB + máscara roja)
- `reporte_alcaldias.csv`

---

## scripts/00_gee_export.js — Script Google Earth Engine

**Ejecutar en:** https://code.earthengine.google.com (no en terminal local)
**Acción:** Define polígono CDMX, filtra colecciones Sentinel-2 y WorldCover, encola 3 exportaciones a Google Drive.

```javascript
// Región CDMX
var cdmx = ee.Geometry.Polygon([[
  [-99.33, 19.19], [-98.94, 19.19],
  [-98.94, 19.59], [-99.33, 19.59], [-99.33, 19.19]
]]);

// Función de adquisición Sentinel-2 L2A
function getSentinel2(startDate, endDate, region) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(region)
    .filterDate(startDate, endDate)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
    .median()
    .select(['B4', 'B3', 'B2', 'B8'])
    .clip(region);
}

// Imágenes (temporada seca para evitar nubes)
var imagen_2015   = getSentinel2('2015-11-01', '2016-02-28', cdmx);
var imagen_actual = getSentinel2('2024-11-01', '2025-02-28', cdmx);
var worldcover    = ee.ImageCollection('ESA/WorldCover/v100').first().clip(cdmx);

// Exportar a Drive (ejecutar cada Task manualmente en la pestaña Tasks)
// Parámetros: scale=10, crs='EPSG:32614', folder='deforestacion_cdmx'
// Archivos resultantes: sentinel2_cdmx_2015.tif, sentinel2_cdmx_actual.tif, worldcover_cdmx.tif
```

---

## scripts/01_descarga_drive.py — Descarga única desde Drive

**Propósito:** Descargar los 3 GeoTIFFs de la carpeta `deforestacion_cdmx/` en Google Drive a `data/raw/`.
**Ejecución:** `python scripts/01_descarga_drive.py` — una sola vez por integrante. Requiere `credentials.json` de Google Cloud Console (OAuth2 Desktop App).

**¿Qué es credentials.json?**
Archivo generado por Google Cloud Console que permite autenticación OAuth2. Lo genera Google — no se crea manualmente. Pasos:
1. [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → habilitar **Google Drive API**
2. Credentials → Create Credentials → **OAuth 2.0 Client ID** → tipo **Desktop App**
3. Descargar JSON → renombrar a `credentials.json` → colocar en raíz del proyecto
4. Primera ejecución: abre navegador para autorizar → guarda `token.json` (no vuelve a pedir autorización)

Estructura del archivo (contenido generado automáticamente por Google):
```json
{
  "installed": {
    "client_id": "XXXXXXXXX.apps.googleusercontent.com",
    "client_secret": "XXXXXXXXX",
    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
  }
}
```
**Nunca subir al repo** — va en `.gitignore`. Cada integrante genera el suyo.

**Flujo:**
1. Autenticación OAuth2 → abre navegador primera vez, guarda `token.json`
2. Busca carpeta `deforestacion_cdmx/` en Drive por nombre
3. Por cada archivo `.tif`: buscar ID → `MediaIoBaseDownload` en chunks de 10 MB → guardar en `data/raw/`
4. Si el archivo ya existe localmente, lo omite (re-ejecución segura)

**Dependencias clave:** `google-api-python-client`, `google-auth-oauthlib`, `tqdm`
**Scopes necesarios:** `https://www.googleapis.com/auth/drive.readonly`

---

## scripts/03_generar_dataset.py — Generación del dataset de entrenamiento

**Propósito:** Leer GeoTIFFs en RAM, extraer 300 parches de bosque y 300 de no-bosque como archivos `.ppm` de 16×16 px para entrenar el kNN.
**Ejecución:** `python scripts/03_generar_dataset.py` — una sola vez. Semilla fija (`SEMILLA=42`) para reproducibilidad.

**Flujo en memoria:**
1. Cargar `sentinel2_cdmx_2015.tif` → `sentinel_rgb ndarray (H,W,3) uint8` en RAM
2. Cargar `worldcover_cdmx.tif` → `worldcover_data ndarray (H,W) int` en RAM
3. Buscar posiciones con valor 10 (bosque) → muestrear 300 aleatoriamente
4. Buscar posiciones con valores 30,40,50,60 (no-bosque) → muestrear 300
5. Por cada posición: `sentinel_rgb[fila-8:fila+8, col-8:col+8]` → extraer parche 16×16
6. `guardar_ppm()` → escribir como texto plano PPM en `forest/` o `deforestation/`

**Formato PPM de salida:**
```
P3
16 16
255
43 89 31  45 91 33  ...  (256 tripletas R G B)
```

**Clases WorldCover:**
- `10` = Tree cover → clase `forest` → carpeta `forest/`
- `30,40,50,60` = Grassland, Cropland, Built-up, Bare → clase `deforestation/`

---

## scripts/02_pipeline.py — Pipeline principal

**Propósito:** Leer los GeoTIFFs una vez, clasificar con kNN, detectar cambio temporal, refinar con morfología, etiquetar componentes, calcular reporte por alcaldía. Todo en RAM hasta la escritura final.

**Parámetros configurables al inicio del archivo:**
```python
K_VALUE    = 16   # vecinos kNN (debe ser impar para evitar empates; si es par se ajusta a k-1)
BLOCK_SIZE = 16   # tamaño de bloque en px (igual al tamaño de los .ppm de entrenamiento)
MIN_AREA_PIXELES = 10  # umbral mínimo de parche (0.1 ha)
```

**Clases y funciones principales:**

`PipelineState` — dataclass que mantiene todo el estado en RAM:
- `rgb_2015`, `rgb_actual`: `ndarray (H,W,3) uint8`
- `transform`, `crs`: georeferenciación
- `dataset`: lista de 600 vectores `[R, G, B, clase]`
- `mascara_bosque_2015`, `mascara_bosque_actual`, `mascara_perdida`, `mascara_refinada`, `etiquetas`: `ndarray (H,W) bool/int`
- `resultados_alcaldias`: lista de `ResultadoAlcaldia`

`cargar_imagen_en_memoria(ruta)` → `(ndarray, Affine, CRS)`
`cargar_dataset_knn(carpeta_f, carpeta_d)` → `list[[R,G,B,clase]]`
`clasificar_imagen_en_memoria(rgb, dataset, k, block_size)` → `(mascara_bool, imagen_resultado_rgb)`
`calcular_mascara_perdida(bosque_2015, bosque_actual)` → `mascara_bool`
`refinar_mascara(mascara)` → `mascara_bool`
`etiquetar_componentes(mascara, min_area_px)` → `(etiquetas_int, stats_list)`
`calcular_reporte_alcaldias(...)` → `list[ResultadoAlcaldia]`

**Salidas finales escritas en `data/outputs/`:**
- `output_2015.ppm` — imagen 2015 con bloques deforestados en rojo (formato PPM joaotav)
- `output_actual.ppm` — imagen actual con bloques deforestados en rojo
- `mapa_deforestacion.png` — figura matplotlib 2 paneles: RGB+máscara roja / máscara binaria
- `reporte_alcaldias.csv` — columnas: Alcaldía, Bosque 2015 (ha), Área Perdida (ha), % Pérdida, N° Parches

**Fallback sin shapefile:** Si `data/raw/alcaldias_cdmx.shp` no existe, genera reporte global de la CDMX completa en lugar de desglosar por alcaldía.

---

## NOTAS IMPORTANTES PARA DESARROLLO

- El clasificador kNN es fiel al repositorio `joaotav/deforestation-detection`: mismo algoritmo (distancia euclidiana RGB, voto por mayoría), mismo formato PPM. La adaptación es: parches 16×16 (no 8×8), bandas Sentinel-2 (no RGB genérico), dataset propio de la CDMX.
- `BLOCK_SIZE` en `02_pipeline.py` y el tamaño de los `.ppm` en `03_generar_dataset.py` **deben ser iguales**.
- El shapefile de alcaldías INEGI se descarga manualmente de `inegi.org.mx/app/mapa/espacioydatos/` y se coloca en `data/raw/alcaldias_cdmx.shp`.
- Para pruebas rápidas sin GEE: se puede usar cualquier imagen RGB en GeoTIFF recortada a una alcaldía pequeña (ej. Milpa Alta) y WorldCover del mismo área.
- El formato `.ppm` es texto plano — no usar para imágenes grandes. Solo se usa para los parches 16×16 de entrenamiento y para los outputs finales (compatibilidad con joaotav).

---

**Versión:** 2.0 — Mayo 2026