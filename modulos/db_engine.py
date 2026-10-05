import streamlit as st
from supabase import Client
import pandas as pd
from PIL import Image
import io
import unicodedata
import re

def normalizar_unidad(u: str) -> str:
    if pd.isna(u) or not u or str(u).strip() == "": return "s/u"
    u_up = str(u).strip().upper()
    if u_up in ["M2", "M²"]: return "m²"
    if u_up in ["M3", "M³"]: return "m³"
    if u_up in ["LITRO", "LITROS", "LT", "LTS", "L", "ML"]: return "litros"
    if u_up in ["KG", "KILOGRAMO", "KILOS"]: return "kg"
    if u_up in ["PZA", "PZAS", "PIEZA", "PIEZAS"]: return "pza"
    if u_up in ["LOTE"]: return "lote"
    if u_up in ["TRAMO"]: return "tramo"
    if u_up in ["JGO", "JUEGO", "JGOS"]: return "jgo"
    if u_up in ["M", "METRO", "METROS"]: return "m"
    if u_up in ["H", "HR", "HORAS", "HORA", "MANO DE OBRA", "MANO DE OBRA (H)"]: return "mano de obra (h)"
    if u_up in ["M3/KM", "M³/KM", "M3 / KM", "M³ / KM"]: return "m³/km"
    return u_up.lower()

unidades_list = ["m²", "m³", "litros", "kg", "pza", "lote", "jgo", "tramo", "m", "mano de obra (h)", "m³/km", "s/u"]

@st.cache_data(show_spinner=False)
def get_proyectos(user_id: str):
    supabase = st.session_state["supabase_client"]
    res = supabase.table("proyectos").select("*").or_(f"user_id.eq.{user_id},user_id.is.null").order("id").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_biblioteca_instituciones(user_id: str):
    """Consulta 'instituciones' y 'biblioteca_conceptos' para asegurar que aparezcan todas sin duplicados."""
    supabase = st.session_state["supabase_client"]
    insts = set(["IMSS", "Poder Judicial de la Federación"])
    
    # 1. Leer de la tabla dedicada 'instituciones'
    try:
        res_inst = supabase.table("instituciones")\
            .select("nombre")\
            .or_(f"user_id.eq.{user_id},user_id.is.null")\
            .execute()
        for r in (res_inst.data or []):
            nom = (r.get("nombre") or "").strip()
            if nom and nom.upper() != "EMPTY":
                insts.add(nom)
    except Exception:
        pass

    # 2. Leer de 'biblioteca_conceptos' por retrocompatibilidad
    try:
        res_bib = supabase.table("biblioteca_conceptos")\
            .select("institucion")\
            .or_(f"user_id.eq.{user_id},user_id.is.null")\
            .execute()
        for r in (res_bib.data or []):
            nom = (r.get("institucion") or "").strip()
            if nom:
                insts.add(nom)
    except Exception:
        pass
        
    return sorted(list(insts))

@st.cache_data(show_spinner=False)
def get_biblioteca_conceptos(institucion: str, user_id: str):
    """Obtiene los conceptos maestros filtrando por la institución activa."""
    supabase = st.session_state["supabase_client"]
    res = supabase.table("biblioteca_conceptos")\
        .select("*")\
        .or_(f"institucion.eq.{institucion},categoria.eq.{institucion}")\
        .or_(f"user_id.eq.{user_id},user_id.is.null")\
        .order("clave")\
        .execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_conceptos(id_proyecto: int):
    supabase = st.session_state["supabase_client"]
    res = supabase.table("catalogo_conceptos").select("*").eq("id_proyecto", id_proyecto).order("id").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_estimaciones(id_proyecto: int):
    supabase = st.session_state["supabase_client"]
    res = supabase.table("estimaciones").select("*").eq("id_proyecto", id_proyecto).order("num_periodo").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_mediciones(id_estimacion: int):
    supabase = st.session_state["supabase_client"]
    res = supabase.table("mediciones_campo").select(
        "id, localizacion, eje, tramo, largo, ancho, alto, piezas, cantidad_total, url_foto, url_croquis, id_concepto, catalogo_conceptos(clave, unidad, precio_unitario)"
    ).eq("id_estimacion", id_estimacion).order("id").execute()
    return res.data or []

def generar_plantilla_excel(tipo="biblioteca"):
    output = io.BytesIO()
    if tipo == "biblioteca":
        cols = ["Especialidad (Opcional)", "Categoria (Opcional)", "Clave", "Descripcion", "Unidad", "Precio_Unitario"]
    else:
        cols = ["Especialidad (Opcional)", "Categoria (Opcional)", "Clave", "Descripcion", "Unidad", "Cantidad_Contratada", "Precio_Unitario"]
        
    df = pd.DataFrame(columns=cols)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
    return output.getvalue()

def _limpiar_texto_header(txt) -> str:
    if not txt or pd.isna(txt): return ""
    s = str(txt).strip().lower().replace("_", " ")
    s = s.replace("(opcional)", "").replace("(opc)", "")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())

def procesar_excel_importacion(df: pd.DataFrame, tipo="proyecto"):
    """
    Parsea e interpreta de forma tolerante y robusta un DataFrame importado desde Excel,
    admitiendo variaciones en nombres de columnas (con o sin '(Opcional)', acentos, espacios o guiones bajos).
    """
    cols_map = {_limpiar_texto_header(c): c for c in df.columns}
    
    def buscar_col(candidatos):
        for cand in candidatos:
            c_norm = _limpiar_texto_header(cand)
            if c_norm in cols_map:
                return cols_map[c_norm]
        return None

    c_clave = buscar_col(["clave", "codigo", "clave concepto", "clave de concepto", "no concepto", "item"])
    c_desc = buscar_col(["descripcion", "concepto", "descripcion de concepto", "detalle", "descripcion detallada"])
    c_unidad = buscar_col(["unidad", "und", "uni", "u"])
    c_pu = buscar_col(["precio unitario", "precio referencial", "precio", "pu", "p u", "costo unitario", "p unitario", "costo"])
    c_cant = buscar_col(["cantidad contratada", "cantidad", "cant contratada", "cant", "volumen contratado", "volumen"]) if tipo == "proyecto" else None
    c_esp = buscar_col(["especialidad", "subpartida"])
    c_cat = buscar_col(["categoria", "partida"])

    faltantes = []
    if not c_clave: faltantes.append("Clave")
    if not c_desc: faltantes.append("Descripción")
    if not c_unidad: faltantes.append("Unidad")
    if not c_pu: faltantes.append("Precio Unitario")
    if tipo == "proyecto" and not c_cant: faltantes.append("Cantidad Contratada")

    if faltantes:
        return False, f"Columnas obligatorias faltantes en el Excel: {', '.join(faltantes)}", []

    records = []
    for _, row in df.iterrows():
        clave = str(row[c_clave]).strip() if c_clave and not pd.isna(row[c_clave]) else ""
        desc = str(row[c_desc]).strip() if c_desc and not pd.isna(row[c_desc]) else ""
        if not clave or clave.lower() == "nan" or not desc or desc.lower() == "nan":
            continue
        
        u = normalizar_unidad(str(row[c_unidad])) if c_unidad else "s/u"
        pu = float(pd.to_numeric(row[c_pu], errors="coerce") or 0.0) if c_pu else 0.0
        esp = str(row[c_esp]).strip() if c_esp and not pd.isna(row[c_esp]) else ""
        cat = str(row[c_cat]).strip() if c_cat and not pd.isna(row[c_cat]) else ""
        
        rec = {
            "especialidad": esp,
            "categoria": cat,
            "clave": clave,
            "descripcion": desc,
            "unidad": u
        }
        if tipo == "proyecto":
            cant = float(pd.to_numeric(row[c_cant], errors="coerce") or 0.0) if c_cant else 0.0
            rec["cantidad_contratada"] = cant
            rec["precio_unitario"] = pu
        else:
            rec["precio_referencial"] = pu
            
        records.append(rec)
        
    return True, None, records

def extraer_nombre_archivo(url_publica: str) -> str:
    if not url_publica: return ""
    return url_publica.split("/")[-1].split("?")[0]

def optimizar_imagen(archivo_subido, max_dim=1280, calidad=80):
    try:
        img = Image.open(archivo_subido)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=calidad, optimize=True)
        return buffer.getvalue(), "image/jpeg"
    except Exception:
        return archivo_subido.getvalue(), archivo_subido.type