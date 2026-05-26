"""
Script de conversión SHP → GeoJSON (ejecutar una sola vez desde consola).
Uso:  python convertir_capas.py
"""

import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

REAS_SHP = Path(r"C:\workspace\CVP\Archivos de entrada\REAS\REAS.shp")
LOTE_SHP = Path(r"C:\workspace\CVP\Archivos de entrada\Catastro\Lote.shp")


def log(msg):
    print(msg, flush=True, end="\n")


def convertir_reas():
    import geopandas as gpd

    out = DATA_DIR / "reas.geojson"
    log(f"\n--- REAS ---")
    log(f"Leyendo {REAS_SHP} ...")
    gdf = gpd.read_file(REAS_SHP)
    log(f"  {len(gdf):,} features leídos · CRS: {gdf.crs}")

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        log("  Reproyectando a WGS84...")
        gdf = gdf.to_crs(epsg=4326)

    log(f"  Exportando a {out.name} ...")
    gdf.to_file(out, driver="GeoJSON")
    size_mb = out.stat().st_size / (1024 * 1024)
    log(f"  ✓ reas.geojson  —  {len(gdf):,} predios · {size_mb:.1f} MB")
    return gdf


def convertir_lote(reas_gdf=None):
    import geopandas as gpd
    from shapely.geometry import box

    out = DATA_DIR / "lote.geojson"
    log(f"\n--- LOTE ---")
    log(f"Leyendo {LOTE_SHP} (archivo grande, puede tardar varios minutos)...")
    gdf = gpd.read_file(LOTE_SHP)
    log(f"  {len(gdf):,} features leídos · CRS: {gdf.crs}")

    # Reproyectar a WGS84 primero para hacer el clip en la misma proyección
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        log("  Reproyectando a WGS84...")
        gdf = gdf.to_crs(epsg=4326)

    # Clip espacial: intersección real con los polígonos REAS (no solo bbox)
    reas_path = DATA_DIR / "reas.geojson"
    if reas_gdf is not None or reas_path.exists():
        if reas_gdf is None:
            reas_gdf = gpd.read_file(reas_path)
        reas_union = reas_gdf.geometry.union_all()
        buf = 0.001  # ~100 m de buffer
        reas_buf = reas_union.buffer(buf)
        log(f"  Filtrando lotes que intersectan área REAS + {buf*111000:.0f} m buffer...")
        mask = gdf.geometry.intersects(reas_buf)
        gdf  = gdf[mask].copy()
        log(f"  {len(gdf):,} lotes seleccionados tras filtro espacial")
    else:
        log("  ⚠ REAS no disponible — convirtiendo Lote completo (no recomendado)")

    # Conservar solo columnas utiles (reduce tamano del GeoJSON)
    cols_utiles = ["LOTLNUMERO", "LOTMANZ_ID", "LOTSECT_ID", "LOTTIPO",
                   "FONDO", "FRENTE", "LOTLOTE_ID", "geometry"]
    gdf = gdf[[c for c in cols_utiles if c in gdf.columns]]

    # Simplificar geometria (~5 m tolerancia, suficiente para visualizacion)
    log("  Simplificando geometrias (tolerance=0.00005)...")
    gdf["geometry"] = gdf["geometry"].simplify(0.00005, preserve_topology=True)

    log(f"  Exportando a {out.name} ...")
    gdf.to_file(out, driver="GeoJSON")
    size_mb = out.stat().st_size / (1024 * 1024)
    log(f"  ✓ lote.geojson  —  {len(gdf):,} lotes · {size_mb:.1f} MB")


if __name__ == "__main__":
    try:
        import geopandas
    except ImportError:
        log("ERROR: geopandas no instalado. Ejecuta: python -m pip install geopandas")
        sys.exit(1)

    if not REAS_SHP.exists():
        log(f"ERROR: No se encontró {REAS_SHP}")
        sys.exit(1)
    if not LOTE_SHP.exists():
        log(f"ERROR: No se encontró {LOTE_SHP}")
        sys.exit(1)

    log("=== Conversion de capas CVP ===")
    reas_gdf = convertir_reas()
    convertir_lote(reas_gdf)
    log("\n=== Conversion completa ===")
    log(f"Archivos en: {DATA_DIR}")
