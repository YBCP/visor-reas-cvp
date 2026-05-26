"""
Utilidad de conversión SHP → GeoJSON.
Conoce las rutas predeterminadas de los archivos fuente.
"""

import os
from pathlib import Path

# Rutas predeterminadas (absolutas)
BASE = Path(r"C:\workspace\CVP\Archivos de entrada")

RUTAS = {
    "reas": BASE / "REAS" / "REAS.shp",
    "lote": BASE / "Catastro" / "Lote.shp",
    "gis":  BASE / "REAS" / "REAS (29).xlsx",
}

DATA_DIR = Path(__file__).parent / "data"


def _log(msg: str):
    """Imprime en consola y, si Streamlit está activo, en pantalla."""
    print(msg)
    try:
        import streamlit as st
        st.write(msg)
    except Exception:
        pass


def convertir_reas(shp_path: Path = None) -> Path:
    """
    Convierte REAS.shp a GeoJSON y guarda en data/reas.geojson.
    Si shp_path es None usa la ruta predeterminada.
    Devuelve la ruta del GeoJSON generado.
    """
    import geopandas as gpd

    src = Path(shp_path) if shp_path else RUTAS["reas"]
    if not src.exists():
        raise FileNotFoundError(f"No se encontró REAS.shp en: {src}")

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / "reas.geojson"

    _log(f"Leyendo {src.name}...")
    gdf = gpd.read_file(src)

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        _log("Reproyectando a WGS84 (EPSG:4326)...")
        gdf = gdf.to_crs(epsg=4326)

    _log(f"Exportando {len(gdf):,} features...")
    gdf.to_file(out, driver="GeoJSON")

    size_mb = out.stat().st_size / (1024 * 1024)
    _log(f"✓ reas.geojson generado — {len(gdf):,} predios · {size_mb:.1f} MB")
    return out


def convertir_lote(shp_path: Path = None, reas_geojson: Path = None) -> Path:
    """
    Convierte Lote.shp a GeoJSON recortado al área de REAS + buffer 500 m.
    Si shp_path es None usa la ruta predeterminada.
    Devuelve la ruta del GeoJSON generado.
    """
    import geopandas as gpd
    from shapely.geometry import box

    src = Path(shp_path) if shp_path else RUTAS["lote"]
    if not src.exists():
        raise FileNotFoundError(f"No se encontró Lote.shp en: {src}")

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / "lote.geojson"

    reas_path = reas_geojson or (DATA_DIR / "reas.geojson")

    _log(f"Leyendo {src.name} (archivo grande, puede tardar)...")
    gdf = gpd.read_file(src)

    if reas_path.exists():
        _log("Recortando al área de REAS + 500 m de buffer...")
        reas = gpd.read_file(reas_path).to_crs(gdf.crs)
        bbox = reas.total_bounds            # [minx, miny, maxx, maxy]
        buf  = 0.005                         # ~500 m en grados
        clip_geom = box(bbox[0]-buf, bbox[1]-buf, bbox[2]+buf, bbox[3]+buf)
        gdf = gdf[gdf.geometry.intersects(clip_geom)].copy()
        _log(f"Recortado: {len(gdf):,} lotes en el área de REAS.")
    else:
        _log("⚠ REAS no disponible — convirtiendo Lote completo.")

    _log("Simplificando geometrías...")
    gdf["geometry"] = gdf["geometry"].simplify(0.000005, preserve_topology=True)

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        _log("Reproyectando a WGS84...")
        gdf = gdf.to_crs(epsg=4326)

    gdf.to_file(out, driver="GeoJSON")

    size_mb = out.stat().st_size / (1024 * 1024)
    _log(f"✓ lote.geojson generado — {len(gdf):,} lotes · {size_mb:.1f} MB")
    return out


def copiar_tabla_gis():
    """Copia REAS (29).xlsx → data/gis.csv si no existe."""
    import pandas as pd
    out = DATA_DIR / "gis.csv"
    if out.exists():
        return
    src = RUTAS["gis"]
    if not src.exists():
        return
    df = pd.read_excel(src)
    df.to_csv(out, index=False, encoding="utf-8-sig")


def auto_convertir_si_falta():
    """
    Verifica si los GeoJSON existen. Si no, los genera desde las rutas predeterminadas.
    Retorna dict con estado de cada capa.
    """
    estado = {"reas": False, "lote": False, "error_reas": None, "error_lote": None}

    reas_path = DATA_DIR / "reas.geojson"
    lote_path = DATA_DIR / "lote.geojson"

    if not reas_path.exists():
        try:
            convertir_reas()
            estado["reas"] = True
        except Exception as e:
            estado["error_reas"] = str(e)
    else:
        estado["reas"] = True

    # Copiar tabla GIS si no existe
    try:
        copiar_tabla_gis()
    except Exception:
        pass

    if not lote_path.exists():
        try:
            convertir_lote()
            estado["lote"] = True
        except Exception as e:
            estado["error_lote"] = str(e)
    else:
        estado["lote"] = True

    return estado


def rutas_disponibles() -> dict:
    """Retorna qué rutas predeterminadas existen en disco."""
    return {k: v.exists() for k, v in RUTAS.items()}
