"""
Módulo 5 — Programar Visita
Carga una lista de identificadores REAS y genera mapa + tabla para planificar recorridos.
"""

import io
import json
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"

NAVY  = "#1A1F36"
BLUE  = "#4F8EF7"
TEAL  = "#00C9A7"
RED   = [255, 80, 80]


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _centroid(geom: dict):
    """Devuelve (lon, lat) del centroide de un Polygon/MultiPolygon WGS84."""
    if geom["type"] == "Polygon":
        ring = geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        ring = geom["coordinates"][0][0]
    else:
        return None, None
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return lon, lat


@st.cache_data(show_spinner=False)
def _load_reas_lookup():
    rj = DATA_DIR / "reas.geojson"
    if not rj.exists():
        return {}
    with open(rj, encoding="utf-8") as f:
        gj = json.load(f)
    lookup = {}
    for feat in gj["features"]:
        props = feat.get("properties", {})
        rid = str(props.get("REA_Identi", "")).strip()
        if not rid:
            continue
        lon, lat = _centroid(feat["geometry"])
        lookup[rid] = {
            "lon": lon, "lat": lat,
            "chip":        props.get("chip", "") or "",
            "DIR_CATAST":  props.get("DIR_CATAST", "") or "",
            "BARRIO":      props.get("BARRIO_LEG", "") or "",
            "LOCALIDAD":   props.get("LocNombre", "") or "",
            "TP_RIESGO":   props.get("TP_RIESGO", "") or "",
        }
    return lookup


@st.cache_data(show_spinner=False)
def _load_depuracion():
    p = DATA_DIR / "depuracion.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, encoding="utf-8-sig", low_memory=False)


@st.cache_data(show_spinner=False)
def _load_gis():
    p = DATA_DIR / "gis.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, encoding="utf-8-sig", low_memory=False)


def _id_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        if any(k in c.upper() for k in ["REA_IDEN", "IDENTIF"]):
            return c
    return None


# ── Página ────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Programar Visita · CVP", layout="wide",
                   initial_sidebar_state="collapsed")

_section_header("Módulo 5 — Programar Visita",
                "Carga una lista de identificadores REAS para planificar recorridos de campo")

# ── 1. Carga del archivo de identificadores ──────────────────────────────────

uploaded = st.file_uploader(
    "Sube un Excel o CSV con los identificadores REAS a visitar",
    type=["xlsx", "xls", "csv"],
    key="up_visita",
)

if uploaded is None:
    st.info(
        "Sube un archivo para comenzar. "
        "Debe tener una columna con los identificadores REAS (ej. `REA_Identi`)."
    )
    st.stop()

# Parsear
if uploaded.name.lower().endswith(".csv"):
    df_ids = pd.read_csv(uploaded, encoding="utf-8-sig")
else:
    df_ids = pd.read_excel(uploaded)

# Auto-detectar columna de identificador
id_col_up = _id_col(df_ids, ["REA_Identi", "REA_IDENTI", "Identificador", "ID"])
if id_col_up is None:
    id_col_up = df_ids.columns[0]

ids_list = df_ids[id_col_up].dropna().astype(str).str.strip().unique().tolist()
st.caption(f"**{len(ids_list)}** identificadores cargados desde columna `{id_col_up}`")

# ── 2. Cruzar con REAS ───────────────────────────────────────────────────────

lookup   = _load_reas_lookup()
df_dep   = _load_depuracion()
df_gis   = _load_gis()

if not lookup:
    st.error("No se encontró **reas.geojson** — carga la capa REAS en el Módulo 1 primero.")
    st.stop()

# Enriquecer con depuracion si está disponible (chip y dir catastral más completos)
dep_dict: dict = {}
dep_id_col = _id_col(df_dep, ["REA_Identi", "REA_IDENTI"]) if not df_dep.empty else None
if dep_id_col:
    df_dep[dep_id_col] = df_dep[dep_id_col].astype(str).str.strip()
    dep_dict = df_dep.set_index(dep_id_col).to_dict("index")

rows = []
for rid in ids_list:
    geo = lookup.get(rid, {})
    dep = dep_dict.get(rid, {})
    lat, lon = geo.get("lat"), geo.get("lon")

    chip = (dep.get("CHIP_USO") or dep.get("chip") or
            geo.get("chip") or "—")
    dir_c = (dep.get("DIRECCION_CATASTRAL") or dep.get("DIR_CATAST") or
             geo.get("DIR_CATAST") or "—")
    barrio    = dep.get("BARRIO", "") or geo.get("BARRIO", "")
    localidad = dep.get("LocNombre", "") or geo.get("LOCALIDAD", "")
    estado    = dep.get("ESTADO_DEPURADO", "") or ""

    maps_url = (f"https://www.google.com/maps?q={lat},{lon}" if lat else "")

    rows.append({
        "REA_Identi":          rid,
        "Dirección catastral": dir_c,
        "CHIP":                chip,
        "Barrio":              barrio,
        "Localidad":           localidad,
        "Estado":              estado,
        "En REAS":             "✓" if geo else "✗",
        "lon":                 lon,
        "lat":                 lat,
        "Google Maps":         maps_url,
    })

df_tabla = pd.DataFrame(rows)
n_ok  = df_tabla["En REAS"].eq("✓").sum()
n_bad = len(df_tabla) - n_ok

col_ok, col_bad = st.columns(2)
col_ok.metric("Encontrados en REAS", n_ok)
col_bad.metric("No encontrados", n_bad)

# ── 3. Mapa ──────────────────────────────────────────────────────────────────

df_map = df_tabla.dropna(subset=["lat", "lon"]).copy()

if not df_map.empty:
    mid_lat = df_map["lat"].mean()
    mid_lon = df_map["lon"].mean()

    layer_pts = pdk.Layer(
        "ScatterplotLayer",
        data=df_map[["lon", "lat", "REA_Identi", "Dirección catastral", "CHIP"]].to_dict("records"),
        get_position=["lon", "lat"],
        get_color=RED + [210],
        get_radius=30,
        pickable=True,
        radius_min_pixels=5,
        radius_max_pixels=18,
    )

    view = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=14, pitch=0)

    tooltip = {
        "html": (
            "<b style='font-size:14px'>{REA_Identi}</b><br/>"
            "{Dirección catastral}<br/>"
            "<span style='opacity:.8'>CHIP: {CHIP}</span>"
        ),
        "style": {
            "background": "#1A1F36", "color": "white",
            "font-size": "13px", "padding": "10px 14px",
            "border-radius": "8px",
        },
    }

    st.pydeck_chart(pdk.Deck(
        layers=[layer_pts],
        initial_view_state=view,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip=tooltip,
    ), use_container_width=True)
else:
    st.warning("Ningún identificador pudo ser ubicado en el mapa (no hay coordenadas).")

# ── 4. Tabla ─────────────────────────────────────────────────────────────────

st.markdown("### Predios a visitar")
st.caption("Selecciona filas para limitar la descarga GIS. Sin selección = descarga todos.")

disp_cols = ["REA_Identi", "Dirección catastral", "CHIP",
             "Barrio", "Localidad", "Estado", "En REAS", "Google Maps"]
df_disp = df_tabla[disp_cols].copy()

sel = st.dataframe(
    df_disp,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="multi-row",
    column_config={
        "Google Maps": st.column_config.LinkColumn(
            "Google Maps", display_text="📍 Ver en Maps"
        ),
        "En REAS": st.column_config.TextColumn("En REAS", width="small"),
        "Estado":  st.column_config.TextColumn("Estado depurado"),
    },
    height=400,
)

# ── 5. Descarga GIS ──────────────────────────────────────────────────────────

st.markdown("### Descargar información GIS completa")

selected_idx = sel.selection.rows if sel.selection.rows else list(range(len(df_tabla)))
ids_sel = df_tabla.iloc[selected_idx]["REA_Identi"].tolist()
st.caption(f"{'Todos' if not sel.selection.rows else len(ids_sel)} identificadores seleccionados")

# Construir tabla de exportación: unir reas, depuracion y gis
export_parts = []

# Base: columnas de geo lookup
df_base = df_tabla[df_tabla["REA_Identi"].isin(ids_sel)].drop(
    columns=["lon", "lat"], errors="ignore"
)
export_parts.append(df_base.set_index("REA_Identi"))

# Depuración (completa)
if not df_dep.empty and dep_id_col:
    cols_dep = [c for c in df_dep.columns if c != dep_id_col]
    df_dep_sel = (df_dep[df_dep[dep_id_col].isin(ids_sel)]
                  .set_index(dep_id_col)[cols_dep])
    # Evitar duplicar columnas ya en base
    nuevas_dep = [c for c in df_dep_sel.columns if c not in export_parts[0].columns]
    if nuevas_dep:
        export_parts.append(df_dep_sel[nuevas_dep])

# GIS
gis_id_col = _id_col(df_gis, ["Identificador", "REA_Identi"]) if not df_gis.empty else None
if gis_id_col:
    df_gis[gis_id_col] = df_gis[gis_id_col].astype(str).str.strip()
    cols_gis = [c for c in df_gis.columns if c != gis_id_col]
    df_gis_sel = (df_gis[df_gis[gis_id_col].isin(ids_sel)]
                  .set_index(gis_id_col)[cols_gis])
    nuevas_gis = [c for c in df_gis_sel.columns
                  if c not in export_parts[0].columns
                  and all(c not in p.columns for p in export_parts[1:])]
    if nuevas_gis:
        export_parts.append(df_gis_sel[nuevas_gis])

df_export = export_parts[0].copy()
for part in export_parts[1:]:
    df_export = df_export.join(part, how="left")
df_export = df_export.reset_index().rename(columns={"index": "REA_Identi"})

buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df_export.to_excel(writer, index=False, sheet_name="Visita")
buf.seek(0)

st.download_button(
    label="⬇ Descargar GIS completo (Excel)",
    data=buf.getvalue(),
    file_name="visita_gis.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
    type="primary",
)
