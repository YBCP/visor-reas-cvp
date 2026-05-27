"""
Módulo 2 — Consulta
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"
sys.path.insert(0, str(Path(__file__).parent.parent))

NAVY  = "#1A1F36"
BLUE  = "#4F8EF7"
TEAL  = "#00C9A7"
AMBER = "#FFB547"
CORAL = "#FF6B6B"
SLATE = "#64748B"

_COLOR_ESTADO = {
    "Reasentamiento Terminado":               [0,   201, 167, 200],
    "En Proceso":                             [255, 181, 71,  200],
    "Adquisicion predial por IDIGER":         [21,  101, 192, 200],
    "Cierre Administrativo Sin Reasentamiento": [106, 13, 173, 200],
}
_COLOR_RIESGO = {
    "Remoción en masa":   [204, 0, 0, 200],
    "Inundación":         [21, 101, 192, 200],
    "Avenida torrencial": [230, 92, 0, 200],
}
_COLOR_TIPO = {
    "Predio": [204, 0, 0, 200],
    "Mejora": [0, 122, 61, 200],
    "Lote":   [255, 195, 0, 200],
}

def _norm(s: str) -> str:
    return unicodedata.normalize("NFD", s.upper()).encode("ascii", "ignore").decode()
_COLOR_DEFAULT    = [150, 150, 150, 150]
_COLOR_SELECTED   = [255, 220, 0, 230]


# ── Carga ─────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Cargando capa REAS...")
def load_reas():
    p = DATA_DIR / "reas.geojson"
    if not p.exists():
        return None, None
    with open(p, encoding="utf-8") as f:
        gj = json.load(f)
    rows = []
    for feat in gj.get("features", []):
        props = feat.get("properties", {}) or {}
        geom  = feat.get("geometry", {})
        lat, lon = _centroid(geom)
        props["_lat"]  = lat
        props["_lon"]  = lon
        props["_geom"] = json.dumps(geom)
        rows.append(props)
    df = pd.DataFrame(rows)
    for c in ["REA_Identi", "chip", "CHIP_VLI_1", "DIR_CAMPO", "DIR_CATAST",
              "REA_ESTADO", "TP_RIESGO", "TIPO_PRED"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return gj, df


@st.cache_data
def load_tabla(nombre):
    p = DATA_DIR / nombre
    if not p.exists():
        return None
    return pd.read_csv(p, encoding="utf-8-sig", low_memory=False)


def _centroid(geom):
    try:
        t    = geom.get("type", "")
        coords = geom.get("coordinates", [])
        if t == "Point":
            return coords[1], coords[0]
        pts = coords[0] if t == "Polygon" else coords[0][0] if t == "MultiPolygon" else []
        if not pts:
            return None, None
        return sum(p[1] for p in pts)/len(pts), sum(p[0] for p in pts)/len(pts)
    except Exception:
        return None, None


# ── Coordenadas ───────────────────────────────────────────────────────────────

def _parse_coords(texto):
    texto = texto.strip()
    # Eliminar comas usadas como separadores de miles (96,709 → 96709 / 2,062,685 → 2062685)
    # Patrón: dígito seguido de coma seguida de exactamente 3 dígitos (luego no-dígito o fin)
    # Se aplica en loop para cubrir múltiples grupos: 1,234,567 → 1234567
    _prev = None
    while _prev != texto:
        _prev = texto
        texto = re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', '', texto)
    # 1. DMS: 4°36'35"N 74°04'54"W
    dms = re.search(
        r"(\d+)[°\s]+(\d+)['\s]+(\d+(?:\.\d+)?)[\"''\s]*([NS])"
        r"[\s,]+(\d+)[°\s]+(\d+)['\s]+(\d+(?:\.\d+)?)[\"''\s]*([EWOo])",
        texto, re.IGNORECASE)
    if dms:
        lat = int(dms[1]) + int(dms[2])/60 + float(dms[3])/3600
        lon = int(dms[5]) + int(dms[6])/60 + float(dms[7])/3600
        if dms[4].upper() == "S": lat = -lat
        if dms[8].upper() in ("W","O"): lon = -lon
        return lat, lon, "DMS"

    # 2. Extracción inteligente de números (maneja formato colombiano punto=miles, coma=decimal)
    def _extraer(t):
        """Devuelve lista de (valor_primario, alt_miles_o_None) en orden de aparición."""
        found, used = [], []
        # Colombiano inequívoco: 2+ grupos de miles, ej. "1.006.325,21" → 1006325.21
        for m in re.finditer(r'(?<!\d)\d{1,3}(?:\.\d{3}){2,}(?:,\d+)?', t):
            s = m.group()
            found.append((m.start(), m.end(), float(s.replace('.','').replace(',','.')), None))
            used.append((m.start(), m.end()))
        # Colombiano inequívoco: 1 grupo + coma decimal, ej. "109.321,53" → 109321.53
        for m in re.finditer(r'(?<!\d)\d{1,3}\.\d{3},\d+', t):
            if not any(m.start() < e and m.end() > s for s, e in used):
                s = m.group()
                found.append((m.start(), m.end(), float(s.replace('.','').replace(',','.')), None))
                used.append((m.start(), m.end()))
        # Números estándar o ambiguos
        for m in re.finditer(r'[-+]?\d+(?:[.,]\d+)?', t):
            if not any(m.start() < e and m.end() > s for s, e in used):
                s = m.group()
                try:
                    v = float(s.replace(',', '.'))
                    # "91.659" → ambiguo: 91.659 (decimal) o 91659 (miles colombiano)
                    alt = None
                    if re.match(r'^\d{1,3}\.\d{3}$', s):
                        if m.start() == 0 or not t[m.start()-1].isdigit():
                            alt = float(s.replace('.', ''))
                    found.append((m.start(), m.end(), v, alt))
                    used.append((m.start(), m.end()))
                except Exception:
                    pass
        found.sort(key=lambda x: x[0])
        return [(v, alt) for _, _, v, alt in found]

    pares = _extraer(texto)
    if len(pares) < 2:
        return None, None, None

    (a_pri, a_alt), (b_pri, b_alt) = pares[0], pares[1]
    a_vals = [a_pri] + ([a_alt] if a_alt is not None and a_alt != a_pri else [])
    b_vals = [b_pri] + ([b_alt] if b_alt is not None and b_alt != b_pri else [])

    _BOG_LAT, _BOG_LON = 4.6534, -74.0836

    # MAGNA Ciudad Bogotá col_urban con x_0=100000/y_0=100000 (parámetros IGAC/portal)
    # Este y Norte para Bogotá: ~85K-115K por eje
    def _try_col_urban(va, vb):
        if not (60000 <= va <= 160000 and 60000 <= vb <= 160000):
            return None
        try:
            from pyproj import Transformer, CRS
            _t = None
            for cd in (
                "+proj=col_urban +lat_0=4.596200416667 +lon_0=-74.077507916667"
                " +x_0=100000 +y_0=100000 +h_0=2550 +ellps=GRS80 +units=m +no_defs",
                "+proj=tmerc +lat_0=4.596200416667 +lon_0=-74.077507916667"
                " +k=1.0003998 +x_0=100000 +y_0=100000 +ellps=GRS80 +units=m +no_defs",
            ):
                try:
                    _t = Transformer.from_crs(CRS.from_proj4(cd), "EPSG:4326", always_xy=True)
                    break
                except Exception:
                    continue
            if _t is None:
                return None
            best, best_d = None, float("inf")
            for xe, yn in [(va, vb), (vb, va)]:
                try:
                    lo, la = _t.transform(xe, yn)
                    if 3.8 <= la <= 5.1 and -74.7 <= lo <= -73.5:
                        d = (la - _BOG_LAT)**2 + (lo - _BOG_LON)**2
                        if d < best_d:
                            best_d, best = d, (la, lo)
                except Exception:
                    pass
            return (best[0], best[1], "MAGNA Ciudad Bogotá (EPSG:7458)") if best else None
        except Exception:
            return None

    # MAGNA-SIRGAS Colombia Bogotá EPSG:3116 (~940K-1060K por eje)
    def _try_epsg3116(va, vb):
        if not (940000 <= va <= 1060000 and 940000 <= vb <= 1060000):
            return None
        try:
            from pyproj import Transformer
            _t = Transformer.from_crs("EPSG:3116", "EPSG:4326", always_xy=True)
            best, best_d = None, float("inf")
            for xe, yn in [(va, vb), (vb, va)]:
                try:
                    lo, la = _t.transform(xe, yn)
                    if 3.8 <= la <= 5.1 and -74.7 <= lo <= -73.5:
                        d = (la - _BOG_LAT)**2 + (lo - _BOG_LON)**2
                        if d < best_d:
                            best_d, best = d, (la, lo)
                except Exception:
                    pass
            return (best[0], best[1], "MAGNA-SIRGAS Colombia Bogotá (EPSG:3116)") if best else None
        except Exception:
            return None

    # Origen Nacional EPSG:9377 — Norte ~2M, Este ~4.9M para Bogotá
    # un valor en [1.9M-2.3M] y el otro en [4.7M-5.2M]
    def _try_epsg9377(va, vb):
        for norte_c, este_c in [(va, vb), (vb, va)]:
            if (1_900_000 <= norte_c <= 2_300_000 and 4_700_000 <= este_c <= 5_200_000):
                try:
                    from pyproj import Transformer
                    lo, la = Transformer.from_crs("EPSG:9377", "EPSG:4326",
                                                   always_xy=True).transform(este_c, norte_c)
                    if 3.8 <= la <= 5.1 and -74.7 <= lo <= -73.5:
                        return la, lo, "Origen Nacional (EPSG:9377)"
                except Exception:
                    pass
        return None

    # Recorre todas las interpretaciones de (a, b)
    for av in a_vals:
        for bv in b_vals:
            r = _try_col_urban(av, bv)
            if r: return r
            r = _try_epsg3116(av, bv)
            if r: return r
            r = _try_epsg9377(av, bv)
            if r: return r
            # WGS84 decimal — también acepta longitud positiva (convenio colombiano sin signo)
            for la, lo in [(av, bv), (bv, av)]:
                if 3.5 <= la <= 5.1 and -74.7 <= lo <= -73.5:
                    return la, lo, "WGS84 decimal"
            for la, lo in [(av, bv), (bv, av)]:
                if 3.5 <= la <= 5.1 and 73.5 <= lo <= 74.7:
                    return la, -lo, "WGS84 decimal"

    return None, None, None


def _wgs84_to_magna(lat, lon):
    """WGS84 → MAGNA Ciudad Bogotá.
    Usa col_urban con x_0=100000/y_0=100000 (parámetros IGAC/portal Bogotá).
    Devuelve (Este, Norte) o (None, None).
    """
    try:
        from pyproj import Transformer, CRS
        _t = None
        for cd in (
            "+proj=col_urban +lat_0=4.596200416667 +lon_0=-74.077507916667"
            " +x_0=100000 +y_0=100000 +h_0=2550 +ellps=GRS80 +units=m +no_defs",
            "+proj=tmerc +lat_0=4.596200416667 +lon_0=-74.077507916667"
            " +k=1.0003998 +x_0=100000 +y_0=100000 +ellps=GRS80 +units=m +no_defs",
        ):
            try:
                _t = Transformer.from_crs("EPSG:4326", CRS.from_proj4(cd), always_xy=True)
                break
            except Exception:
                continue
        if _t is None:
            return None, None
        x, y = _t.transform(lon, lat)
        return x, y
    except Exception:
        return None, None


def _wgs84_to_9377(lat, lon):
    """WGS84 → MAGNA-SIRGAS Origen Nacional (EPSG:9377). Devuelve (Este, Norte) o (None, None)."""
    try:
        from pyproj import Transformer
        x, y = Transformer.from_crs("EPSG:4326", "EPSG:9377",
                                     always_xy=True).transform(lon, lat)
        return x, y
    except Exception:
        return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def _geocode_bogota(query: str):
    """Geocodifica una dirección de Bogotá.
    Usa ArcGIS World Geocoder (entiende abreviaturas colombianas de forma nativa)
    con Nominatim como respaldo. Devuelve (lat, lon, address) o None.
    """
    _BOG_LAT = (3.8, 5.0)
    _BOG_LON = (-74.6, -73.5)

    def _en_bogota(loc):
        return (loc and _BOG_LAT[0] <= loc.latitude <= _BOG_LAT[1]
                and _BOG_LON[0] <= loc.longitude <= _BOG_LON[1])

    # ── 1. ArcGIS World Geocoder ─────────────────────────────────────────────
    try:
        from geopy.geocoders import ArcGIS
        gc = ArcGIS()
        for sufijo in [", Bogota Colombia", ", Bogota", ""]:
            try:
                loc = gc.geocode(f"{query}{sufijo}", timeout=14)
                if _en_bogota(loc):
                    return loc.latitude, loc.longitude, loc.address
            except Exception:
                continue
    except Exception:
        pass

    # ── 2. Nominatim como respaldo ───────────────────────────────────────────
    try:
        from geopy.geocoders import Nominatim
        gc = Nominatim(user_agent="visor_cvp_bogota_v2")
        for sufijo in [", Bogota", ", Bogotá, Colombia"]:
            try:
                loc = gc.geocode(f"{query}{sufijo}", timeout=14)
                if _en_bogota(loc):
                    return loc.latitude, loc.longitude, loc.address
            except Exception:
                continue
    except Exception:
        pass

    return None


def _normalizar_dir(s: str) -> str:
    """Normaliza dirección para comparación difusa."""
    s = s.upper()
    for p, r in [("CALLE","CL"),("CARRERA","CR"),("DIAGONAL","DG"),
                 ("TRANSVERSAL","TV"),("AVENIDA","AV"),("AUTOPISTA","AU"),
                 ("#",""), ("-"," "), ("."," ")]:
        s = s.replace(p, r)
    return " ".join(s.split())


@st.cache_data(show_spinner=False)
def _reas_bbox():
    """Lee el bbox real de reas.geojson escaneando todos los vértices del anillo exterior."""
    p = DATA_DIR / "reas.geojson"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        gj = json.load(f)
    # Si el GeoJSON ya tiene bbox guardado, usarlo directo
    if "bbox" in gj and len(gj["bbox"]) >= 4:
        b = gj["bbox"]
        return b[1], b[3], b[0], b[2]   # min_lat, max_lat, min_lon, max_lon
    min_lat = min_lon = 1e9
    max_lat = max_lon = -1e9
    for feat in gj.get("features", []):
        geom = feat.get("geometry") or {}
        t    = geom.get("type", "")
        coords = geom.get("coordinates")
        if not coords:
            continue
        try:
            rings = coords if t == "Polygon" else [p[0] for p in coords] if t == "MultiPolygon" else []
            for ring in rings:
                for pt in ring:
                    lo, la = pt[0], pt[1]
                    if la < min_lat: min_lat = la
                    if la > max_lat: max_lat = la
                    if lo < min_lon: min_lon = lo
                    if lo > max_lon: max_lon = lo
        except Exception:
            pass
    if min_lat == 1e9:
        return None
    return min_lat, max_lat, min_lon, max_lon


def _home_view(df_reas):
    """Calcula center + zoom para mostrar toda la capa REAS (usa bbox real)."""
    import math
    bbox = _reas_bbox()
    if bbox:
        min_lat, max_lat, min_lon, max_lon = bbox
    else:
        lats = df_reas["_lat"].dropna()
        lons = df_reas["_lon"].dropna()
        if lats.empty:
            return 4.65, -74.08, 11
        min_lat, max_lat = lats.min(), lats.max()
        min_lon, max_lon = lons.min(), lons.max()

    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    lat_span   = max_lat - min_lat
    lon_span   = max_lon - min_lon
    # margen del 15 % en cada dimensión
    lat_span   = max(lat_span * 1.15, 0.005)
    lon_span   = max(lon_span * 1.15, 0.005)
    # Mercator: al zoom z, viewport de 900 px muestra 900*360/(256*2^z) grados
    # Queremos que quepan lat_span y lon_span → tomamos el zoom mínimo
    zoom_lat = math.log2(900 * 180 / (256 * lat_span))
    zoom_lon = math.log2(900 * 360 / (256 * lon_span))
    zoom = min(zoom_lat, zoom_lon) - 0.3        # -0.3 para margen extra
    zoom = max(8.0, min(14.0, zoom))
    return center_lat, center_lon, zoom


def _detect_tipo(q: str) -> str:
    """Detecta el tipo de búsqueda a partir del texto."""
    q = q.lower().strip()
    dir_words = ["calle","carrera","cra","cl ","diagonal","dg","transversal","tv",
                 "avenida","av ","#","sur","bis","norte","este","oeste"]
    if any(w in q for w in dir_words):
        return "dir"
    if re.match(r"^\d{4}-", q):
        return "id"
    digits = sum(c.isdigit() for c in q)
    letters = sum(c.isalpha() for c in q)
    if digits >= 5 and digits > letters:
        return "chip"
    return "name"


# ── Color ─────────────────────────────────────────────────────────────────────

def _get_color(props, modo):
    if modo == "Estado":
        v = str(props.get("ESTADO_DEPURADO", ""))
        return _COLOR_ESTADO.get(v, _COLOR_DEFAULT)
    elif modo == "Tipo de riesgo":
        k = _norm(str(props.get("TP_RIESGO", "")))
        for key, col in _COLOR_RIESGO.items():
            if _norm(key) in k: return col
    elif modo == "Tipo predio":
        k = _norm(str(props.get("TIPO_PRED", "")))
        for key, col in _COLOR_TIPO.items():
            if _norm(key) in k: return col
    return _COLOR_DEFAULT


@st.cache_data(show_spinner=False, max_entries=4)
def _reas_gj_coloreado(n_feats: int, color_por: str, dep_hash: int,
                        _gj_reas: dict, _dep_dict: dict) -> dict:
    """Pre-computa colores para todas las features REAS.
    dep_hash invalida la caché cuando cambia la tabla depuración.
    _gj_reas y _dep_dict tienen prefijo _ → no se hashean.
    """
    _keep = {"REA_Identi", "BARRIO_LEG", "LocNombre", "TP_RIESGO", "chip", "TIPO_PRED"}
    feats = []
    for feat in _gj_reas.get("features", []):
        orig = feat.get("properties", {}) or {}
        rid  = str(orig.get("REA_Identi", "")).strip()
        slim = {k: orig[k] for k in _keep if k in orig}
        # Inyectar ESTADO_DEPURADO desde tabla depuración
        if _dep_dict and rid in _dep_dict:
            slim["ESTADO_DEPURADO"] = _dep_dict[rid]
        slim["_fill"]   = _get_color(slim, color_por)
        slim["_stroke"] = [180, 180, 180, 80]
        slim["_lw"]     = 0
        feats.append({"type": "Feature", "geometry": feat["geometry"], "properties": slim})
    return {"type": "FeatureCollection", "features": feats}


# ── Helpers UI ────────────────────────────────────────────────────────────────

def _val(d, *keys):
    for k in keys:
        v = d.get(k, "")
        if v and str(v).strip() not in ("", "nan", "None", "NaN"):
            return str(v).strip()
    return "—"


def _campo(label, value):
    return (
        f'<div style="background:#F8FAFC;border-radius:10px;padding:10px 14px;">'
        f'<div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;'
        f'color:{SLATE};text-transform:uppercase;margin-bottom:3px;">{label}</div>'
        f'<div style="font-size:.88rem;font-weight:600;color:#1E293B;">{value}</div>'
        f'</div>'
    )


def _grid(*campos):
    return (
        f'<div style="display:grid;grid-template-columns:repeat(auto-fill,'
        f'minmax(175px,1fr));gap:10px;margin-top:10px;">'
        + "".join(_campo(l, v) for l, v in campos)
        + '</div>'
    )


# ── Ficha inline ─────────────────────────────────────────────────────────────

def _render_ficha(props, lat, lon, df_propietario, df_gis, df_depuracion):
    rea_id  = _val(props, "REA_Identi")
    # Estado desde tabla depuración (fuente authoritative)
    estado = "—"
    if df_depuracion is not None:
        _id_col = next((c for c in df_depuracion.columns
                        if "rea" in c.lower() and "ident" in c.lower()), None)
        if _id_col:
            _row = df_depuracion[df_depuracion[_id_col].astype(str).str.upper()
                                 == rea_id.upper()]
            if not _row.empty and "ESTADO_DEPURADO" in _row.columns:
                estado = str(_row.iloc[0]["ESTADO_DEPURADO"])
    if estado == "—":
        estado = _val(props, "REA_ESTADO")
    color_e = {"Reasentamiento Terminado": TEAL,
               "En Proceso": AMBER,
               "Adquisicion predial por IDIGER": "#1565C0",
               "Cierre Administrativo Sin Reasentamiento": "#6A0DAD"}.get(estado, SLATE)
    gmaps     = f"https://www.google.com/maps?q={lat},{lon}"
    mx, my    = _wgs84_to_magna(lat, lon)
    magna_txt = f"Norte {my:.0f}  Este {mx:.0f}" if mx else "—"
    ox, oy    = _wgs84_to_9377(lat, lon)
    ori_txt   = f"Norte {oy:.0f}  Este {ox:.0f}" if ox else "—"

    # Cabecera
    st.markdown(f"""
    <div style="background:white;border-radius:14px;padding:18px 22px;
                box-shadow:0 4px 20px rgba(0,0,0,.09);
                border-left:5px solid {color_e};margin:10px 0 4px;">
      <div style="display:flex;justify-content:space-between;
                  align-items:center;flex-wrap:wrap;gap:8px;">
        <div>
          <div style="font-size:.68rem;font-weight:700;color:{SLATE};
                      text-transform:uppercase;letter-spacing:.1em;">
            Predio seleccionado</div>
          <div style="font-size:1.3rem;font-weight:900;color:#1E293B;
                      margin-top:2px;">{rea_id}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <span style="background:{color_e}22;color:{color_e};
                       border:1px solid {color_e}55;border-radius:20px;
                       padding:4px 14px;font-size:.78rem;font-weight:600;">
            {estado}</span>
          <a href="{gmaps}" target="_blank"
             style="background:{BLUE};color:white;border-radius:10px;
                    padding:6px 14px;font-size:.78rem;font-weight:600;
                    text-decoration:none;">Ver en Google Maps</a>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📍 Geográfica", "🏘 Catastral", "🗺 GIS", "📋 Depurada", "👤 Propietario",
    ])

    with tab1:
        st.markdown(_grid(
            ("Identificador REA", _val(props, "REA_Identi")),
            ("Tipo predio",       _val(props, "TIPO_PRED")),
            ("Estado REA",        _val(props, "REA_ESTADO")),
            ("Sub-estado",        _val(props, "REA_SUBEST")),
            ("Riesgo",            _val(props, "Riesgo")),
            ("Tipo de riesgo",    _val(props, "TP_RIESGO")),
            ("Barrio",            _val(props, "BARRIO")),
            ("Localidad",         _val(props, "LOCALIDA")),
            ("Coord. Este (X)",   _val(props, "COOR_EST_X")),
            ("Coord. Norte (Y)",  _val(props, "COOR_NOR_Y")),
            ("Area (m2)",         _val(props, "Shape_Area", "AREA", "AreaGEO")),
            ("WGS84",             f"{lat:.6f}, {lon:.6f}"),
            ("MAGNA Cdad. Bogotá (7458)", magna_txt),
            ("Origen Nacional (9377)",    ori_txt),
        ), unsafe_allow_html=True)

    def _por_chip(df, label):
        if df is None:
            st.info(f"Tabla {label} no cargada.", icon="📂"); return
        chip_val = _val(props, "chip", "CHIP_VLI_1")
        sub = pd.DataFrame()
        for col in df.columns:
            if "chip" in col.lower() or "predio" in col.lower():
                m = df[df[col].astype(str).str.upper() == chip_val.upper()]
                if not m.empty: sub = m; break
        if sub.empty:
            st.warning(f"Sin registros para chip: {chip_val}")
        else:
            st.dataframe(sub.T.reset_index().rename(columns={"index":"Campo",0:"Valor"}),
                         hide_index=True, use_container_width=True, height=380)

    with tab2:
        # Catastral desde tabla depuración
        if df_depuracion is None:
            st.info("Tabla Depuración no cargada.", icon="📂")
        else:
            _cat_cols = [c for c in [
                "CHIP_USO", "LOTLOTE_ID", "MATRICULA_INMO", "DIRECCION_CATASTRAL",
                "VALOR_TERRENO", "VALOR_CONSTRUCCION", "VALOR_AVALUO_TOTAL",
                "POSIBLE_LOTE_VACIO", "TIPO_LOTE", "CASO_CHIP", "MEJORA"
            ] if c in df_depuracion.columns]
            _id_col = next((c for c in df_depuracion.columns
                            if "rea" in c.lower() and "ident" in c.lower()), None)
            _sub = pd.DataFrame()
            if _id_col:
                _sub = df_depuracion[
                    df_depuracion[_id_col].astype(str).str.upper() == rea_id.upper()
                ]
            if _sub.empty:
                st.warning(f"Sin registros catastral para: {rea_id}")
            elif _cat_cols:
                st.dataframe(
                    _sub[_cat_cols].T.reset_index().rename(
                        columns={"index": "Campo", _sub.index[0]: "Valor"}),
                    hide_index=True, use_container_width=True, height=340)

    with tab3:
        rea_id_val = _val(props, "REA_Identi")
        if df_gis is None:
            st.markdown(_grid(
                ("Chip",         _val(props, "chip")),
                ("Chip validado",_val(props, "CHIP_VLI_1")),
                ("Codigo lote",  _val(props, "COD_LT")),
                ("Sector cod.",  _val(props, "SCACODIGO")),
                ("Sector nom.",  _val(props, "SCANOMBRE_")),
                ("UPL",          _val(props, "UPL_NMG")),
                ("UPZ",          _val(props, "UPZ")),
            ), unsafe_allow_html=True)
            st.caption("Tabla GIS no cargada — mostrando datos del GeoJSON.")
        else:
            if "Identificador" in df_gis.columns:
                sub = df_gis[df_gis["Identificador"].astype(str).str.upper()
                             == rea_id_val.upper()]
            else:
                sub = pd.DataFrame()
            if sub.empty:
                st.warning(f"Sin registros GIS para: {rea_id_val}")
                st.markdown(_grid(
                    ("Chip",         _val(props, "chip")),
                    ("Chip validado",_val(props, "CHIP_VLI_1")),
                    ("UPL",          _val(props, "UPL_NMG")),
                    ("UPZ",          _val(props, "UPZ")),
                ), unsafe_allow_html=True)
            else:
                st.dataframe(sub.T.reset_index().rename(columns={"index":"Campo",0:"Valor"}),
                             hide_index=True, use_container_width=True, height=380)

    with tab4:
        if df_depuracion is None:
            st.info("Tabla Depuracion no cargada.", icon="📂")
        else:
            rea_id_val = _val(props, "REA_Identi")
            sub = pd.DataFrame()
            for col in df_depuracion.columns:
                if "rea" in col.lower() and "ident" in col.lower():
                    m = df_depuracion[df_depuracion[col].astype(str).str.upper()
                                      == rea_id_val.upper()]
                    if not m.empty: sub = m; break
            if sub.empty:
                st.warning(f"Sin registros para: {rea_id_val}")
            else:
                st.dataframe(sub.T.reset_index().rename(columns={"index":"Campo",0:"Valor"}),
                             hide_index=True, use_container_width=True, height=380)

    with tab5:
        _por_chip(df_propietario, "Propietario")


# ── Fragmento: mapa + controles + mini-ficha ──────────────────────────────────

def _mapa_fragment(gj_reas, df_reas, df_propietario,
                   df_gis, df_depuracion):
    try:
        import pydeck as pdk
    except ImportError:
        st.error("pydeck no instalado.")
        return

    # Controles sobre el mapa
    c1, c2, c3 = st.columns([1, 2, 2])
    show_reas = c1.checkbox("REAS",  value=True,  key="ck_reas")
    color_por = c2.selectbox("Colorear por:",
                             ["Estado", "Tipo de riesgo", "Tipo predio"],
                             label_visibility="collapsed", key="sel_color")

    # Leer estado ANTES del botón para evitar NameError si se hace clic en él
    sel_idx   = st.session_state.get("sel_idx")
    marker    = st.session_state.get("marker")
    zoom_key  = st.session_state.get("zoom_key", 0)

    if c3.button("⌂ Vista completa", key="btn_home"):
        st.session_state.pop("sel_idx", None)
        st.session_state.pop("marker", None)
        st.session_state.pop("gis_only_id", None)
        st.session_state["zoom_key"]   = zoom_key + 1
        st.session_state["clear_count"] = st.session_state.get("clear_count", 0) + 1
        st.rerun()

    # Determinar vista ANTES de construir el deck
    if sel_idx is not None and sel_idx in df_reas.index:
        r = df_reas.loc[sel_idx]
        vlat, vlon, vzoom = r["_lat"], r["_lon"], 19
    elif marker:
        vlat, vlon, vzoom = marker[0], marker[1], 18
    else:
        vlat, vlon, vzoom = _home_view(df_reas)

    # Construir lookup ESTADO_DEPURADO desde tabla depuración
    _dep_dict: dict = {}
    _dep_hash: int  = 0
    if df_depuracion is not None:
        _idc = next((c for c in df_depuracion.columns
                     if "rea" in c.lower() and "ident" in c.lower()), None)
        if _idc and "ESTADO_DEPURADO" in df_depuracion.columns:
            _dep_dict = (df_depuracion.dropna(subset=["ESTADO_DEPURADO"])
                         .set_index(_idc)["ESTADO_DEPURADO"].to_dict())
            _dep_hash = hash(frozenset(_dep_dict.items()))

    # Capa REAS coloreada (cacheada por color_por — no se reconstruye en cada rerun)
    sel_rid = (df_reas.loc[sel_idx, "REA_Identi"]
               if sel_idx is not None and sel_idx in df_reas.index else None)

    layers = []
    if show_reas and gj_reas:
        gj_color = _reas_gj_coloreado(
            len(gj_reas.get("features", [])), color_por, _dep_hash, gj_reas, _dep_dict)
        layers.append(pdk.Layer(
            "GeoJsonLayer", data=gj_color,
            get_fill_color="properties._fill",
            get_line_color="properties._stroke",
            get_line_width="properties._lw",
            line_width_min_pixels=0,
            line_width_max_pixels=2,
            auto_highlight=True,
            highlight_color=[255, 255, 255, 80],
            pickable=True, id="reas_layer"))
        # Capa de selección (polígono amarillo sobre el REAS activo)
        if sel_rid:
            _sel_feats = [f for f in gj_reas.get("features", [])
                          if (f.get("properties") or {}).get("REA_Identi") == sel_rid]
            if _sel_feats:
                layers.append(pdk.Layer(
                    "GeoJsonLayer",
                    data={"type":"FeatureCollection","features":_sel_feats},
                    get_fill_color=[255, 230, 50, 90],
                    get_line_color=[255, 50, 50, 255],
                    get_line_width=4,
                    line_width_min_pixels=2,
                    line_width_max_pixels=6,
                    pickable=False, id="sel_layer"))

    if marker:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=[{"lat":marker[0],"lon":marker[1]}],
            get_position="[lon,lat]",
            get_fill_color=[255,50,50,230],
            get_radius=40, radius_min_pixels=7, radius_max_pixels=18,
            pickable=False, id="marker_layer"))

    view = pdk.ViewState(latitude=vlat, longitude=vlon, zoom=vzoom, pitch=0)
    deck = pdk.Deck(
        layers=layers, initial_view_state=view,
        tooltip={"html": "<b>{REA_Identi}</b><br/>{BARRIO_LEG} · {LocNombre}<br/>{ESTADO_DEPURADO}",
                 "style": {"backgroundColor": NAVY, "color":"white",
                            "fontSize":"12px","borderRadius":"8px","padding":"8px 12px"}},
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    )

    # Renderizar mapa — key cambia al seleccionar para forzar re-mount + zoom
    _deck_key = f"deck_{zoom_key}"
    event = st.pydeck_chart(deck, on_select="rerun",
                            use_container_width=True, height=560,
                            key=_deck_key)

    # ── Extraer objetos seleccionados (varios formatos según versión Streamlit) ──
    def _extract_hits(ev, ss_key):
        """Intenta leer objetos seleccionados desde el retorno del widget y desde session_state."""
        # 1. Desde el valor de retorno del widget
        try:
            _ss = getattr(ev, "selection", None)
            _ob = getattr(_ss, "objects", None) if _ss else None
            if isinstance(_ob, dict) and _ob:
                return _ob
            if isinstance(_ob, list) and _ob:
                return {"__list__": _ob}
        except Exception:
            pass
        # 2. Desde session_state[key] (algunas versiones de Streamlit guardan aquí)
        _st = st.session_state.get(ss_key)
        if isinstance(_st, dict):
            _sel = _st.get("selection", {})
            if isinstance(_sel, dict):
                _ob2 = _sel.get("objects", {})
                if _ob2:
                    return _ob2
        return {}

    def _objs_to_hits(objs):
        """Extrae la lista de features REAS de cualquier estructura de objs."""
        if isinstance(objs, dict):
            for _k in ("reas_layer", "__list__"):
                if isinstance(objs.get(_k), list) and objs[_k]:
                    return objs[_k]
            for v in objs.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return v
        if isinstance(objs, list) and objs and isinstance(objs[0], dict):
            return objs
        return []

    import time as _time_mod
    objs = {}
    if event is not None:
        objs = _extract_hits(event, _deck_key)

    # ── Procesar clic ──────────────────────────────────────────────────────────
    hits = _objs_to_hits(objs)

    if hits and "REA_Identi" in df_reas.columns:
        _h = hits[0]
        # GeoJSON features anidan atributos en "properties"
        _hprops = (_h.get("properties") or _h) if isinstance(_h, dict) else {}
        rid = str(_hprops.get("REA_Identi", "")).strip()
        if rid and rid.lower() not in ("nan", "none", ""):
            m = df_reas[df_reas["REA_Identi"].astype(str).str.strip() == rid]
            if not m.empty:
                new_idx = m.index[0]
                st.session_state["sel_idx"]     = new_idx
                sel_idx = new_idx
                st.session_state["clear_count"] = st.session_state.get("clear_count", 0) + 1
                st.session_state.pop("marker", None)
                st.session_state.pop("gis_only_id", None)
                # on_select="rerun" ya lanza el rerun automáticamente;
                # NO llamar st.rerun() aquí para evitar doble-rerun con doble clic

    # Leyenda
    leyenda = {"Estado": _COLOR_ESTADO,
               "Tipo de riesgo": _COLOR_RIESGO,
               "Tipo predio": _COLOR_TIPO}.get(color_por, {})
    items = "".join(
        f'<div style="display:flex;align-items:center;gap:5px;background:#F8FAFC;'
        f'border-radius:8px;padding:4px 10px;">'
        f'<div style="width:9px;height:9px;border-radius:50%;'
        f'background:#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X};flex-shrink:0;"></div>'
        f'<span style="font-size:.73rem;color:#1E293B;">{k.title()}</span></div>'
        for k, rgb in leyenda.items()
    )
    if items:
        st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:6px;'
                    f'margin:6px 0 6px;">{items}</div>', unsafe_allow_html=True)

    # Botón quitar selección
    if sel_idx is not None:
        if st.button("Quitar seleccion", key="btn_clear"):
            st.session_state["clear_count"] = st.session_state.get("clear_count", 0) + 1
            st.session_state["zoom_key"]    = zoom_key + 1
            st.session_state.pop("sel_idx", None)
            st.session_state.pop("gis_only_id", None)
            st.rerun()

    # Ficha inline
    if sel_idx is not None and sel_idx in df_reas.index:
        row   = df_reas.loc[sel_idx].to_dict()
        lat_f = row.get("_lat") or vlat
        lon_f = row.get("_lon") or vlon
        _render_ficha(row, lat_f, lon_f,
                      df_propietario, df_gis, df_depuracion)


# ════════════════════════════════════════════════════════════════════════════
# FRAGMENTO DE BÚSQUEDA — solo esta sección re-ejecuta al escribir
# ════════════════════════════════════════════════════════════════════════════

@st.fragment
def _busqueda_fragment(df_reas, df_gis):
    """Contiene inputs + resultados. Al escribir solo rerenderiza este bloque (no el mapa)."""
    import streamlit.components.v1 as components
    _cc   = st.session_state.get("clear_count", 0)
    _modo = st.session_state.get("modo_radio", "Por atributo")

    # ── Input: atributo (barra superior, área principal) ─────────────────────
    if _modo == "Por atributo":
        _sb1, _sb2 = st.columns([6, 1])
        _sb1.text_input("Buscar", placeholder="ID, chip, dirección, nombre...",
                        label_visibility="collapsed", key="inp_attr")
        if _sb2.button("🔍", key="btn_search", use_container_width=True):
            _t_btn = st.session_state.get("inp_attr", "").strip().lower()
            st.session_state["_last_attr_q"] = _t_btn
            st.session_state.pop("sel_idx", None)
            st.session_state.pop("marker", None)
            st.session_state.pop("gis_only_id", None)
            st.session_state["zoom_key"] = st.session_state.get("zoom_key", 0) + 1
            st.rerun(scope="app")
        # JS: blur tras 200 ms → rerenderiza solo este fragmento (rápido)
        components.html("""<script>
(function(){
  var last='',timer;
  function attach(){
    try{
      var all=window.parent.document.querySelectorAll('input[type="text"]');
      var inp=null;
      for(var i=0;i<all.length;i++){
        var ph=all[i].placeholder||'';
        if(ph.indexOf('chip')>-1||ph.indexOf('nombre')>-1||ph.indexOf('dirección')>-1){inp=all[i];break;}
      }
      if(!inp&&all.length)inp=all[0];
      if(!inp){setTimeout(attach,300);return;}
      if(inp._live){return;}
      inp._live=true;
      inp.addEventListener('input',function(){
        clearTimeout(timer);
        var v=inp.value;
        timer=setTimeout(function(){
          if(v===last)return;
          if(v.length>=4||(v.length===0&&last.length>0)){
            last=v;
            inp.dispatchEvent(new FocusEvent('blur',{bubbles:true,cancelable:false}));
            setTimeout(function(){try{inp.focus();inp.setSelectionRange(v.length,v.length);}catch(e){}},120);
          }
        },200);
      });
    }catch(e){setTimeout(attach,400);}
  }
  attach();setTimeout(attach,800);
})();
</script>""", height=0, scrolling=False)

    # El input de dirección vive en el sidebar (fuera del fragment) — ver bloque PÁGINA

    # ── Resultados: Por atributo ──────────────────────────────────────────────
    if _modo == "Por atributo":
        _t = st.session_state.get("inp_attr", "").strip().lower()
        # Limpiar selección anterior cuando cambia la búsqueda
        if _t != st.session_state.get("_last_attr_q", ""):
            st.session_state["_last_attr_q"] = _t
            st.session_state.pop("sel_idx", None)
            st.session_state.pop("marker", None)
            st.session_state.pop("gis_only_id", None)
            st.session_state["_last_geo_addr"] = ""
            st.session_state["zoom_key"] = st.session_state.get("zoom_key", 0) + 1
            st.rerun(scope="app")
        if _t:
            _tipo = _detect_tipo(_t)
            _id_m = (df_reas["REA_Identi"].astype(str).str.lower().str.contains(_t, na=False, regex=False)
                     if "REA_Identi" in df_reas.columns else pd.Series(False, index=df_reas.index))
            _chip_m = pd.Series(False, index=df_reas.index)
            for _c in ["chip", "CHIP_VLI_1"]:
                if _c in df_reas.columns:
                    _chip_m |= df_reas[_c].astype(str).str.lower().str.contains(_t, na=False, regex=False)
            _dir_m = pd.Series(False, index=df_reas.index)
            for _c in ["DIR_CAMPO", "DIR_CATAST"]:
                if _c in df_reas.columns:
                    _dir_m |= df_reas[_c].astype(str).str.lower().str.contains(_t, na=False, regex=False)
            _rgis = pd.DataFrame()
            _name_m = pd.Series(False, index=df_reas.index)
            if df_gis is not None:
                _gm = pd.Series(False, index=df_gis.index)
                for _col in df_gis.columns:
                    _cl = _col.lower().replace(" ", "")
                    if any(x in _cl for x in ["identificador", "nombre1", "nombre2"]):
                        _gm |= df_gis[_col].astype(str).str.lower().str.contains(_t, na=False, regex=False)
                _rgis = df_gis[_gm]
                if not _rgis.empty and "Identificador" in _rgis.columns:
                    _ids = set(_rgis["Identificador"].astype(str).str.upper())
                    if "REA_Identi" in df_reas.columns:
                        _name_m = df_reas["REA_Identi"].astype(str).str.upper().isin(_ids)
            _rg = df_reas[_id_m | _chip_m | _dir_m | _name_m].dropna(subset=["_lat", "_lon"]).copy()
            _rg["_orig_idx"] = _rg.index
            _gis_nombre_cols = ([c for c in (df_gis.columns if df_gis is not None else [])
                                 if "nombre" in c.lower()])
            if (_tipo == "name" and df_gis is not None and _gis_nombre_cols
                    and "Identificador" in df_gis.columns and not _rg.empty):
                _gmerge = (df_gis[["Identificador"] + _gis_nombre_cols]
                           .drop_duplicates("Identificador")
                           .rename(columns={"Identificador": "REA_Identi"}))
                _rg = _rg.merge(_gmerge, on="REA_Identi", how="left")
                _rg.columns = [str(c) for c in _rg.columns]
            if _tipo == "name":
                _show = [c for c in _gis_nombre_cols[:2] + ["REA_Identi", "BARRIO"] if c in _rg.columns]
            elif _tipo == "dir":
                _show = [c for c in ["DIR_CAMPO", "REA_Identi", "BARRIO"] if c in _rg.columns]
            elif _tipo == "chip":
                _show = [c for c in ["chip", "CHIP_VLI_1", "REA_Identi"] if c in _rg.columns][:3]
            else:
                _show = [c for c in ["REA_Identi", "BARRIO", "REA_ESTADO"] if c in _rg.columns]
            if not _show:
                _show = [c for c in ["REA_Identi", "BARRIO"] if c in _rg.columns]
            _ro = pd.DataFrame()
            if not _rgis.empty and "Identificador" in _rgis.columns:
                _ig = (set(df_reas["REA_Identi"].astype(str).str.upper())
                       if "REA_Identi" in df_reas.columns else set())
                _ro = _rgis[~_rgis["Identificador"].astype(str).str.upper().isin(_ig)]
            if not _rg.empty:
                with st.expander(f"**{len(_rg):,}** resultado(s) con geometría", expanded=True):
                    _ev = st.dataframe(
                        _rg[_show].head(6).reset_index(drop=True),
                        hide_index=True, use_container_width=True,
                        height=min(38 + min(len(_rg), 6) * 35, 248),
                        on_select="rerun", selection_mode="single-row",
                        key=f"tbl_busq_{_cc}")
                    _sel = _sel_rows(_ev)
                    if _sel:
                        _row_sel = _rg.iloc[_sel[0]]
                        _ni = _row_sel["_orig_idx"] if "_orig_idx" in _rg.columns else _row_sel.name
                        st.session_state["sel_idx"]     = _ni
                        st.session_state["zoom_key"]    = st.session_state.get("zoom_key", 0) + 1
                        st.session_state["clear_count"] = _cc + 1
                        st.session_state.pop("marker", None)
                        st.session_state.pop("gis_only_id", None)
                        st.rerun(scope="app")
            if not _ro.empty:
                _gis_show = [c for c in (["Identificador"]
                             + [c for c in _ro.columns if "nombre" in c.lower()]
                             + ["Estado Proceso"]) if c in _ro.columns]
                with st.expander(f"**{len(_ro)}** sin geometría (solo tabla GIS)", expanded=True):
                    _ev2 = st.dataframe(
                        _ro[_gis_show].head(4).reset_index(drop=True),
                        hide_index=True, use_container_width=True,
                        height=min(38 + min(len(_ro), 4) * 35, 178),
                        on_select="rerun", selection_mode="single-row",
                        key=f"tbl_gis_{_cc}")
                    _sg = _sel_rows(_ev2)
                    if _sg:
                        _gid = str(_ro.iloc[_sg[0]].get("Identificador", ""))
                        st.session_state["gis_only_id"] = _gid
                        st.session_state["clear_count"] = _cc + 1
                        st.session_state.pop("sel_idx", None)
                        st.session_state.pop("marker", None)
                        st.rerun(scope="app")
            if _rg.empty and _ro.empty:
                st.caption(f"Sin resultados para «{st.session_state.get('inp_attr', '')}»")

    # ── Resultados: Por dirección ─────────────────────────────────────────────
    elif _modo == "Por dirección":
        _a        = st.session_state.get("inp_addr", "").strip()
        _geo_res  = st.session_state.get("_geo_result", {})
        _geo_addr = _geo_res.get("addr_input", "")

        if _geo_res.get("ok") is True and _geo_addr == _a:
            # ── OSM encontró el punto ─────────────────────────────────────────
            st.caption(f"📍 {_geo_res['display']}")

        elif _geo_res.get("ok") is False and _geo_addr == _a:
            # ── OSM falló: buscar en REAS ─────────────────────────────────────
            _dc  = [c for c in ["DIR_CAMPO", "DIR_CATAST"] if c in df_reas.columns]
            _dm  = pd.Series(False, index=df_reas.index)
            for _dcc in _dc:
                _dm |= df_reas[_dcc].astype(str).str.lower().str.contains(
                    _a.lower(), na=False, regex=False)
            _sug = df_reas[_dm].dropna(subset=["_lat", "_lon"]).copy()
            _sug["_orig_idx"] = _sug.index

            if not _sug.empty:
                _sc3 = [c for c in ["DIR_CAMPO", "REA_Identi", "BARRIO"] if c in _sug.columns]
                with st.expander(f"**{len(_sug)}** predio(s) REAS con esa dirección", expanded=True):
                    _ev3 = st.dataframe(
                        _sug[_sc3].head(8).reset_index(drop=True),
                        hide_index=True, use_container_width=True,
                        height=min(38 + min(len(_sug), 8) * 35, 318),
                        on_select="rerun", selection_mode="single-row",
                        key=f"tbl_dir_{_cc}")
                    _s3 = _sel_rows(_ev3)
                    if _s3:
                        _row3 = _sug.iloc[_s3[0]]
                        _ni3  = _row3["_orig_idx"] if "_orig_idx" in _sug.columns else _row3.name
                        st.session_state["sel_idx"]     = _ni3
                        st.session_state["zoom_key"]    = st.session_state.get("zoom_key", 0) + 1
                        st.session_state["clear_count"] = _cc + 1
                        st.session_state.pop("marker", None)
                        st.session_state.pop("gis_only_id", None)
                        st.rerun(scope="app")
            else:
                # ── Similares en REAS ─────────────────────────────────────────
                st.caption("No encontrado en OpenStreetMap ni en REAS.")
                import difflib
                _dir_col = next((c for c in ["DIR_CAMPO", "DIR_CATAST"] if c in df_reas.columns), None)
                if _dir_col:
                    _all_dirs = df_reas[_dir_col].dropna().astype(str).tolist()
                    _all_norm = [_normalizar_dir(d) for d in _all_dirs]
                    _q_norm   = _normalizar_dir(_a)
                    _scores   = [(difflib.SequenceMatcher(None, _q_norm, d).ratio(), i)
                                 for i, d in enumerate(_all_norm)]
                    _scores.sort(reverse=True)
                    _top = [i for sc, i in _scores[:8] if sc >= 0.35]
                    if _top:
                        _sim = df_reas.iloc[_top].dropna(subset=["_lat", "_lon"]).copy()
                        _sim["_orig_idx"] = _sim.index
                        _sc_sim = [c for c in ["DIR_CAMPO", "REA_Identi", "BARRIO"] if c in _sim.columns]
                        with st.expander(f"**{len(_sim)}** dirección(es) similar(es) en REAS", expanded=True):
                            _ev_sim = st.dataframe(
                                _sim[_sc_sim].reset_index(drop=True),
                                hide_index=True, use_container_width=True,
                                height=min(38 + len(_sim) * 35, 318),
                                on_select="rerun", selection_mode="single-row",
                                key=f"tbl_sim_{_cc}")
                            _s_sim = _sel_rows(_ev_sim)
                            if _s_sim:
                                _row_sim = _sim.iloc[_s_sim[0]]
                                _ni_sim  = (_row_sim["_orig_idx"] if "_orig_idx" in _sim.columns
                                            else _row_sim.name)
                                st.session_state["sel_idx"]     = _ni_sim
                                st.session_state["zoom_key"]    = st.session_state.get("zoom_key", 0) + 1
                                st.session_state["clear_count"] = _cc + 1
                                st.session_state.pop("marker", None)
                                st.session_state.pop("gis_only_id", None)
                                st.rerun(scope="app")

        elif _a:
            st.caption("Escribe una dirección y pulsa **Buscar**.")


# ════════════════════════════════════════════════════════════════════════════
# PÁGINA
# ════════════════════════════════════════════════════════════════════════════


# Auto-convertir REAS si no existe
if not (DATA_DIR / "reas.geojson").exists():
    from conversor import auto_convertir_si_falta
    with st.spinner("Generando capa REAS por primera vez..."):
        auto_convertir_si_falta()
    st.cache_data.clear()

gj_reas, df_reas = load_reas()
df_propietario   = load_tabla("propietario.csv")
df_gis           = load_tabla("gis.csv")
df_depuracion    = load_tabla("depuracion.csv")

if gj_reas is None:
    st.warning("Capa REAS no disponible. Ve al **Módulo de Carga**.", icon="📂")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;
                color:rgba(255,255,255,.45);text-transform:uppercase;
                margin:8px 0 12px;">Buscar predio</div>
    """, unsafe_allow_html=True)
    st.radio("Modo de búsqueda",
             ["Por atributo", "Por dirección", "Por coordenadas"],
             label_visibility="collapsed", key="modo_radio")


    _modo_sb = st.session_state.get("modo_radio", "Por atributo")
    if _modo_sb == "Por dirección":
        st.text_input("Dirección", placeholder="Calle 13 Sur # 12-45",
                      label_visibility="collapsed", key="inp_addr")
        if st.button("Buscar", type="primary", key="btn_dir", use_container_width=True):
            _a_btn = st.session_state.get("inp_addr", "").strip()
            if _a_btn and len(_a_btn) >= 4:
                with st.spinner("Geocodificando..."):
                    _geo_btn = _geocode_bogota(_a_btn)
                if _geo_btn:
                    _glat_b, _glon_b, _gaddr_b = _geo_btn
                    st.session_state["_geo_result"] = {
                        "addr_input": _a_btn, "lat": _glat_b, "lon": _glon_b,
                        "display": _gaddr_b, "ok": True,
                    }
                    st.session_state["marker"]       = (_glat_b, _glon_b)
                    st.session_state["zoom_key"]     = st.session_state.get("zoom_key", 0) + 1
                    st.session_state["clear_count"]  = st.session_state.get("clear_count", 0) + 1
                    st.session_state["_last_geo_addr"] = _a_btn
                    st.session_state.pop("gis_only_id", None)
                    st.session_state.pop("sel_idx", None)
                else:
                    st.session_state["_geo_result"] = {"addr_input": _a_btn, "ok": False}
                    st.session_state.pop("marker", None)
    elif _modo_sb == "Por coordenadas":
        _cts = st.text_input("Coordenadas",
                             placeholder="WGS84: 4.6097,-74.0817  ·  MAGNA: 105921,114072  ·  9377: 4886458,2080016",
                             label_visibility="collapsed", key="inp_coords")
        if st.button("Ir", type="primary", key="btn_coords"):
            if _cts.strip():
                _lc, _lonc, _sis = _parse_coords(_cts)
                if _lc is not None:
                    _mx, _my = _wgs84_to_magna(_lc, _lonc)
                    _ox, _oy = _wgs84_to_9377(_lc, _lonc)
                    _mxd = f"Norte {_my:.0f}  Este {_mx:.0f}" if _mx else "—"
                    _oxd = f"Norte {_oy:.0f}  Este {_ox:.0f}" if _ox else "—"
                    st.session_state["marker"]      = (_lc, _lonc)
                    st.session_state["zoom_key"]    = st.session_state.get("zoom_key", 0) + 1
                    st.session_state["clear_count"] = st.session_state.get("clear_count", 0) + 1
                    st.session_state.pop("sel_idx", None)
                    st.session_state.pop("gis_only_id", None)
                    st.session_state["_last_attr_q"] = ""
                    st.session_state["_last_geo_addr"] = ""
                    st.success(f"**{_sis}**  \nWGS84: `{_lc:.6f}, {_lonc:.6f}`  \n"
                               f"MAGNA Cdad. Bogotá (7458): `{_mxd}`  \n"
                               f"Origen Nacional (9377): `{_oxd}`")
                    if "_lat" in df_reas.columns:
                        _d2 = ((df_reas["_lat"] - _lc)**2 + (df_reas["_lon"] - _lonc)**2)
                        _ni = _d2.idxmin()
                        if _d2[_ni] ** 0.5 < 0.00045:
                            st.session_state["sel_idx"]  = _ni
                            st.info(f"REAS cercano: **{df_reas.loc[_ni, 'REA_Identi']}**")
                else:
                    st.error("Formato no reconocido.")


# ── Header ────────────────────────────────────────────────────────────────────
_n_reas = len(df_reas) if df_reas is not None else 0
hcol, _ = st.columns([3, 4])
hcol.markdown(f"""
<div style="background:linear-gradient(135deg,{NAVY} 0%,#2C3560 100%);
            color:white;padding:14px 20px;border-radius:14px;
            box-shadow:0 4px 16px rgba(26,31,54,.22);">
  <div style="font-size:1rem;font-weight:800;">Módulo 2 — Consulta</div>
  <div style="margin-top:2px;opacity:.7;font-size:.78rem;">
    {_n_reas:,} predios REAS
  </div>
</div>""", unsafe_allow_html=True)

def _sel_rows(ev):
    if ev and ev.selection:
        return (list(ev.selection.rows)
                if hasattr(ev.selection, "rows")
                else ev.selection.get("rows", []))
    return []

# ── Fragmento de búsqueda (input + resultados, sin rerenderizar el mapa) ──────
_busqueda_fragment(df_reas, df_gis)

# ── Mapa ─────────────────────────────────────────────────────────────────────
_mapa_fragment(gj_reas, df_reas,
               df_propietario, df_gis, df_depuracion)

# ── Resultado GIS sin geometría ───────────────────────────────────────────────
_goi = st.session_state.get("gis_only_id")
if _goi and df_gis is not None and "Identificador" in df_gis.columns:
    _sub = df_gis[df_gis["Identificador"].astype(str) == _goi]
    if not _sub.empty:
        _row  = _sub.iloc[0]
        _nm1  = str(_row.get("Nombre 1", "")).strip()
        _nm2  = str(_row.get("Nombre 2", "")).strip()
        _nomb = f"{_nm1} {_nm2}".strip()
        _nhtml = (f'<div style="font-size:.9rem;color:#475569;margin-top:3px;">'
                  f'{_nomb}</div>') if _nomb else ""
        st.markdown(f"""
        <div style="background:white;border-radius:14px;padding:18px 22px;
                    box-shadow:0 4px 20px rgba(0,0,0,.09);
                    border-left:5px solid {AMBER};margin:10px 0 4px;">
          <div style="font-size:.68rem;font-weight:700;color:{SLATE};
                      text-transform:uppercase;letter-spacing:.1em;">
            Resultado GIS — sin geometría asociada</div>
          <div style="font-size:1.1rem;font-weight:900;color:#1E293B;
                      margin-top:4px;">{_goi}</div>{_nhtml}
        </div>""", unsafe_allow_html=True)
        st.dataframe(
            _sub.T.reset_index().rename(columns={"index":"Campo", 0:"Valor"}),
            hide_index=True, use_container_width=True, height=420)
