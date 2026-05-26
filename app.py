"""
Visor Geográfico CVP — app principal
"""

import streamlit as st

st.set_page_config(
    page_title="Visor REAS",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS global (se aplica en todas las páginas) ──────────────────────────────
NAVY  = "#1A1F36"
BLUE  = "#4F8EF7"
SLATE = "#64748B"
BG    = "#F0F4FF"

st.markdown(f"""
<style>
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {NAVY} 0%, #252D4A 100%);
    border-right: none;
    box-shadow: 4px 0 24px rgba(0,0,0,.18);
}}
[data-testid="stSidebar"] > div > div > div > div > div p,
[data-testid="stSidebar"] > div > div > div > div > div span,
[data-testid="stSidebar"] label {{
    color: rgba(255,255,255,.85) !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,.12) !important;
    margin: 12px 0 !important;
}}
[data-testid="stAppViewContainer"] > .main {{
    background: {BG};
}}
.block-container {{
    padding-top: 1.5rem !important;
}}
[data-testid="stWidgetLabel"] {{
    font-weight: 600 !important;
    font-size: .82rem !important;
    color: {SLATE} !important;
    text-transform: uppercase !important;
    letter-spacing: .04em !important;
}}
/* ── Navegación lateral (páginas) ── */
[data-testid="stSidebarNavLink"] {{
    border-radius: 10px !important;
    padding: 7px 12px !important;
    margin: 2px 4px !important;
    transition: background .15s !important;
}}
[data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNavLink"] p {{
    color: rgba(255,255,255,.88) !important;
    font-size: .85rem !important;
    font-weight: 500 !important;
}}
[data-testid="stSidebarNavLink"]:hover {{
    background: rgba(255,255,255,.1) !important;
}}
[data-testid="stSidebarNavLink"]:hover span,
[data-testid="stSidebarNavLink"]:hover p {{
    color: white !important;
    font-weight: 600 !important;
}}
[data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebarNavLink"][aria-selected="true"] {{
    background: rgba(79,142,247,.28) !important;
    border-left: 3px solid #4F8EF7 !important;
}}
[data-testid="stSidebarNavLink"][aria-current="page"] span,
[data-testid="stSidebarNavLink"][aria-selected="true"] span {{
    color: white !important;
    font-weight: 700 !important;
}}
/* Título de sección en la nav */
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarNavSectionHeader"] {{
    color: rgba(255,255,255,.45) !important;
    font-size: .7rem !important;
    text-transform: uppercase !important;
    letter-spacing: .08em !important;
}}
[data-testid="stAlert"] {{ border-radius: 12px !important; }}
[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 2px 16px rgba(0,0,0,.06) !important;
}}
</style>
""", unsafe_allow_html=True)


# ── Página de inicio ─────────────────────────────────────────────────────────
def _home():
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{NAVY} 0%,#2C3560 100%);
                color:white;padding:28px 32px;border-radius:16px;margin-bottom:28px;
                box-shadow:0 6px 24px rgba(26,31,54,.22);">
      <h1 style="margin:0;font-size:1.8rem;font-weight:900;letter-spacing:-.02em;">
        Visor Geográfico CVP
      </h1>
      <p style="margin:8px 0 0;opacity:.75;font-size:.95rem;">
        Sistema de visualización y consulta de predios en reasentamiento · Bogotá D.C.
      </p>
    </div>
    """, unsafe_allow_html=True)

    def _modulo_card(col, numero, titulo, descripcion, color, icono):
        col.markdown(f"""
        <div style="background:white;border-radius:16px;padding:24px 20px;
                    box-shadow:0 4px 20px rgba(0,0,0,.07);
                    border-top:4px solid {color};height:100%;">
          <div style="font-size:2rem;margin-bottom:10px;">{icono}</div>
          <div style="font-size:.68rem;font-weight:700;color:{SLATE};
                      text-transform:uppercase;letter-spacing:.1em;
                      margin-bottom:4px;">Módulo {numero}</div>
          <div style="font-size:1.05rem;font-weight:800;color:#1E293B;
                      margin-bottom:8px;">{titulo}</div>
          <div style="font-size:.85rem;color:{SLATE};line-height:1.5;">
            {descripcion}
          </div>
        </div>
        """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    _modulo_card(col1, "1", "Carga de Datos",
        "Convierte capas SHP a GeoJSON y carga las tablas de atributos (Propietario, GIS, Depuración, Origen Destino).",
        "#4F8EF7", "📂")
    _modulo_card(col2, "2", "Consulta",
        "Busca predios por código REA, chip, dirección o coordenadas. Visualiza la ficha completa con 5 pestañas de información.",
        "#00C9A7", "🔍")
    _modulo_card(col3, "3", "Presentación",
        "Tablero de control con KPIs, mapa de calor por localidad/UPL y gráficos por estado depurado y acción PPT.",
        "#FFB547", "📊")

    st.markdown("<br>", unsafe_allow_html=True)

    col4, col5, col6 = st.columns(3)
    _modulo_card(col4, "4", "Origen Destino",
        "Diagrama de flujo Sankey entre localidades de origen y destino de los hogares reasentados.",
        "#FF6B6B", "🔄")
    _modulo_card(col5, "5", "Programar Visita",
        "Carga una lista de identificadores REAS, visualiza marcadores en el mapa y descarga la información GIS completa.",
        "#A78BFA", "📍")
    col6.markdown("""
    <div style="background:#F8FAFC;border-radius:16px;padding:24px 20px;
                box-shadow:0 4px 20px rgba(0,0,0,.04);border-top:4px solid #E2E8F0;
                height:100%;display:flex;align-items:center;justify-content:center;">
      <div style="text-align:center;color:#94A3B8;font-size:.85rem;">
        Más módulos próximamente
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Usa el menú de la barra lateral izquierda para navegar entre módulos.", icon="👈")


# ── Enrutador de páginas ─────────────────────────────────────────────────────
pg = st.navigation([
    st.Page(_home,                           title="Visor REAS",     icon="🗺️"),
    st.Page("pages/01_Carga_de_Datos.py",    title="Carga de Datos", icon="📂"),
    st.Page("pages/02_Consulta.py",          title="Consulta",       icon="🔍"),
    st.Page("pages/03_Presentacion.py",      title="Presentación",   icon="📊"),
    st.Page("pages/04_Origen_Destino.py",    title="Origen Destino", icon="🔄"),
    st.Page("pages/05_Programar_Visita.py",  title="Programar Visita", icon="📍"),
])
pg.run()
