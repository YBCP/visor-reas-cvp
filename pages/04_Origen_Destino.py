"""
Módulo 4 — Origen Destino
Flujos de reasentamiento: localidad origen → proyecto → localidad destino
"""

from pathlib import Path
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"

NAVY  = "#1A1F36"
TEAL  = "#00C9A7"
AMBER = "#FFB547"
CORAL = "#FF6B6B"
BLUE  = "#4F8EF7"
SLATE = "#64748B"


# ── Carga ─────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _cargar(path: str) -> pd.DataFrame:
    df_raw = pd.read_excel(path)
    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    year_cols = [c for c in df_raw.columns
                 if str(c).isdigit() and 2000 <= int(str(c)) <= 2040]
    id_cols   = [c for c in df_raw.columns
                 if c not in year_cols and str(c).upper() != "TOTAL"]

    df = df_raw.melt(id_vars=id_cols, value_vars=year_cols,
                     var_name="Año", value_name="Hogares")
    df["Año"]    = df["Año"].astype(int)
    df["Hogares"] = pd.to_numeric(df["Hogares"], errors="coerce").fillna(0).astype(int)

    for col in ["Latitud", "Longitud"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            mask = df[col].abs() > 1000
            df.loc[mask, col] = df.loc[mask, col] / 1_000_000

    renames = {}
    for c in df.columns:
        cl = c.lower()
        if   "nombre" in cl and "proyecto" in cl:    renames[c] = "Proyecto"
        elif "localidad" in cl and "origen" in cl:   renames[c] = "Loc_Origen"
        elif "localidad" in cl and "proyecto" in cl: renames[c] = "Loc_Destino"
        elif "tipo" in cl and "proyecto" in cl:      renames[c] = "Tipo_Proyecto"
        elif cl == "latitud":                         renames[c] = "Lat"
        elif cl == "longitud":                        renames[c] = "Lon"
    df = df.rename(columns=renames)

    for col in ["Proyecto", "Loc_Origen", "Loc_Destino", "Tipo_Proyecto"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def _fuente() -> str | None:
    p = DATA_DIR / "origen_destino.xlsx"
    return str(p) if p.exists() else None


# ── Página ────────────────────────────────────────────────────────────────────


st.markdown(f"""
<div style="background:linear-gradient(135deg,{NAVY} 0%,#2C3560 100%);
            color:white;padding:14px 20px;border-radius:14px;
            box-shadow:0 4px 16px rgba(26,31,54,.22);margin-bottom:16px;">
  <div style="font-size:1rem;font-weight:800;">Módulo 4 — Origen Destino</div>
  <div style="margin-top:2px;opacity:.7;font-size:.78rem;">
    Flujos de reasentamiento · localidad origen → proyecto → localidad destino
  </div>
</div>""", unsafe_allow_html=True)

ruta = _fuente()
if ruta is None:
    st.warning("Archivo **Origen destino maestro.xlsx** no encontrado. "
               "Cárgalo desde el **Módulo 1 — Carga de Datos**.", icon="📂")
    st.stop()

with st.spinner("Cargando datos..."):
    df_base = _cargar(ruta)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""<div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;
                color:rgba(255,255,255,.45);text-transform:uppercase;
                margin:8px 0 12px;">Filtros</div>""", unsafe_allow_html=True)

    todos_años    = sorted(df_base["Año"].unique())
    todos_tipos   = sorted(df_base["Tipo_Proyecto"].dropna().unique()) if "Tipo_Proyecto"  in df_base.columns else []
    todos_origen  = sorted(df_base["Loc_Origen"].dropna().unique())    if "Loc_Origen"     in df_base.columns else []
    todos_destino = sorted(df_base["Loc_Destino"].dropna().unique())   if "Loc_Destino"    in df_base.columns else []
    todos_proy    = sorted(df_base["Proyecto"].dropna().unique())       if "Proyecto"       in df_base.columns else []

    # Año: "Total" por defecto (todos seleccionados)
    sel_año = st.multiselect("Año (vacío = total)", todos_años,
                              default=[], key="od_año",
                              help="Deja vacío para ver el total consolidado")
    sel_tipo   = st.multiselect("Tipo proyecto",     todos_tipos,   default=[], key="od_tipo")
    sel_origen = st.multiselect("Localidad origen",  todos_origen,  default=[], key="od_orig")
    sel_dest   = st.multiselect("Localidad destino", todos_destino, default=[], key="od_dest")
    sel_proy   = st.multiselect("Proyecto",          todos_proy,    default=[], key="od_proy")


# Aplicar filtros (vacío = sin filtro = total)
df = df_base.copy()
if sel_año:    df = df[df["Año"].isin(sel_año)]
if sel_tipo:   df = df[df["Tipo_Proyecto"].isin(sel_tipo)]
if sel_origen: df = df[df["Loc_Origen"].isin(sel_origen)]
if sel_dest:   df = df[df["Loc_Destino"].isin(sel_dest)]
if sel_proy:   df = df[df["Proyecto"].isin(sel_proy)]

df_pos = df[df["Hogares"] > 0]

if df_pos.empty:
    st.info("Sin datos para los filtros seleccionados.")
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────────

total_hog  = int(df_pos["Hogares"].sum())
total_proy = df_pos["Proyecto"].nunique() if "Proyecto" in df_pos.columns else 0

orig_top = (df_pos.groupby("Loc_Origen")["Hogares"].sum().idxmax()
            if "Loc_Origen" in df_pos.columns else "—")
dest_top = (df_pos.groupby("Loc_Destino")["Hogares"].sum().idxmax()
            if "Loc_Destino" in df_pos.columns else "—")

pct_cb = 0.0
if "Loc_Origen" in df_pos.columns and total_hog > 0:
    cb_v = [c for c in df_pos["Loc_Origen"].unique() if "bol" in c.lower()]
    if cb_v:
        pct_cb = df_pos[df_pos["Loc_Origen"].isin(cb_v)]["Hogares"].sum() / total_hog * 100

def _kpi_card(label, value, color=BLUE):
    return f"""
    <div style="background:white;border-radius:12px;padding:14px 16px;
                box-shadow:0 2px 10px rgba(0,0,0,.07);
                border-top:4px solid {color};text-align:center;">
      <div style="font-size:.68rem;font-weight:700;color:{SLATE};
                  text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">
        {label}</div>
      <div style="font-size:1.15rem;font-weight:900;color:{NAVY};
                  line-height:1.2;word-break:break-word;">
        {value}</div>
    </div>"""

k1, k2, k3, k4, k5 = st.columns(5)
k1.markdown(_kpi_card("Total hogares",     f"{total_hog:,}",      TEAL),   unsafe_allow_html=True)
k2.markdown(_kpi_card("Proyectos",         str(total_proy),        BLUE),   unsafe_allow_html=True)
k3.markdown(_kpi_card("Principal origen",  str(orig_top),          AMBER),  unsafe_allow_html=True)
k4.markdown(_kpi_card("Principal destino", str(dest_top),          CORAL),  unsafe_allow_html=True)
k5.markdown(_kpi_card("% Ciudad Bolívar",  f"{pct_cb:.1f}%",       NAVY),   unsafe_allow_html=True)

st.divider()

# ── Sankey ────────────────────────────────────────────────────────────────────

st.markdown("#### Flujo Origen → Proyecto → Destino")

try:
    import plotly.graph_objects as go

    agg_op = df_pos.groupby(["Loc_Origen",  "Proyecto"])["Hogares"].sum().reset_index()
    agg_pd = df_pos.groupby(["Proyecto", "Loc_Destino"])["Hogares"].sum().reset_index()

    origenes  = sorted(agg_op["Loc_Origen"].unique())
    proyectos = sorted(agg_op["Proyecto"].unique())
    destinos  = sorted(agg_pd["Loc_Destino"].unique())

    # Prefijos solo para desambiguar si un nombre aparece en varias columnas
    _dup = set(origenes) & set(destinos)
    def _lbl_o(n): return f"Origen: {n}" if n in _dup else n
    def _lbl_d(n): return f"Destino: {n}" if n in _dup else n

    nodos = ([_lbl_o(o) for o in origenes] +
             list(proyectos) +
             [_lbl_d(d) for d in destinos])
    idx = {n: i for i, n in enumerate(nodos)}

    src, tgt, val = [], [], []
    for _, r in agg_op.iterrows():
        src.append(idx[_lbl_o(r["Loc_Origen"])])
        tgt.append(idx[r["Proyecto"]])
        val.append(int(r["Hogares"]))
    for _, r in agg_pd.iterrows():
        src.append(idx[r["Proyecto"]])
        tgt.append(idx[_lbl_d(r["Loc_Destino"])])
        val.append(int(r["Hogares"]))

    _pal_n = (["#4F8EF7"] * len(origenes) +
              ["#00C9A7"] * len(proyectos) +
              ["#FFB547"] * len(destinos))

    fig_sk = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=nodos,
            color=_pal_n,
            pad=20, thickness=20,
            line=dict(color="white", width=0.5),
            hovertemplate="%{label}<br>Total: <b>%{value:,}</b> hogares<extra></extra>",
        ),
        link=dict(
            source=src, target=tgt, value=val,
            color="rgba(100,116,139,0.22)",
            hovertemplate=(
                "Origen: %{source.label}<br>"
                "Destino: %{target.label}<br>"
                "<b>%{value:,}</b> hogares<extra></extra>"
            ),
        ),
    ))
    fig_sk.update_layout(
        font=dict(family="Arial, sans-serif", size=16, color="#1E293B"),
        margin=dict(l=20, r=20, t=10, b=10),
        height=460,
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    st.plotly_chart(fig_sk, use_container_width=True)

except ImportError:
    st.warning("plotly no instalado. Ejecuta: `pip install plotly`")

st.divider()

# ── Heatmap + Mapa ────────────────────────────────────────────────────────────

col_heat, col_mapa = st.columns([3, 2], gap="medium")

with col_heat:
    st.markdown("#### Hogares: Origen vs Destino")
    try:
        import altair as alt
        hm = df_pos.groupby(["Loc_Origen", "Loc_Destino"])["Hogares"].sum().reset_index()
        chart_hm = (
            alt.Chart(hm)
            .mark_rect()
            .encode(
                x=alt.X("Loc_Destino:N", title="Destino",
                         axis=alt.Axis(labelAngle=-35)),
                y=alt.Y("Loc_Origen:N", title="Origen"),
                color=alt.Color("Hogares:Q",
                                scale=alt.Scale(scheme="blues"),
                                title="Hogares"),
                tooltip=["Loc_Origen:N", "Loc_Destino:N", "Hogares:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart_hm, use_container_width=True)
    except ImportError:
        st.warning("altair no instalado.")

with col_mapa:
    st.markdown("#### Mapa de proyectos")
    try:
        import pydeck as pdk
        _años_vis = sorted(df_pos["Año"].unique())
        _label_vig = (str(_años_vis[0]) if len(_años_vis) == 1
                      else f"{min(_años_vis)}–{max(_años_vis)}")

        pts = (df_pos.groupby(["Proyecto", "Lat", "Lon", "Loc_Destino"])
               .agg(Hogares=("Hogares", "sum"))
               .reset_index()
               .dropna(subset=["Lat", "Lon"]))
        pts["Vigencia"] = _label_vig
        pts = pts[(pts["Lat"].between(3.5, 5.2)) & (pts["Lon"].between(-75, -73))]

        layer = pdk.Layer(
            "ScatterplotLayer", data=pts,
            get_position="[Lon, Lat]",
            get_fill_color=[79, 142, 247, 200],
            get_radius="Hogares * 8",
            radius_min_pixels=8, radius_max_pixels=45,
            pickable=True,
        )
        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(
                latitude=4.65, longitude=-74.09, zoom=10, pitch=0),
            tooltip={"html": "<b>{Proyecto}</b><br/>{Loc_Destino}<br/>"
                             "Hogares: <b>{Hogares}</b><br/>"
                             "Vigencia: {Vigencia}",
                     "style": {"backgroundColor": NAVY, "color": "white",
                                "fontSize": "12px", "borderRadius": "8px",
                                "padding": "8px 12px"}},
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        )
        st.pydeck_chart(deck, use_container_width=True, height=320)
    except ImportError:
        st.warning("pydeck no instalado.")

st.divider()

# ── Ranking + Serie temporal ──────────────────────────────────────────────────

col_rank, col_serie = st.columns(2, gap="medium")

with col_rank:
    st.markdown("#### Ranking por localidad")

    def _tabla_ranking(df_rk, col_nombre, color):
        max_v = df_rk["Hogares"].max() or 1
        rows_html = ""
        for _, r in df_rk.iterrows():
            pct = r["Hogares"] / max_v * 100
            rows_html += f"""
            <div style="margin-bottom:7px;">
              <div style="display:flex;justify-content:space-between;
                          font-size:.78rem;margin-bottom:2px;">
                <span style="color:{NAVY};font-weight:600;
                             white-space:nowrap;overflow:hidden;
                             text-overflow:ellipsis;max-width:65%;">
                  {r[col_nombre]}</span>
                <span style="color:{SLATE};font-weight:700;">{r['Hogares']:,}</span>
              </div>
              <div style="background:#F1F5F9;border-radius:4px;height:6px;">
                <div style="background:{color};border-radius:4px;
                            height:6px;width:{pct:.1f}%;"></div>
              </div>
            </div>"""
        return f'<div style="padding:4px 0">{rows_html}</div>'

    rk_orig = (df_pos.groupby("Loc_Origen")["Hogares"].sum().reset_index()
               .sort_values("Hogares", ascending=False).head(10))
    rk_dest = (df_pos.groupby("Loc_Destino")["Hogares"].sum().reset_index()
               .sort_values("Hogares", ascending=False).head(10))

    st.caption("**Orígenes**")
    st.markdown(_tabla_ranking(rk_orig, "Loc_Origen", BLUE), unsafe_allow_html=True)
    st.caption("**Destinos**")
    st.markdown(_tabla_ranking(rk_dest, "Loc_Destino", TEAL), unsafe_allow_html=True)

with col_serie:
    st.markdown("#### Hogares por vigencia")
    try:
        import altair as alt
        ts = df_base[df_base["Hogares"] > 0].groupby("Año")["Hogares"].sum().reset_index()

        chart_ts = (
            alt.Chart(ts)
            .mark_line(point=alt.OverlayMarkDef(filled=True, size=80), color=BLUE, strokeWidth=2.5)
            .encode(
                x=alt.X("Año:O", title="Vigencia"),
                y=alt.Y("Hogares:Q", title="Hogares"),
                tooltip=[alt.Tooltip("Año:O", title="Vigencia"),
                         alt.Tooltip("Hogares:Q", title="Hogares", format=",")],
            )
            .properties(height=300)
        )
        # Etiquetas de valor sobre cada punto
        labels = (
            alt.Chart(ts)
            .mark_text(dy=-12, fontSize=11, color=NAVY, fontWeight="bold")
            .encode(
                x=alt.X("Año:O"),
                y=alt.Y("Hogares:Q"),
                text=alt.Text("Hogares:Q", format=","),
            )
        )
        st.altair_chart(chart_ts + labels, use_container_width=True)
    except ImportError:
        st.warning("altair no instalado.")

st.divider()

# ── Tabla ─────────────────────────────────────────────────────────────────────

st.markdown("#### Tabla detallada")

cols_show = [c for c in ["Año", "Proyecto", "Tipo_Proyecto",
                          "Loc_Origen", "Loc_Destino", "Hogares"]
             if c in df_pos.columns]
grp_cols  = [c for c in cols_show if c != "Hogares"]
df_tabla  = (df_pos[cols_show]
             .groupby(grp_cols)["Hogares"].sum()
             .reset_index()
             .sort_values("Hogares", ascending=False))

st.dataframe(df_tabla, use_container_width=True, hide_index=True, height=340,
             column_config={"Hogares": st.column_config.NumberColumn(format="%d")})

dl1, dl2 = st.columns(2)
csv = df_tabla.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
dl1.download_button("⬇ Descargar CSV", csv, "origen_destino_filtrado.csv",
                    "text/csv", key="dl_od_csv")

try:
    import io, openpyxl  # noqa: F401
    _buf = io.BytesIO()
    df_tabla.to_excel(_buf, index=False, engine="openpyxl")
    dl2.download_button("⬇ Descargar Excel", _buf.getvalue(),
                        "origen_destino_filtrado.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_od_xlsx")
except ImportError:
    dl2.caption("openpyxl no instalado para Excel")
