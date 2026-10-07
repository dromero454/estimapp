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
UNIDADES_ENTERAS = {"pza", "jgo"}

def admite_decimales(unidad: str) -> bool:
    """Retorna False si la unidad es estrictamente discreta/entera (pza, jgo), True en caso contrario."""
    u_norm = normalizar_unidad(unidad)
    return u_norm not in UNIDADES_ENTERAS

@st.cache_data(show_spinner=False)
def get_proyectos(user_id: str):
    supabase = st.session_state["supabase_client"]
    res = supabase.table("proyectos").select("*").eq("user_id", user_id).order("id").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_biblioteca_instituciones(user_id: str):
    """Consulta 'instituciones' y 'biblioteca_conceptos' del usuario activo sin duplicados ni huérfanos."""
    supabase = st.session_state["supabase_client"]
    insts = set()
    
    # 1. Leer de la tabla dedicada 'instituciones' del usuario
    try:
        res_inst = supabase.table("instituciones")\
            .select("nombre")\
            .eq("user_id", user_id)\
            .execute()
        for r in (res_inst.data or []):
            nom = (r.get("nombre") or "").strip()
            if nom and nom.upper() != "EMPTY":
                insts.add(nom)
    except Exception:
        pass

    # 2. Leer de 'biblioteca_conceptos' del usuario
    try:
        res_bib = supabase.table("biblioteca_conceptos")\
            .select("institucion")\
            .eq("user_id", user_id)\
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
    """Obtiene los conceptos maestros filtrando por la institución activa y user_id."""
    if not institucion:
        return []
    supabase = st.session_state["supabase_client"]
    res = supabase.table("biblioteca_conceptos")\
        .select("*")\
        .or_(f"institucion.eq.{institucion},categoria.eq.{institucion}")\
        .eq("user_id", user_id)\
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
        cols = [
            "Especialidad (Opcional)", "Categoria (Opcional)", "Clave", "Descripcion", "Unidad",
            "Precio_Unitario", "Costo_Material (Opcional)", "Costo_MdeO (Opcional)", "Costo_Herr (Opcional)", "Costo_Ind (Opcional)"
        ]
    else:
        cols = [
            "Especialidad (Opcional)", "Categoria (Opcional)", "Clave", "Descripcion", "Unidad",
            "Cantidad_Contratada", "Precio_Unitario", "Costo_Material (Opcional)", "Costo_MdeO (Opcional)", "Costo_Herr (Opcional)", "Costo_Ind (Opcional)", "%_Utilidad (Opcional)"
        ]
        
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

def procesar_excel_importacion(df: pd.DataFrame, tipo="proyecto", pct_utilidad_default=15.0):
    """
    Parsea e interpreta de forma tolerante y robusta un DataFrame importado desde Excel,
    admitiendo variaciones en nombres de columnas (con o sin '(Opcional)', acentos, espacios o guiones bajos),
    y dando soporte Dual Path tanto a formatos clásicos v1.0 como extendidos v2.0 (APU + Utilidad).
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
    
    # Columnas analíticas opcionales v2.0
    c_mat = buscar_col(["costo material", "costo mat", "material", "costo de material", "mat"])
    c_mo = buscar_col(["costo mdeo", "costo mano de obra", "mano de obra", "costo mo", "mdeo", "mo"])
    c_herr = buscar_col(["costo herr", "costo herramienta", "costo equipo", "herramienta", "herr", "equipo"])
    c_ind = buscar_col(["costo ind", "costo indirecto", "costo indirectos", "indirecto", "indirectos", "ind"])
    c_util = buscar_col(["utilidad", "porcentaje utilidad", "pct utilidad", "porc utilidad", "utilidad pct"]) if tipo == "proyecto" else None

    faltantes = []
    if not c_clave: faltantes.append("Clave")
    if not c_desc: faltantes.append("Descripción")
    if not c_unidad: faltantes.append("Unidad")
    if not c_pu and not (c_mat or c_mo or c_herr or c_ind):
        faltantes.append("Precio Unitario")
    if tipo == "proyecto" and not c_cant:
        faltantes.append("Cantidad Contratada")

    if faltantes:
        return False, f"Columnas obligatorias faltantes en el Excel: {', '.join(faltantes)}", []

    records = []
    for _, row in df.iterrows():
        clave = str(row[c_clave]).strip() if c_clave and not pd.isna(row[c_clave]) else ""
        desc = str(row[c_desc]).strip() if c_desc and not pd.isna(row[c_desc]) else ""
        if not clave or clave.lower() == "nan" or not desc or desc.lower() == "nan":
            continue
        
        u = normalizar_unidad(str(row[c_unidad])) if c_unidad else "s/u"
        pu_raw = float(pd.to_numeric(row[c_pu], errors="coerce") or 0.0) if c_pu and not pd.isna(row[c_pu]) else 0.0
        pu = round(max(0.0, pu_raw), 2)
        esp = str(row[c_esp]).strip() if c_esp and not pd.isna(row[c_esp]) else ""
        cat = str(row[c_cat]).strip() if c_cat and not pd.isna(row[c_cat]) else ""
        
        val_mat = round(max(0.0, float(pd.to_numeric(row[c_mat], errors="coerce") or 0.0)), 2) if c_mat and not pd.isna(row[c_mat]) else 0.0
        val_mo = round(max(0.0, float(pd.to_numeric(row[c_mo], errors="coerce") or 0.0)), 2) if c_mo and not pd.isna(row[c_mo]) else 0.0
        val_herr = round(max(0.0, float(pd.to_numeric(row[c_herr], errors="coerce") or 0.0)), 2) if c_herr and not pd.isna(row[c_herr]) else 0.0
        val_ind = round(max(0.0, float(pd.to_numeric(row[c_ind], errors="coerce") or 0.0)), 2) if c_ind and not pd.isna(row[c_ind]) else 0.0
        suma_analitica = round(val_mat + val_mo + val_herr + val_ind, 2)
        
        rec = {
            "especialidad": esp,
            "categoria": cat,
            "clave": clave,
            "descripcion": desc,
            "unidad": u,
            "costo_material": val_mat,
            "costo_mano_obra": val_mo,
            "costo_herramienta": val_herr,
            "costo_indirecto": val_ind
        }
        
        if tipo == "proyecto":
            cant_raw = float(pd.to_numeric(row[c_cant], errors="coerce") or 0.0) if c_cant else 0.0
            cant = round(cant_raw) if not admite_decimales(u) else round(cant_raw, 2)
            rec["cantidad_contratada"] = cant
            
            # Utilidad por concepto (hereda la del proyecto si no se especifica)
            if c_util and not pd.isna(row[c_util]):
                util_raw = pd.to_numeric(row[c_util], errors="coerce")
                rec["porcentaje_utilidad"] = round(max(0.0, float(util_raw)), 2) if not pd.isna(util_raw) else float(pct_utilidad_default)
            else:
                rec["porcentaje_utilidad"] = round(float(pct_utilidad_default), 2)
                
            # Precio unitario resultante
            if suma_analitica > 0:
                if pu == 0.0:
                    rec["precio_unitario"] = round(suma_analitica * (1.0 + rec["porcentaje_utilidad"] / 100.0), 2)
                else:
                    rec["precio_unitario"] = pu
            else:
                rec["precio_unitario"] = pu
        else:
            # En biblioteca no se almacena porcentaje ni monto de utilidad
            if suma_analitica > 0 and pu == 0.0:
                rec["precio_referencial"] = suma_analitica
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