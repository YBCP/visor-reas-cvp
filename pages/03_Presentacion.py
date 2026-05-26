"""
Módulo 3 — Presentación
Tablero de control: KPIs + mapa + gráficos por estado y territorio
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR  = Path(__file__).parent.parent / "data"
INPUT_DIR = Path(__file__).parent.parent.parent / "Archivos de entrada"

NAVY  = "#1A1F36"
TEAL  = "#00C9A7"
AMBER = "#FFB547"
CORAL = "#FF6B6B"
SLATE = "#64748B"
BLUE  = "#4F8EF7"
PURP  = "#6A0DAD"
DBLUE = "#1565C0"

COLORES_ESTADO = {
    "Reasentamiento Terminado":               [0,   201, 167, 210],
    "En Proceso":                             [255, 181, 71,  210],
    "Adquisicion predial por IDIGER":         [21,  101, 192, 210],
    "Cierre Administrativo Sin Reasentamiento": [106, 13, 173, 210],
}
COLOR_DEFAULT = [150, 150, 150, 160]

# ── Carga ────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_capa_gj(shp_path: str, keep_cols: list) -> dict:
    try:
        import geopandas as gpd
        gdf = gpd.read_file(shp_path).to_crs("EPSG:4326")
        gdf = gdf[[c for c in keep_cols if c in gdf.columns] + ["geometry"]]
        return json.loads(gdf.to_json())
    except Exception as e:
        return {"__error__": str(e)}


@st.cache_data(show_spinner=False)
def _load_reas_gj() -> dict:
    p = DATA_DIR / "reas.geojson"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def _load_depuracion() -> pd.DataFrame:
    p = DATA_DIR / "depuracion.csv"
    if not p.exists():
        return None
    return pd.read_csv(p, encoding="utf-8-sig", low_memory=False)


def _color_escala(val, min_v, max_v, alpha=160):
    if max_v == min_v or val is None:
        return [200, 220, 255, alpha]
    t = max(0.0, min(1.0, (val - min_v) / (max_v - min_v)))
    return [int(200-180*t), int(220-150*t), int(255-55*t), alpha]


@st.cache_data(show_spinner=False, max_entries=8)
def _colorear_territorio(n_feats, vista_key, _gj, _conteos, id_field):
    if not _gj:
        return _gj
    vals = list(_conteos.values())
    min_v, max_v = (min(vals), max(vals)) if vals else (0, 1)
    feats = []
    for feat in _gj.get("features", []):
        props = dict(feat.get("properties") or {})
        key   = str(props.get(id_field, "")).strip()
        cnt   = _conteos.get(key, 0)
        props["_count"] = cnt
        props["_fill"]  = _color_escala(cnt, min_v, max_v)
        feats.append({"type": "Feature", "geometry": feat["geometry"], "properties": props})
    return {"type": "FeatureCollection", "features": feats}


@st.cache_data(show_spinner=False)
def _geo_lookup() -> dict:
    """REA_Identi → {LocNombre, NOMBRE_UPL} desde reas.geojson."""
    p = DATA_DIR / "reas.geojson"
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        gj = json.load(f)
    result = {}
    for feat in gj.get("features", []):
        props = feat.get("properties", {}) or {}
        rid = str(props.get("REA_Identi", "")).strip()
        if rid:
            result[rid] = {
                "LocNombre":  str(props.get("LocNombre", "") or ""),
                "NOMBRE_UPL": str(props.get("NOMBRE", "") or ""),
            }
    return result


def _enriquecer_reas(gj_reas, id_estado: dict) -> dict:
    """Inyecta ESTADO_DEPURADO y color en cada feature del GeoJSON REAS."""
    feats = []
    for feat in (gj_reas or {}).get("features", []):
        props = dict(feat.get("properties") or {})
        rea   = str(props.get("REA_Identi", "")).strip()
        est   = id_estado.get(rea, "")
        props["ESTADO_DEPURADO"] = est
        props["_fill"] = COLORES_ESTADO.get(est, COLOR_DEFAULT)
        feats.append({"type": "Feature", "geometry": feat["geometry"], "properties": props})
    return {"type": "FeatureCollection", "features": feats}


def _kpi(label, valor, color, pct=None):
    pct_html = (f'<div style="font-size:.7rem;color:{SLATE};margin-top:3px;">'
                f'{pct:.1f}%</div>' if pct is not None else "")
    return f"""
    <div style="background:white;border-radius:12px;padding:12px 14px;
                box-shadow:0 2px 10px rgba(0,0,0,.07);
                border-top:4px solid {color};text-align:center;">
      <div style="font-size:.62rem;font-weight:700;color:{SLATE};
                  text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px;">
        {label}</div>
      <div style="font-size:1.25rem;font-weight:900;color:{NAVY};">{valor}</div>
      {pct_html}
    </div>"""


# ════════════════════════════════════════════════════════════════════════════
# PÁGINA
# ════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="Presentación · CVP", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown(f"""
<div style="background:linear-gradient(135deg,{NAVY} 0%,#2C3560 100%);
            color:white;padding:14px 20px;border-radius:14px;
            box-shadow:0 4px 16px rgba(26,31,54,.22);margin-bottom:16px;">
  <div style="font-size:1rem;font-weight:800;">Módulo 3 — Presentación</div>
  <div style="margin-top:2px;opacity:.7;font-size:.78rem;">
    Tablero de control · Distribución territorial de predios REAS
  </div>
</div>""", unsafe_allow_html=True)

# ── Carga datos ───────────────────────────────────────────────────────────────
with st.spinner("Cargando capas..."):
    gj_loc = _load_capa_gj(
        str(INPUT_DIR / "Localidad" / "Loca.shp"),
        ["LocNombre", "LocCodigo", "LocArea"])
    gj_upl = _load_capa_gj(
        str(INPUT_DIR / "UPL" / "UnidadPlaneamientoLocal.shp"),
        ["CODIGO_UPL", "NOMBRE", "VOCACION", "AREA_HA", "SECTOR"])

gj_reas_raw = _load_reas_gj()
df_dep      = _load_depuracion()

_err_loc, _err_upl = None, None

# Enriquecer df_dep con LocNombre y NOMBRE_UPL si no existen (fueron excluidas de depuracion_slim)
if df_dep is not None:
    _glkp = _geo_lookup()
    _id_c_geo = next((c for c in df_dep.columns
                      if "rea" in c.lower() and "ident" in c.lower()), None)
    if _glkp and _id_c_geo:
        if "LocNombre" not in df_dep.columns or df_dep["LocNombre"].isna().all():
            df_dep = df_dep.copy()
            df_dep["LocNombre"]  = df_dep[_id_c_geo].astype(str).map(
                lambda x: _glkp.get(x, {}).get("LocNombre", ""))
            df_dep["NOMBRE_UPL"] = df_dep[_id_c_geo].astype(str).map(
                lambda x: _glkp.get(x, {}).get("NOMBRE_UPL", ""))
if isinstance(gj_loc, dict) and "__error__" in gj_loc:
    _err_loc = gj_loc["__error__"]; gj_loc = None
if isinstance(gj_upl, dict) and "__error__" in gj_upl:
    _err_upl = gj_upl["__error__"]; gj_upl = None

if df_dep is None:
    st.warning("Tabla Depuración no cargada. Ve al **Módulo 1**.", icon="📂")
    st.stop()

# ── Sidebar — filtros ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;
                color:rgba(255,255,255,.45);text-transform:uppercase;
                margin:8px 0 12px;">Vista y filtros</div>""", unsafe_allow_html=True)

    vista = st.radio("Agrupar por", ["Localidad", "UPL"],
                     label_visibility="collapsed", key="vista_radio")

    st.markdown("---")
    st.caption("Capas visibles")
    show_loc  = st.checkbox("Localidades", value=True,  key="ck_loc")
    show_upl  = st.checkbox("UPL",         value=False, key="ck_upl")
    show_reas = st.checkbox("REAS",        value=True,  key="ck_reas_p")

    st.markdown("---")
    st.caption("Filtros")

    _estados_all = sorted(df_dep["ESTADO_DEPURADO"].dropna().astype(str).unique())
    sel_estado = st.multiselect("Estado depurado", _estados_all, default=[],
                                help="Vacío = todos")

    _riesgo_col = next((c for c in ["TP_RIESGO", "Riesgo", "TIPO_RIESGO"]
                        if c in df_dep.columns), None)
    sel_riesgo = []
    if _riesgo_col:
        _riesgos_all = sorted(df_dep[_riesgo_col].dropna().astype(str)
                              .replace("nan","").replace("","").unique())
        _riesgos_all = [r for r in _riesgos_all if r]
        if _riesgos_all:
            sel_riesgo = st.multiselect("Tipo de riesgo", _riesgos_all, default=[],
                                        help="Vacío = todos")

    _loc_col = next((c for c in ["LocNombre", "LOCALIDA"] if c in df_dep.columns), None)
    sel_loc = []
    if _loc_col:
        _locs_all = sorted(df_dep[_loc_col].dropna().astype(str)
                           .replace("nan","").unique())
        _locs_all = [l for l in _locs_all if l]
        if _locs_all:
            sel_loc = st.multiselect("Localidad", _locs_all, default=[],
                                     help="Vacío = todas")

    if gj_loc is None:
        st.error(f"Localidad.shp: {_err_loc or 'no encontrado'}")
    if gj_upl is None:
        st.error(f"UPL.shp: {_err_upl or 'no encontrado'}")

# ── Aplicar filtros ───────────────────────────────────────────────────────────
df = df_dep.copy()
if sel_estado:
    df = df[df["ESTADO_DEPURADO"].isin(sel_estado)]
if sel_riesgo and _riesgo_col:
    df = df[df[_riesgo_col].astype(str).isin(sel_riesgo)]
if sel_loc and _loc_col:
    df = df[df[_loc_col].astype(str).isin(sel_loc)]

total    = len(df)
_id_col  = next((c for c in df.columns if "rea" in c.lower() and "ident" in c.lower()), None)

# ── KPIs ─────────────────────────────────────────────────────────────────────
n_term   = int((df["ESTADO_DEPURADO"] == "Reasentamiento Terminado").sum())
n_proc   = int((df["ESTADO_DEPURADO"] == "En Proceso").sum())
n_idiger = int((df["ESTADO_DEPURADO"] == "Adquisicion predial por IDIGER").sum())
n_cierre = int((df["ESTADO_DEPURADO"] == "Cierre Administrativo Sin Reasentamiento").sum())

k1, k2, k3, k4, k5 = st.columns(5)
k1.markdown(_kpi("Total predios",            f"{total:,}",        NAVY),  unsafe_allow_html=True)
k2.markdown(_kpi("Reasentamiento terminado", f"{n_term:,}",  TEAL,  n_term/total*100  if total else None), unsafe_allow_html=True)
k3.markdown(_kpi("En proceso",               f"{n_proc:,}",  AMBER, n_proc/total*100  if total else None), unsafe_allow_html=True)
k4.markdown(_kpi("Adq. predial IDIGER",      f"{n_idiger:,}", DBLUE, n_idiger/total*100 if total else None), unsafe_allow_html=True)
k5.markdown(_kpi("Cierre admin.",            f"{n_cierre:,}", PURP,  n_cierre/total*100 if total else None), unsafe_allow_html=True)

st.divider()

# ── Mapa + gráficos ───────────────────────────────────────────────────────────
col_mapa, col_graf = st.columns([5, 3], gap="medium")

# Conteos por territorio (sobre df filtrado)
cnt_loc: dict = {}
cnt_upl: dict = {}
if _loc_col and _loc_col in df.columns:
    cnt_loc = (df[_loc_col].astype(str).str.strip()
               .replace("nan","").replace("",pd.NA)
               .dropna().value_counts().to_dict())
_upl_col = next((c for c in ["NOMBRE_UPL", "NOMBRE", "UPL"] if c in df.columns), None)
if _upl_col:
    cnt_upl = (df[_upl_col].astype(str).str.strip()
               .replace("nan","").replace("",pd.NA)
               .dropna().value_counts().to_dict())

_n_loc = len(gj_loc.get("features",[])) if gj_loc else 0
_n_upl = len(gj_upl.get("features",[])) if gj_upl else 0
gj_loc_col = (_colorear_territorio(_n_loc, "loc", gj_loc, cnt_loc, "LocNombre")
              if gj_loc and cnt_loc else gj_loc)
# cnt_upl está indexado por NOMBRE_UPL (=NOMBRE en geojson UPL)
gj_upl_col = (_colorear_territorio(_n_upl, "upl", gj_upl, cnt_upl, "NOMBRE")
              if gj_upl and cnt_upl else gj_upl)

# REAS enriquecido con estado + color
_id_estado: dict = {}
if _id_col and "ESTADO_DEPURADO" in df.columns:
    _id_estado = dict(zip(df[_id_col].astype(str), df["ESTADO_DEPURADO"].astype(str)))
gj_reas_col = _enriquecer_reas(gj_reas_raw, _id_estado) if gj_reas_raw else None

# ── MAPA ─────────────────────────────────────────────────────────────────────
with col_mapa:
    try:
        import pydeck as pdk

        layers = []
        if show_loc and gj_loc_col:
            layers.append(pdk.Layer(
                "GeoJsonLayer", data=gj_loc_col,
                get_fill_color="properties._fill",
                get_line_color=[60, 70, 130, 220],
                get_line_width=80, line_width_min_pixels=1,
                auto_highlight=True, highlight_color=[255,220,50,130],
                pickable=True, id="loc_layer"))

        if show_upl and gj_upl_col:
            layers.append(pdk.Layer(
                "GeoJsonLayer", data=gj_upl_col,
                get_fill_color="properties._fill" if cnt_upl else [170,230,190,80],
                get_line_color=[30,120,70,200],
                get_line_width=50, line_width_min_pixels=1,
                auto_highlight=True, highlight_color=[80,255,140,130],
                pickable=True, id="upl_layer"))

        if show_reas and gj_reas_col:
            layers.append(pdk.Layer(
                "GeoJsonLayer", data=gj_reas_col,
                get_fill_color="properties._fill",
                get_line_color=[80,80,80,80],
                get_line_width=0, line_width_min_pixels=0,
                pickable=True, id="reas_layer_p"))

        _tip_html = (
            "<b>{LocNombre}</b><br/>Predios: <b>{_count}</b>"
            if vista == "Localidad"
            else "<b>{NOMBRE}</b><br/>Predios: <b>{_count}</b>"
        )
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(
                latitude=4.6534, longitude=-74.0836, zoom=10.5, pitch=0),
            tooltip={"html": _tip_html,
                     "style": {"backgroundColor":NAVY,"color":"white",
                               "fontSize":"12px","borderRadius":"8px",
                               "padding":"8px 12px"}},
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        )
        st.pydeck_chart(deck, use_container_width=True, height=520)

        # Leyenda de colores REAS
        if show_reas:
            leyenda_html = '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:6px;">'
            for est, rgb in COLORES_ESTADO.items():
                c = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
                leyenda_html += (f'<div style="display:flex;align-items:center;gap:5px;'
                                 f'font-size:.7rem;color:{SLATE};">'
                                 f'<div style="width:12px;height:12px;border-radius:3px;'
                                 f'background:{c};flex-shrink:0;"></div>{est}</div>')
            leyenda_html += "</div>"
            st.markdown(leyenda_html, unsafe_allow_html=True)

    except ImportError:
        st.error("pydeck no instalado.")

# ── GRÁFICOS ─────────────────────────────────────────────────────────────────
with col_graf:
    try:
        import altair as alt

        # 1. Por estado depurado
        st.markdown("#### Estado depurado")
        _est = (df["ESTADO_DEPURADO"].astype(str).str.strip()
                .replace("nan","Sin información")
                .value_counts().rename_axis("Estado").reset_index(name="n"))
        _pal_dom = ["Reasentamiento Terminado","En Proceso",
                    "Adquisicion predial por IDIGER",
                    "Cierre Administrativo Sin Reasentamiento"]
        _pal_rng = [TEAL, AMBER, DBLUE, PURP]
        chart_est = (
            alt.Chart(_est)
            .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
            .encode(
                x=alt.X("n:Q", title="Predios"),
                y=alt.Y("Estado:N", sort="-x", title=None,
                        axis=alt.Axis(labelLimit=320, labelOverlap=False)),
                color=alt.Color("Estado:N",
                    scale=alt.Scale(domain=_pal_dom, range=_pal_rng), legend=None),
                tooltip=["Estado:N", alt.Tooltip("n:Q", title="Predios", format=",")],
            ).properties(height=max(110, len(_est)*36))
        )
        st.altair_chart(chart_est, use_container_width=True)

        # 2. Acción PPT (solo para En Proceso)
        if "ESTADO_PPT" in df.columns:
            df_proc = df[df["ESTADO_DEPURADO"] == "En Proceso"]
            if not df_proc.empty:
                st.markdown("#### Acción PPT (en proceso)")
                _ppt = (df_proc["ESTADO_PPT"].astype(str)
                        .replace("nan","Sin clasificar").replace("<NA>","Sin clasificar")
                        .value_counts().rename_axis("Acción").reset_index(name="n"))
                chart_ppt = (
                    alt.Chart(_ppt)
                    .mark_bar(color=AMBER,
                              cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
                    .encode(
                        x=alt.X("n:Q", title="Predios"),
                        y=alt.Y("Acción:N", sort="-x", title=None,
                                axis=alt.Axis(labelLimit=280, labelOverlap=False)),
                        tooltip=["Acción:N",
                                 alt.Tooltip("n:Q", title="Predios", format=",")],
                    ).properties(height=max(110, len(_ppt)*36))
                )
                st.altair_chart(chart_ppt, use_container_width=True)

        # 3. Por territorio
        _conteos_vis = cnt_loc if vista == "Localidad" else cnt_upl
        _campo_vis   = "LocNombre" if vista == "Localidad" else "NOMBRE"
        if _conteos_vis:
            st.markdown(f"#### Por {vista}")
            df_ch = (pd.Series(_conteos_vis)
                     .sort_values(ascending=False).head(15)
                     .rename_axis("Territorio").reset_index(name="Predios"))
            chart_ter = (
                alt.Chart(df_ch)
                .mark_bar(color=BLUE,
                          cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
                .encode(
                    x=alt.X("Predios:Q"),
                    y=alt.Y("Territorio:N", sort="-x", title=None,
                            axis=alt.Axis(labelLimit=280, labelOverlap=False)),
                    tooltip=["Territorio:N",
                             alt.Tooltip("Predios:Q", title="Predios", format=",")],
                ).properties(height=max(200, min(len(df_ch)*28, 460)))
            )
            st.altair_chart(chart_ter, use_container_width=True)

    except ImportError:
        st.warning("altair no instalado.")
