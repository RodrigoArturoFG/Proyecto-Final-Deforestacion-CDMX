// ============================================================
// 00_gee_export.js
// Script para Google Earth Engine (code.earthengine.google.com)
// Exporta Sentinel-2 (2015 y actual) + WorldCover a Google Drive
// Ejecutar directamente en el editor de GEE, NO en Python
// ============================================================

// ── 1. REGIÓN DE INTERÉS: Ciudad de México ───────────────────
// Polígono simplificado de la CDMX en coordenadas WGS84
var cdmx = ee.Geometry.Polygon([[
  [-99.33, 19.19],
  [-98.94, 19.19],
  [-98.94, 19.59],
  [-99.33, 19.59],
  [-99.33, 19.19]
]]);

// ── 2. FUNCIÓN: obtener imagen Sentinel-2 con baja nubosidad ─
function getSentinel2(startDate, endDate, region) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(region)
    .filterDate(startDate, endDate)
    // Solo escenas con menos del 10% de nubes
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
    // Mediana de la colección elimina nubes residuales
    .median()
    // Solo las bandas que necesitamos: R, G, B para kNN + NIR para NDVI
    .select(['B4', 'B3', 'B2', 'B8'])
    .clip(region);
}

// ── 3. IMAGEN BASE: 2015 ─────────────────────────────────────
// Sentinel-2A inició operaciones en junio 2015
// Buscamos la mejor escena de temporada seca (nov-feb) para evitar nubes
var imagen_2015 = getSentinel2('2015-11-01', '2016-02-28', cdmx);

// ── 4. IMAGEN ACTUAL: 2024-2025 ──────────────────────────────
// Misma época del año para comparación justa (temporada seca)
var imagen_actual = getSentinel2('2024-11-01', '2025-02-28', cdmx);

// ── 5. WORLDCOVER: mapa de cobertura para dataset entrenamiento
var worldcover = ee.ImageCollection('ESA/WorldCover/v100')
  .first()
  .clip(cdmx);

// ── 6. VERIFICACIÓN VISUAL en el editor de GEE ───────────────
Map.centerObject(cdmx, 10);
Map.addLayer(imagen_actual, {bands: ['B4', 'B3', 'B2'], min: 0, max: 3000}, 'Sentinel-2 Actual RGB');
Map.addLayer(imagen_2015,   {bands: ['B4', 'B3', 'B2'], min: 0, max: 3000}, 'Sentinel-2 2015 RGB');
Map.addLayer(worldcover,    {min: 10, max: 100}, 'WorldCover');

// ── 7. EXPORTAR A GOOGLE DRIVE ───────────────────────────────
// Las tres exportaciones van a la carpeta 'deforestacion_cdmx' en tu Drive
// Cada tarea aparece en la pestaña "Tasks" de GEE — hay que correrlas manualmente

// Imagen 2015 (bandas B4=Rojo, B3=Verde, B2=Azul, B8=NIR)
Export.image.toDrive({
  image: imagen_2015,
  description: 'sentinel2_cdmx_2015',
  folder: 'deforestacion_cdmx',
  fileNamePrefix: 'sentinel2_cdmx_2015',
  region: cdmx,
  scale: 10,           // 10 metros por píxel (resolución nativa Sentinel-2)
  crs: 'EPSG:32614',   // UTM zona 14N - sistema métrico para la CDMX
  maxPixels: 1e10,
  fileFormat: 'GeoTIFF'
});

// Imagen actual
Export.image.toDrive({
  image: imagen_actual,
  description: 'sentinel2_cdmx_actual',
  folder: 'deforestacion_cdmx',
  fileNamePrefix: 'sentinel2_cdmx_actual',
  region: cdmx,
  scale: 10,
  crs: 'EPSG:32614',
  maxPixels: 1e10,
  fileFormat: 'GeoTIFF'
});

// WorldCover (para generar dataset de entrenamiento)
Export.image.toDrive({
  image: worldcover,
  description: 'worldcover_cdmx',
  folder: 'deforestacion_cdmx',
  fileNamePrefix: 'worldcover_cdmx',
  region: cdmx,
  scale: 10,
  crs: 'EPSG:32614',
  maxPixels: 1e10,
  fileFormat: 'GeoTIFF'
});

// ── NOTAS DE USO ─────────────────────────────────────────────
// 1. Pegar este script en code.earthengine.google.com
// 2. Clic en "Run" para ver las capas en el mapa
// 3. Ir a la pestaña "Tasks" y hacer clic en "Run" para cada exportación
// 4. Las tareas tardan 5-20 minutos dependiendo del tamaño
// 5. Los archivos aparecerán en Google Drive > deforestacion_cdmx/
