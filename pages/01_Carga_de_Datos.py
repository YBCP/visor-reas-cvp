"""
Módulo 1 — Carga de Datos
Convierte SHP a GeoJSON y carga tablas de atributos.
"""

import io
import os
import sys
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(Path(__file__).parent.parent))
from conversor import RUTAS, convertir_reas, convertir_lote, copiar_tabla_gis

NAVY = "#1A1F36"
BLUE = "#4F8EF7"
SLATE = "#64748B"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_header(title, subtitle=""):
    sub = (f'<p style="margin:5px 0 0;opacity:.75;font-size:.88rem;">{subtitle}</p>'
           if subtitle else "")
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{NAVY} 0%,#2C3560 100%);
                color:white;padding:20px 28px;border-radius:14px;margin-bottom:22px;
                box-shadow:0 6px 24px rgba(26,31,54,.22);">
      <h2 style="margin:0;font-size:1.25rem;font-weight:800;">{title}</h2>
      {sub}
    </div>""", unsafe_allow_html=True)


def _status_pill(ok: bool):
    if ok:
        return '<span style="background:#00C9A718;color:#00C9A7;border:1px solid #00C9A744;border-radius:20px;padding:2px 10px;font-size:.75rem;font-weight:600;">✓ Cargado</span>'
    return '<span style="background:#FF6B6B18;color:#FF6B6B;border:1px solid #FF6B6B44;border-radius:20px;padding:2px 10px;font-size:.75rem;font-weight:600;">✗ Sin cargar</span>'


def _read_dbf(uploaded) -> pd.DataFrame:
    """Lee un .dbf subido y devuelve DataFrame."""
    try:
        from simpledbf import Dbf5
        with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        df = Dbf5(tmp_path, codec="latin-1").to_dataframe()
        os.unlink(tmp_path)
        return df
    except Exception as e:
        st.error(f"Error leyendo DBF: {e}")
        return pd.DataFrame()


def _read_uploaded(uploaded) -> pd.DataFrame:
    name = uploaded.name.lower()
    if name.endswith(".dbf"):
        return _read_dbf(uploaded)
    elif name.endswith(".csv"):
        return pd.read_csv(uploaded, encoding="utf-8-sig", low_memory=False)
    elif name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded)
    return pd.DataFrame()


def _save_csv(df: pd.DataFrame, filename: str):
    path = DATA_DIR / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _file_info(filename: str):
    path = DATA_DIR / filename
    if path.exists():
        stat = path.stat()
        size_kb = stat.st_size / 1024
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
        return True, mtime, size_kb
    return False, None, None


def _download_btn(filename: str, label: str, key: str):
    """Botón de descarga para un archivo en DATA_DIR."""
    path = DATA_DIR / filename
    if not path.exists():
        return
    if filename.endswith(".csv"):
        mime = "text/csv"
    elif filename.endswith(".geojson"):
        mime = "application/geo+json"
    elif filename.endswith((".xlsx", ".xls")):
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        mime = "application/octet-stream"
    st.download_button(
        label=f"⬇ Descargar {label}",
        data=path.read_bytes(),
        file_name=filename,
        mime=mime,
        key=key,
        use_container_width=True,
    )


# ── Conversión SHP ────────────────────────────────────────────────────────────

def _convertir_shp(uploaded_files: list, nombre_salida: str, es_lote: bool = False):
    """Recibe archivos del uploader (shp, dbf, shx, prj, cpg) y convierte a GeoJSON."""
    try:
        import geopandas as gpd
        import tempfile, shutil
    except ImportError:
        st.error("geopandas no está instalado. Ejecuta: `pip install geopandas`")
        return

    with st.spinner(f"Convirtiendo {nombre_salida}..."):
        # Guardar todos los archivos en un directorio temporal
        tmpdir = tempfile.mkdtemp()
        shp_path = None
        for f in uploaded_files:
            dest = os.path.join(tmpdir, f.name)
            with open(dest, "wb") as out:
                out.write(f.read())
            if f.name.lower().endswith(".shp"):
                shp_path = dest

        if not shp_path:
            st.error("No se encontró archivo .shp entre los archivos subidos.")
            shutil.rmtree(tmpdir)
            return

        try:
            gdf = gpd.read_file(shp_path)

            if es_lote:
                # Cargar REAS para obtener bbox de recorte
                reas_path = DATA_DIR / "reas.geojson"
                if reas_path.exists():
                    reas = gpd.read_file(reas_path)
                    reas_proj = reas.to_crs(gdf.crs)
                    bbox = reas_proj.total_bounds  # [minx, miny, maxx, maxy]
                    # Buffer ~500m en grados (~0.005°)
                    buf = 0.005
                    from shapely.geometry import box
                    clip_geom = box(bbox[0]-buf, bbox[1]-buf, bbox[2]+buf, bbox[3]+buf)
                    gdf = gdf[gdf.geometry.intersects(clip_geom)].copy()
                    st.info(f"Recortado al área de REAS: {len(gdf):,} features seleccionados.")
                else:
                    st.warning("REAS.geojson no encontrado — se convierte Lote completo (puede ser muy pesado).")

                # Simplificar geometría para reducir peso
                gdf["geometry"] = gdf["geometry"].simplify(0.000005, preserve_topology=True)

            # Reproyectar a WGS84
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)

            # Exportar
            out_path = DATA_DIR / nombre_salida
            gdf.to_file(out_path, driver="GeoJSON")

            size_mb = out_path.stat().st_size / (1024 * 1024)
            st.success(f"✓ {nombre_salida} generado — {len(gdf):,} features · {size_mb:.1f} MB")
            st.cache_data.clear()
            st.info("↺ Caché del visor actualizado — Módulos 2 y 3 usarán los datos nuevos.")

        except Exception as e:
            st.error(f"Error durante la conversión: {e}")
        finally:
            shutil.rmtree(tmpdir)


# ── Página ────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Carga de Datos · CVP", layout="wide",
                   initial_sidebar_state="expanded")

_section_header("Módulo 1 — Carga de Datos",
                "Convierte capas geográficas y carga tablas de atributos")

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN A — Capas geográficas SHP → GeoJSON
# ════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:22px 0 14px;">
  <div style="width:4px;height:20px;background:linear-gradient(180deg,{BLUE},#A78BFA);
              border-radius:2px;flex-shrink:0;"></div>
  <span style="font-size:.95rem;font-weight:700;color:#1E293B;">
    A — Capas geográficas (SHP → GeoJSON)
  </span>
</div>
""", unsafe_allow_html=True)

st.caption("Sube todos los archivos del shapefile juntos (.shp, .dbf, .shx, .prj). "
           "Procesa primero REAS, luego Lote (Lote usa la extensión de REAS para recortarse).")

col_reas, col_lote = st.columns(2)

with col_reas:
    reas_ok, reas_mtime, reas_kb = _file_info("reas.geojson")
    st.markdown(f"**Capa REAS** &nbsp; {_status_pill(reas_ok)}", unsafe_allow_html=True)
    if reas_ok:
        st.caption(f"Última actualización: {reas_mtime} · {reas_kb/1024:.1f} MB")
        _download_btn("reas.geojson", "reas.geojson", "dl_reas")

    # Botón de ruta predeterminada
    ruta_reas = RUTAS["reas"]
    if ruta_reas.exists():
        st.caption(f"Ruta predeterminada: `{ruta_reas.name}`")
        if st.button("Convertir desde ruta predeterminada",
                     type="primary", key="btn_reas_default"):
            with st.spinner("Convirtiendo REAS.shp..."):
                try:
                    convertir_reas()
                    st.cache_data.clear()
                    st.success("✓ reas.geojson generado")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.caption(f"⚠ Ruta predeterminada no encontrada: `{ruta_reas}`")

    with st.expander("Subir archivo manualmente"):
        files_reas = st.file_uploader(
            "Archivos REAS.shp",
            accept_multiple_files=True,
            type=["shp", "dbf", "shx", "prj", "cpg"],
            key="uploader_reas",
            label_visibility="collapsed",
        )
        if files_reas and st.button("Convertir REAS → GeoJSON", key="btn_reas_manual"):
            _convertir_shp(files_reas, "reas.geojson", es_lote=False)
            st.rerun()

with col_lote:
    lote_ok, lote_mtime, lote_kb = _file_info("lote.geojson")
    st.markdown(f"**Capa Lote (Catastro)** &nbsp; {_status_pill(lote_ok)}", unsafe_allow_html=True)
    if lote_ok:
        st.caption(f"Última actualización: {lote_mtime} · {lote_kb/1024:.1f} MB")
        _download_btn("lote.geojson", "lote.geojson", "dl_lote")

    ruta_lote = RUTAS["lote"]
    if ruta_lote.exists():
        st.caption(f"Ruta predeterminada: `{ruta_lote.name}` · ~311 MB (puede tardar)")
        if st.button("Convertir desde ruta predeterminada",
                     type="primary", key="btn_lote_default"):
            with st.spinner("Convirtiendo Lote.shp (archivo grande)..."):
                try:
                    convertir_lote()
                    st.cache_data.clear()
                    st.success("✓ lote.geojson generado")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.caption(f"⚠ Ruta predeterminada no encontrada: `{ruta_lote}`")

    with st.expander("Subir archivo manualmente"):
        st.caption("Sube todos los archivos juntos (.shp, .dbf, .shx, .prj).")
        files_lote = st.file_uploader(
            "Archivos Lote.shp",
            accept_multiple_files=True,
            type=["shp", "dbf", "shx", "prj", "cpg"],
            key="uploader_lote",
            label_visibility="collapsed",
        )
        if files_lote and st.button("Convertir Lote → GeoJSON", key="btn_lote_manual"):
            _convertir_shp(files_lote, "lote.geojson", es_lote=True)
            st.rerun()

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN B — Tablas
# ════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:22px 0 14px;">
  <div style="width:4px;height:20px;background:linear-gradient(180deg,{BLUE},#A78BFA);
              border-radius:2px;flex-shrink:0;"></div>
  <span style="font-size:.95rem;font-weight:700;color:#1E293B;">
    B — Tablas de atributos
  </span>
</div>
""", unsafe_allow_html=True)

TABLAS = [
    ("Propietario",     "propietario.csv",      "Propietario.dbf (Catastro)"),
    ("GIS",             "gis.csv",              f"REAS (29).xlsx · {RUTAS['gis'].parent}"),
    ("Depuración",      "depuracion.csv",       "resultado_final_predios_cvp.csv (R_Analisis/output)"),
    ("Origen Destino",  "origen_destino.xlsx",  "Origen destino maestro.xlsx"),
]

for tabla_nombre, tabla_archivo, tabla_fuente in TABLAS:
    tabla_ok, tabla_mtime, tabla_kb = _file_info(tabla_archivo)

    with st.expander(f"**{tabla_nombre}** — {tabla_fuente} &nbsp; "
                     f"{'✓' if tabla_ok else '✗'}", expanded=not tabla_ok):

        if tabla_ok:
            _size_str = f"{tabla_kb/1024:.1f} MB" if tabla_kb and tabla_kb > 1024 else f"{tabla_kb:.0f} KB"
            st.caption(f"Última actualización: {tabla_mtime} · {_size_str}")
            _download_btn(tabla_archivo, tabla_nombre, f"dl_{tabla_archivo}")

        uploaded = st.file_uploader(
            f"Subir tabla {tabla_nombre}",
            type=["dbf", "xlsx", "xls", "csv"],
            key=f"up_{tabla_archivo}",
            label_visibility="collapsed",
        )

        # Botón de ruta predeterminada para GIS
        if tabla_archivo == "gis.csv" and RUTAS["gis"].exists():
            st.caption(f"Ruta predeterminada disponible: `{RUTAS['gis'].name}`")
            if st.button("Cargar desde ruta predeterminada",
                         key=f"default_{tabla_archivo}"):
                copiar_tabla_gis.__wrapped__ = None  # evitar cache
                try:
                    import pandas as pd
                    df_tmp = pd.read_excel(RUTAS["gis"])
                    _save_csv(df_tmp, tabla_archivo)
                    st.success(f"✓ GIS cargada — {len(df_tmp):,} registros")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        if uploaded:
            # Origen Destino se guarda como xlsx, el resto como csv
            es_xlsx = tabla_archivo.endswith(".xlsx")
            if es_xlsx:
                # Guardar binario directo sin parsear
                if st.button(f"Guardar tabla {tabla_nombre}", type="primary",
                             key=f"save_{tabla_archivo}"):
                    dest = DATA_DIR / tabla_archivo
                    dest.write_bytes(uploaded.read())
                    st.cache_data.clear()
                    st.success(f"✓ {tabla_nombre} guardada")
                    st.info("↺ Caché del visor actualizado — Módulo 4 usará los datos nuevos.")
                    st.rerun()
            else:
                df_prev = _read_uploaded(uploaded)
                if not df_prev.empty:
                    st.caption(f"{len(df_prev):,} filas · {len(df_prev.columns)} columnas")
                    st.dataframe(df_prev.head(10), use_container_width=True,
                                 hide_index=True, height=220)
                    if st.button(f"Guardar tabla {tabla_nombre}", type="primary",
                                 key=f"save_{tabla_archivo}"):
                        _save_csv(df_prev, tabla_archivo)
                        st.cache_data.clear()
                        st.success(f"✓ {tabla_nombre} guardada — {len(df_prev):,} registros")
                        st.info("↺ Caché del visor actualizado — Módulos 2 y 3 usarán los datos nuevos.")
                        st.rerun()

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN C — Estado de los datos
# ════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:22px 0 14px;">
  <div style="width:4px;height:20px;background:linear-gradient(180deg,{BLUE},#A78BFA);
              border-radius:2px;flex-shrink:0;"></div>
  <span style="font-size:.95rem;font-weight:700;color:#1E293B;">
    C — Estado actual de los datos
  </span>
</div>
""", unsafe_allow_html=True)

TODOS = [
    ("reas.geojson",        "Capa REAS"),
    ("lote.geojson",        "Capa Lote"),
    ("propietario.csv",     "Tabla Propietario"),
    ("gis.csv",             "Tabla GIS"),
    ("depuracion.csv",      "Tabla Depuración"),
    ("origen_destino.xlsx", "Tabla Origen Destino"),
]

for fname, label in TODOS:
    ok, mtime, kb = _file_info(fname)
    size_str = f"{kb/1024:.1f} MB" if (kb and kb > 1024) else (f"{kb:.0f} KB" if kb else "—")
    c1, c2, c3 = st.columns([4, 3, 2])
    with c1:
        st.markdown(f"**{label}**  \n`{fname}`")
    with c2:
        st.markdown(_status_pill(ok), unsafe_allow_html=True)
        if ok:
            st.caption(f"{mtime} · {size_str}")
    with c3:
        if ok:
            _download_btn(fname, fname, f"dlc_{fname}")
    st.divider()
