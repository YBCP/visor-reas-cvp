"""
Módulo 1 — Datos
Descarga de archivos disponibles y enlace al repositorio para actualizar datos.
"""

from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"

NAVY = "#1A1F36"
BLUE = "#4F8EF7"
SLATE = "#64748B"

REPO_URL = "https://github.com/YBCP/visor-reas-cvp/tree/master/data"

ARCHIVOS = [
    ("reas.geojson",        "Capa REAS",           "GeoJSON",  "application/geo+json"),
    ("lote.geojson",        "Capa Lote (Catastro)", "GeoJSON",  "application/geo+json"),
    ("depuracion.csv",      "Depuración",           "CSV",      "text/csv"),
    ("gis.csv",             "GIS",                  "CSV",      "text/csv"),
    ("propietario.csv",     "Propietario",          "CSV",      "text/csv"),
    ("origen_destino.xlsx", "Origen Destino",       "XLSX",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
]


def _file_info(filename: str):
    path = DATA_DIR / filename
    if path.exists():
        stat = path.stat()
        kb   = stat.st_size / 1024
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
        size_str = f"{kb/1024:.1f} MB" if kb > 1024 else f"{kb:.0f} KB"
        return True, mtime, size_str
    return False, None, None


# ── Encabezado ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,{NAVY} 0%,#2C3560 100%);
            color:white;padding:20px 28px;border-radius:14px;margin-bottom:22px;
            box-shadow:0 6px 24px rgba(26,31,54,.22);">
  <h2 style="margin:0;font-size:1.25rem;font-weight:800;">Módulo 1 — Datos</h2>
  <p style="margin:6px 0 0;opacity:.75;font-size:.88rem;">
    Descarga los archivos de datos activos · Para actualizar, reemplaza el archivo en el repositorio
  </p>
</div>""", unsafe_allow_html=True)

# ── Enlace al repo ────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:12px;
            padding:14px 18px;margin-bottom:24px;display:flex;align-items:center;gap:12px;">
  <span style="font-size:1.4rem;">🔗</span>
  <div>
    <div style="font-size:.85rem;font-weight:700;color:#1E40AF;">Repositorio de datos</div>
    <div style="font-size:.82rem;color:#3B82F6;margin-top:2px;">
      Para actualizar un archivo: ve al repositorio, abre la carpeta
      <code>data/</code>, selecciona el archivo y usa el botón <b>Edit / Upload</b>.
    </div>
    <a href="{REPO_URL}" target="_blank"
       style="font-size:.82rem;color:#2563EB;font-weight:600;">
      📁 Abrir carpeta data/ en GitHub →
    </a>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabla de archivos ─────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:0 0 14px;">
  <div style="width:4px;height:20px;background:linear-gradient(180deg,{BLUE},#A78BFA);
              border-radius:2px;flex-shrink:0;"></div>
  <span style="font-size:.95rem;font-weight:700;color:#1E293B;">Archivos disponibles</span>
</div>
""", unsafe_allow_html=True)

for fname, label, fmt, mime in ARCHIVOS:
    ok, mtime, size_str = _file_info(fname)
    path = DATA_DIR / fname

    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])

    with c1:
        st.markdown(f"**{label}**  \n`{fname}`")
    with c2:
        if ok:
            st.markdown(
                '<span style="background:#00C9A718;color:#00C9A7;border:1px solid #00C9A744;'
                'border-radius:20px;padding:2px 10px;font-size:.75rem;font-weight:600;">✓ Disponible</span>',
                unsafe_allow_html=True)
            st.caption(f"{size_str}")
        else:
            st.markdown(
                '<span style="background:#FF6B6B18;color:#FF6B6B;border:1px solid #FF6B6B44;'
                'border-radius:20px;padding:2px 10px;font-size:.75rem;font-weight:600;">✗ No encontrado</span>',
                unsafe_allow_html=True)
    with c3:
        if ok:
            st.caption(f"Actualizado: {mtime}")
    with c4:
        if ok:
            st.download_button(
                label=f"⬇ {fmt}",
                data=path.read_bytes(),
                file_name=fname,
                mime=mime,
                key=f"dl_{fname}",
                use_container_width=True,
            )

    st.divider()
