# 🌿 Sistema de Detección de Deforestación en la CDMX
**Detección Multitemporal con Sentinel-2 + kNN**

Herramienta de análisis de imágenes satelitales que detecta pérdida de cobertura forestal en la Ciudad de México comparando imágenes Sentinel-2 de 2015 contra imágenes actuales, usando un clasificador k-Nearest Neighbors. Los resultados se desagregan por alcaldía.

---

## ¿Qué hace?

- Descarga imágenes Sentinel-2 de 2015 y del año actual sobre la CDMX desde Google Earth Engine
- Entrena un clasificador kNN con muestras etiquetadas de ESA WorldCover
- Detecta píxeles que **eran bosque en 2015 y ya no lo son**
- Refina la detección con morfología matemática
- Genera un reporte de hectáreas perdidas y porcentaje de deforestación **por alcaldía**

**Salidas:**
```
data/outputs/
├── output_2015.ppm          # Imagen 2015 con zonas deforestadas en rojo
├── output_actual.ppm        # Imagen actual con zonas deforestadas en rojo
├── mapa_deforestacion.png   # Mapa visual con áreas afectadas
└── reporte_alcaldias.csv    # Métricas por alcaldía
```

---

## Requisitos

- Python 3.10+
- Cuenta gratuita en [Google Earth Engine](https://code.earthengine.google.com)
- Cuenta de Google con Google Drive
- Credenciales OAuth2 de Google Cloud Console (`credentials.json`) — ver sección de configuración
- Shapefile de alcaldías CDMX del [INEGI](https://www.inegi.org.mx/app/mapa/espacioydatos/) colocado en `data/raw/alcaldias_cdmx.shp`

```bash
pip install -r requirements.txt
```

---

## Configuración inicial

### 1. Credenciales de Google Drive

El archivo `credentials.json` lo genera Google Cloud Console y permite que `01_descarga_drive.py` se autentique con tu cuenta de Google para acceder a Drive. **Cada integrante genera el suyo propio — nunca subir este archivo al repo.**

1. Ir a [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials
2. Crear un proyecto nuevo (o usar uno existente) → habilitar la **Google Drive API**
3. Ir a Credentials → Create Credentials → **OAuth 2.0 Client ID** → tipo **Desktop App**
4. Descargar el JSON generado y renombrarlo a `credentials.json`
5. Colocarlo en la raíz del proyecto

El archivo tiene esta estructura (el contenido lo genera Google automáticamente):
```json
{
  "installed": {
    "client_id": "XXXXXXXXX.apps.googleusercontent.com",
    "client_secret": "XXXXXXXXX",
    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
  }
}
```

La primera vez que corras `01_descarga_drive.py` se abrirá el navegador para autorizar el acceso. Después queda guardado en `token.json` y no vuelve a pedir autorización.

### 2. Shapefile de alcaldías INEGI

Descargar el Marco Geoestadístico Nacional de [INEGI](https://www.inegi.org.mx/app/mapa/espacioydatos/), extraer el shapefile de alcaldías de la CDMX y colocarlo en:
```
data/raw/alcaldias_cdmx.shp
data/raw/alcaldias_cdmx.dbf
data/raw/alcaldias_cdmx.shx
```

---

## Uso

### Paso 1 — Exportar imágenes desde Google Earth Engine

Abrir [code.earthengine.google.com](https://code.earthengine.google.com), pegar el contenido de `scripts/00_gee_export.js` y ejecutarlo. En la pestaña **Tasks**, correr las 3 exportaciones. Los archivos llegarán a Google Drive en la carpeta `deforestacion_cdmx/` en 5–20 minutos.

### Paso 2 — Descargar imágenes al disco local

```bash
python scripts/01_descarga_drive.py
```

Se abrirá el navegador para autenticación la primera vez. Descarga ~1 GB a `data/raw/`.

### Paso 3 — Generar dataset de entrenamiento

```bash
python scripts/03_generar_dataset.py
```

Extrae 600 parches de 16×16 píxeles etiquetados desde WorldCover. Solo se ejecuta una vez.

### Paso 4 — Ejecutar el análisis

```bash
python scripts/02_pipeline.py
```

Procesa todo en memoria RAM y escribe los resultados en `data/outputs/`.

---

## Parámetros ajustables

En `scripts/02_pipeline.py`:

| Parámetro | Default | Descripción |
|---|---|---|
| `K_VALUE` | `16` | Número de vecinos del kNN |
| `BLOCK_SIZE` | `16` | Tamaño de bloque en píxeles (16px = 160m en terreno) |
| `MIN_AREA_PIXELES` | `10` | Área mínima de parche detectado (10px = 0.1 ha) |

> `BLOCK_SIZE` debe coincidir con el tamaño de los `.ppm` generados en el paso 3. Si se cambia, regenerar el dataset.

---

## Fuentes de datos

| Fuente | Uso |
|---|---|
| [Copernicus / Sentinel-2](https://dataspace.copernicus.eu) | Imágenes satelitales 10m/px, gratuitas desde 2015 |
| [ESA WorldCover 10m](https://esa-worldcover.org) | Mapa de cobertura de suelo para entrenamiento del kNN |
| [INEGI](https://www.inegi.org.mx) | Shapefile de las 16 alcaldías de la CDMX |

---

## Tiempo estimado de ejecución

| Paso | Tiempo aprox. |
|---|---|
| Exportación GEE | 5–20 min |
| Descarga Drive | 10–20 min (depende de conexión) |
| Generación dataset | < 1 min |
| Pipeline completo | 8–15 min (Intel i5, 8 GB RAM) |

---

## Estructura del proyecto

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

> Agregar a `.gitignore`: `credentials.json`, `token.json`, `data/raw/*.tif`, `forest/`, `deforestation/`, `contexto_proyecto_final_AI.md`

---

## Alineación con la Agenda 2030

| ODS | Indicador SIODS |
|---|---|
| ODS 15 — Vida de Ecosistemas Terrestres | 15n.2.1 Tasa de deforestación |
| ODS 13 — Acción por el Clima | 13n.3.1 Emisiones GEI sector forestal |
| ODS 16 — Paz, Justicia e Instituciones | 16.3.2, 16.6.2, 16n.5.1 |

---

## Licencia

Apache 2.0