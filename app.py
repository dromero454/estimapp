import streamlit as st
from supabase import create_client, Client
import uuid
import pandas as pd

st.set_page_config(page_title="Estimapp", page_icon="🏗️", layout="wide")

# Conexión con Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Título con glifo a color y ancla desactivada
st.markdown(
    "<h1 style='margin-bottom: -10px;'>Estimapp <span style='font-family: \"Segoe UI Emoji\", \"Apple Color Emoji\", \"Noto Color Emoji\";'>🏗</span></h1>", 
    unsafe_allow_html=True
)
st.caption("Control de avance físico y financiero de obra")

# =============================================================
# FUNCIONES DE CACHÉ QUIRÚRGICA (LATENCIA CERO)
# =============================================================
@st.cache_data(show_spinner=False)
def get_proyectos():
    res = supabase.table("proyectos").select("*").order("id").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_biblioteca_categorias():
    res = supabase.table("biblioteca_conceptos").select("categoria").execute()
    cats = sorted(list(set(c["categoria"] for c in res.data))) if res.data else ["IMSS"]
    if "IMSS" not in cats:
        cats.insert(0, "IMSS")
    return cats

@st.cache_data(show_spinner=False)
def get_biblioteca_conceptos(categoria: str):
    res = supabase.table("biblioteca_conceptos").select("*").eq("categoria", categoria).order("clave").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_conceptos(id_proyecto: int):
    res = supabase.table("catalogo_conceptos").select("*").eq("id_proyecto", id_proyecto).order("id").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_estimaciones(id_proyecto: int):
    res = supabase.table("estimaciones").select("*").eq("id_proyecto", id_proyecto).order("num_periodo").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_mediciones(id_estimacion: int):
    res = supabase.table("mediciones_campo").select(
        "id, localizacion, eje, tramo, largo, ancho, alto, piezas, cantidad_total, url_foto, url_croquis, catalogo_conceptos(clave, unidad)"
    ).eq("id_estimacion", id_estimacion).order("id").execute()
    return res.data or []

def normalizar_unidad(u: str) -> str:
    """Homologa cualquier variante a formato técnico estándar con superíndices."""
    if not u:
        return ""
    u_up = u.strip().upper()
    if u_up in ["M2", "M²"]: return "m²"
    if u_up in ["M3", "M³"]: return "m³"
    if u_up in ["LITRO", "LITROS", "LT", "LTS", "L"]: return "litros"
    if u_up in ["PZA", "PZAS", "PIEZA", "PIEZAS"]: return "pza"
    if u_up in ["LOTE"]: return "lote"
    if u_up in ["KG"]: return "kg"
    if u_up in ["TRAMO"]: return "tramo"
    if u_up in ["ML"]: return "ml"
    return u.lower()

def extraer_nombre_archivo(url_publica: str) -> str:
    """Extrae el nombre del archivo en Supabase Storage a partir de su URL pública."""
    if not url_publica:
        return ""
    return url_publica.split("/")[-1].split("?")[0]

# Contadores dinámicos para formularios y widgets interactivos
if "del_proy_counter" not in st.session_state: st.session_state.del_proy_counter = 0
if "del_conc_counter" not in st.session_state: st.session_state.del_conc_counter = 0
if "del_est_counter" not in st.session_state: st.session_state.del_est_counter = 0
if "del_med_counter" not in st.session_state: st.session_state.del_med_counter = 0
if "cap_counter" not in st.session_state: st.session_state.cap_counter = 0
if "dim_counter" not in st.session_state: st.session_state.dim_counter = 0

# Pestañas principales
tab_captura, tab_estimaciones, tab_catalogo, tab_proyectos = st.tabs([
    "📐 Captura en Campo", 
    "📑 Estimaciones", 
    "📚 Catálogo de Conceptos", 
    "🏢 Proyectos"
])

# -------------------------------------------------------------
# TAB 1: PROYECTOS
# -------------------------------------------------------------
with tab_proyectos:
    st.subheader("Gestión de Proyectos")
    col_p_alta, col_p_baja = st.columns(2)

    with col_p_alta:
        with st.expander("➕ Dar de alta nuevo proyecto", expanded=False):
            with st.form("form_nuevo_proyecto", clear_on_submit=True):
                nombre_obra = st.text_input("Nombre de la Obra *", placeholder="Inserte aquí el nombre oficial completo de la obra...")
                descripcion_sintetica = st.text_area("Descripción sintética", placeholder="Escriba un resumen del alcance de los trabajos...")
                
                c1, c2 = st.columns(2)
                ubicacion = c1.text_input("Ubicación", placeholder="Ej: Villa de Álvarez, Colima")
                unidad = c2.text_input("Unidad médica / Inmueble", placeholder="Ej: HGZ-01, UMF-19...")
                
                c3, c4 = st.columns(2)
                contrato_no = c3.text_input("N° de Contrato", placeholder="Ej: C5M0077")
                concurso_no = c4.text_input("N° de Concurso / Licitación", placeholder="Ej: LO-50-GYR-050GYR080-N-15-2025")
                
                c5, c6 = st.columns(2)
                contratista = c5.text_input("Contratista / Empresa", placeholder="Razón social o nombre del contratista...")
                residente = c6.text_input("Residente de Obra / Supervisor", placeholder="Nombre del responsable de supervisión...")
                
                submit_proy = st.form_submit_button("Guardar Proyecto")
                if submit_proy:
                    if not nombre_obra.strip():
                        st.error("El nombre de la obra es obligatorio.")
                    else:
                        data = {
                            "nombre_obra": nombre_obra.strip(),
                            "descripcion_sintetica": descripcion_sintetica.strip(),
                            "ubicacion": ubicacion.strip(),
                            "unidad": unidad.strip(),
                            "contrato_no": contrato_no.strip(),
                            "concurso_no": concurso_no.strip(),
                            "contratista": contratista.strip(),
                            "residente_obra": residente.strip()
                        }
                        supabase.table("proyectos").insert(data).execute()
                        get_proyectos.clear()
                        st.success("✅ Proyecto registrado con éxito.")
                        st.rerun()

    lista_proyectos = get_proyectos()
    proy_dict_delete = {}
    if lista_proyectos:
        for idx, p in enumerate(lista_proyectos, start=1):
            proy_dict_delete[f"#{idx} — {p['nombre_obra'][:70]}... ({p.get('contrato_no') or 'S/C'})"] = p["id"]

    with col_p_baja:
        with st.expander("🗑️ Eliminar Proyecto"):
            if not proy_dict_delete:
                st.info("No hay proyectos registrados para eliminar.")
            else:
                proy_del_sel = st.selectbox(
                    "Seleccionar proyecto a borrar:", 
                    list(proy_dict_delete.keys()), 
                    key=f"del_proy_sel_{st.session_state.del_proy_counter}"
                )
                id_proy_borrar = proy_dict_delete[proy_del_sel]
                st.warning("⚠️ Eliminar un proyecto borrará en cascada todo su catálogo, estimaciones y mediciones.")
                
                conf_proy = st.checkbox(
                    "Confirmo la eliminación definitiva del proyecto", 
                    key=f"chk_del_proy_{st.session_state.del_proy_counter}"
                )
                
                if st.button("Eliminar Proyecto", type="primary", disabled=not conf_proy):
                    supabase.table("proyectos").delete().eq("id", id_proy_borrar).execute()
                    get_proyectos.clear()
                    st.session_state.del_proy_counter += 1
                    st.success("Proyecto eliminado correctamente.")
                    st.rerun()

    if lista_proyectos:
        df_p = pd.DataFrame(lista_proyectos)
        df_p.insert(0, "#", range(1, len(df_p) + 1))
        st.dataframe(df_p[["#", "nombre_obra", "unidad", "contrato_no", "ubicacion"]], use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay proyectos registrados.")

# -------------------------------------------------------------
# TAB 2: CATÁLOGO DE CONCEPTOS (CONEXIÓN A BIBLIOTECA MAESTRA)
# -------------------------------------------------------------
with tab_catalogo:
    st.subheader("Catálogo de Conceptos")
    proyectos_dict = {p["nombre_obra"]: p["id"] for p in lista_proyectos} if lista_proyectos else {}

    if not proyectos_dict:
        st.warning("Primero debes registrar un proyecto en la pestaña 'Proyectos'.")
    else:
        proy_seleccionado = st.selectbox("Seleccionar Proyecto Destino", list(proyectos_dict.keys()), key="cat_proy")
        proy_id = proyectos_dict[proy_seleccionado]

        col_importar_bib, col_alta_manual, col_borrar_c = st.columns(3)

        # 1. IMPORTAR DESDE BIBLIOTECA
        with col_importar_bib:
            with st.expander("📚 Importar desde Biblioteca"):
                categorias_disp = get_biblioteca_categorias()
                cat_seleccionada = st.selectbox("Categoría:", categorias_disp, key="sel_cat_bib")
                
                conceptos_bib = get_biblioteca_conceptos(cat_seleccionada)
                if not conceptos_bib:
                    st.info(f"No hay conceptos guardados en la categoría '{cat_seleccionada}'.")
                else:
                    opciones_bib = {
                        f"{c['clave']} — {c['descripcion'][:55]}... ({normalizar_unidad(c['unidad'])})": c 
                        for c in conceptos_bib
                    }
                    conc_bib_sel = st.selectbox("Concepto maestro:", list(opciones_bib.keys()), key="sel_conc_bib")
                    obj_bib = opciones_bib[conc_bib_sel]

                    with st.form("form_importar_bib", clear_on_submit=True):
                        st.caption(f"**Especialidad:** {obj_bib.get('especialidad') or 'General'}")
                        st.write(f"*{obj_bib['descripcion']}*")
                        c_cant_b, c_pu_b = st.columns(2)
                        cant_contratada = c_cant_b.number_input("Cantidad Contratada", min_value=0.001, value=1.0, step=1.0)
                        pu_contratado = c_pu_b.number_input(
                            "Precio Unitario ($)", 
                            min_value=0.0, 
                            value=float(obj_bib.get("precio_referencial") or 0.0), 
                            step=10.0
                        )

                        if st.form_submit_button("➕ Agregar este Concepto al Contrato"):
                            data_c = {
                                "id_proyecto": proy_id,
                                "especialidad": obj_bib.get("especialidad"),
                                "clave": obj_bib["clave"],
                                "descripcion": obj_bib["descripcion"],
                                "unidad": normalizar_unidad(obj_bib["unidad"]),
                                "cantidad_contratada": cant_contratada,
                                "precio_unitario": pu_contratado
                            }
                            supabase.table("catalogo_conceptos").insert(data_c).execute()
                            get_conceptos.clear(proy_id)
                            st.success(f"Concepto {obj_bib['clave']} agregado a la obra.")
                            st.rerun()

        # 2. ALTA MANUAL CON CASILLA A LA BIBLIOTECA (SIN ML)
        with col_alta_manual:
            with st.expander("➕ Alta manual de concepto"):
                with st.form("form_concepto_manual", clear_on_submit=True):
                    esp_m = st.text_input("Especialidad", placeholder="Ej: 01 PRELIMINARES, 04 ALBAÑILERIA...")
                    clave_m = st.text_input("Clave de Concepto *", placeholder="Ej: OC01-015-126")
                    unidad_m = st.selectbox("Unidad", ["m²", "m³", "litros", "pza", "lote", "kg", "tramo"])
                    desc_m = st.text_area("Descripción detallada *", placeholder="Ingrese la descripción completa del concepto...")
                    
                    c_cant_m, c_pu_m = st.columns(2)
                    cant_m = c_cant_m.number_input("Cantidad Contratada", min_value=0.001, value=1.0, step=1.0)
                    pu_m = c_pu_m.number_input("Precio Unitario ($)", min_value=0.0, value=0.0, step=10.0)

                    categoria_target = cat_seleccionada if 'cat_seleccionada' in locals() else "IMSS"
                    guardar_en_bib = st.checkbox(
                        f"Guardar también en la Biblioteca de conceptos: {categoria_target} para futuros proyectos."
                    )

                    submit_manual = st.form_submit_button("Guardar en Catálogo")
                    if submit_manual:
                        if not clave_m.strip() or not desc_m.strip():
                            st.error("La clave y la descripción son obligatorias.")
                        else:
                            data_c = {
                                "id_proyecto": proy_id,
                                "especialidad": esp_m.strip(),
                                "clave": clave_m.strip(),
                                "descripcion": desc_m.strip(),
                                "unidad": normalizar_unidad(unidad_m),
                                "cantidad_contratada": cant_m,
                                "precio_unitario": pu_m
                            }
                            supabase.table("catalogo_conceptos").insert(data_c).execute()
                            get_conceptos.clear(proy_id)

                            if guardar_en_bib:
                                data_b = {
                                    "categoria": categoria_target,
                                    "especialidad": esp_m.strip(),
                                    "clave": clave_m.strip(),
                                    "descripcion": desc_m.strip(),
                                    "unidad": normalizar_unidad(unidad_m),
                                    "precio_referencial": pu_m
                                }
                                try:
                                    supabase.table("biblioteca_conceptos").upsert(data_b, on_conflict="categoria,clave").execute()
                                    get_biblioteca_conceptos.clear(categoria_target)
                                    get_biblioteca_categorias.clear()
                                except Exception:
                                    pass

                            st.success(f"Concepto {clave_m} guardado exitosamente.")
                            st.rerun()

        # 3. ELIMINACIÓN DE CONCEPTOS
        conceptos_proyecto = get_conceptos(proy_id)
        dict_conc_borrar = {}
        if conceptos_proyecto:
            for idx, c in enumerate(conceptos_proyecto, start=1):
                dict_conc_borrar[f"#{idx} — {c['clave']} ({c['descripcion'][:45]}...)"] = c["id"]

        with col_borrar_c:
            with st.expander("🗑️ Eliminar Concepto"):
                if not dict_conc_borrar:
                    st.info("No hay conceptos en este proyecto.")
                else:
                    conc_a_borrar_sel = st.selectbox(
                        "Seleccionar concepto:", 
                        list(dict_conc_borrar.keys()), 
                        key=f"del_conc_sel_{st.session_state.del_conc_counter}"
                    )
                    id_conc_borrar = dict_conc_borrar[conc_a_borrar_sel]
                    
                    conf_conc = st.checkbox(
                        "Confirmo eliminar este concepto", 
                        key=f"chk_del_conc_{st.session_state.del_conc_counter}"
                    )
                    if st.button("Eliminar Concepto", type="primary", disabled=not conf_conc):
                        supabase.table("catalogo_conceptos").delete().eq("id", id_conc_borrar).execute()
                        get_conceptos.clear(proy_id)
                        st.session_state.del_conc_counter += 1
                        st.success("Concepto eliminado del catálogo.")
                        st.rerun()

        # Tabla del catálogo
        if conceptos_proyecto:
            df_c = pd.DataFrame(conceptos_proyecto)
            df_c["unidad"] = df_c["unidad"].apply(normalizar_unidad)
            df_c.insert(0, "#", range(1, len(df_c) + 1))
            st.dataframe(
                df_c[["#", "clave", "especialidad", "unidad", "cantidad_contratada", "precio_unitario", "descripcion"]], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("No hay conceptos dados de alta en este proyecto.")

# -------------------------------------------------------------
# TAB 3: ESTIMACIONES (CELDA DESPLEGABLE DIRECTA CON ST.DATA_EDITOR)
# -------------------------------------------------------------
with tab_estimaciones:
    st.subheader("Periodos de Estimación")
    if not proyectos_dict:
        st.warning("Registra un proyecto primero.")
    else:
        proy_sel_est = st.selectbox("Seleccionar Proyecto", list(proyectos_dict.keys()), key="est_proy")
        id_proy_est = proyectos_dict[proy_sel_est]

        col_est_nueva, col_est_baja = st.columns(2)

        with col_est_nueva:
            with st.expander("➕ Aperturar nueva estimación"):
                with st.form("form_nueva_estimacion", clear_on_submit=True):
                    col_e1, col_e2, col_e3 = st.columns(3)
                    num_periodo = col_e1.number_input("N° Estimación", min_value=1, step=1, value=1)
                    f_ini = col_e2.date_input("Fecha Inicio")
                    f_fin = col_e3.date_input("Fecha Fin")

                    submit_est = st.form_submit_button("Abrir Periodo")
                    if submit_est:
                        try:
                            data = {
                                "id_proyecto": id_proy_est,
                                "num_periodo": int(num_periodo),
                                "periodo_inicio": str(f_ini),
                                "periodo_fin": str(f_fin),
                                "estado": "borrador"
                            }
                            supabase.table("estimaciones").insert(data).execute()
                            get_estimaciones.clear(id_proy_est)
                            st.success(f"Estimación #{num_periodo} aperturada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al aperturar estimación (posiblemente duplicada): {e}")

        estimaciones_proyecto = get_estimaciones(id_proy_est)
        dict_est_borrar = {}
        if estimaciones_proyecto:
            for idx, e in enumerate(estimaciones_proyecto, start=1):
                dict_est_borrar[f"#{idx} — Estimación #{e['num_periodo']} ({e['periodo_inicio']} al {e['periodo_fin']})"] = e["id"]

        with col_est_baja:
            with st.expander("🗑️ Eliminar Estimación"):
                if not dict_est_borrar:
                    st.info("No hay estimaciones registradas.")
                else:
                    est_del_sel = st.selectbox(
                        "Seleccionar estimación a borrar:", 
                        list(dict_est_borrar.keys()), 
                        key=f"del_est_sel_{st.session_state.del_est_counter}"
                    )
                    id_est_borrar = dict_est_borrar[est_del_sel]
                    st.warning("⚠️ Al eliminar la estimación también se borrarán todas sus mediciones de campo.")
                    
                    conf_est = st.checkbox(
                        "Confirmo eliminar esta estimación", 
                        key=f"chk_del_est_{st.session_state.del_est_counter}"
                    )
                    if st.button("Eliminar Estimación", type="primary", disabled=not conf_est):
                        supabase.table("estimaciones").delete().eq("id", id_est_borrar).execute()
                        get_estimaciones.clear(id_proy_est)
                        st.session_state.del_est_counter += 1
                        st.success("Estimación eliminada.")
                        st.rerun()

        if estimaciones_proyecto:
            st.markdown("##### Listado de Estimaciones (puedes cambiar el estado directamente en la celda):")
            df_e = pd.DataFrame(estimaciones_proyecto)
            df_e.insert(0, "#", range(1, len(df_e) + 1))
            
            df_editor_data = df_e[["#", "num_periodo", "periodo_inicio", "periodo_fin", "estado"]].copy()

            edited_table = st.data_editor(
                df_editor_data,
                column_config={
                    "estado": st.column_config.SelectboxColumn(
                        "Estado de la Estimación",
                        help="Cambia el estado de captura de la estimación",
                        width="medium",
                        options=["borrador", "en_revision", "aprobada"],
                        required=True
                    ),
                    "#": st.column_config.NumberColumn("#", disabled=True),
                    "num_periodo": st.column_config.NumberColumn("N° Periodo", disabled=True),
                    "periodo_inicio": st.column_config.DateColumn("Fecha Inicio", disabled=True),
                    "periodo_fin": st.column_config.DateColumn("Fecha Fin", disabled=True),
                },
                hide_index=True,
                use_container_width=True,
                key="editor_estimaciones"
            )

            if "editor_estimaciones" in st.session_state:
                cambios = st.session_state["editor_estimaciones"].get("edited_rows", {})
                if cambios:
                    for row_idx_str, col_mod in cambios.items():
                        if "estado" in col_mod:
                            row_idx = int(row_idx_str)
                            nuevo_estado = col_mod["estado"]
                            id_est_modificar = estimaciones_proyecto[row_idx]["id"]
                            
                            supabase.table("estimaciones").update({"estado": nuevo_estado}).eq("id", id_est_modificar).execute()
                            get_estimaciones.clear(id_proy_est)
                            st.toast(f"✅ Estimación #{estimaciones_proyecto[row_idx]['num_periodo']} actualizada a: {nuevo_estado}")
                            st.rerun()
        else:
            st.info("No se han creado estimaciones para este proyecto.")

# -------------------------------------------------------------
# TAB 4: CAPTURA EN CAMPO (MANEJO DE LITROS Y RESETEO POR UNIDAD)
# -------------------------------------------------------------
with tab_captura:
    st.subheader("Captura de Mediciones y Evidencia")
    if not proyectos_dict:
        st.warning("Configura tu proyecto primero.")
    else:
        proy_sel_cap = st.selectbox("Proyecto", list(proyectos_dict.keys()), key="cap_proy")
        id_proy_cap = proyectos_dict[proy_sel_cap]

        lista_est_cap = get_estimaciones(id_proy_cap)
        estimaciones_dict = {f"Estimación #{e['num_periodo']} ({e['estado']})": e["id"] for e in lista_est_cap} if lista_est_cap else {}

        lista_conc_cap = get_conceptos(id_proy_cap)
        conceptos_dict = {}
        if lista_conc_cap:
            for c in lista_conc_cap:
                clave_c = c["clave"]
                desc_c = c["descripcion"]
                u_norm = normalizar_unidad(c["unidad"])
                if desc_c.lower().startswith(clave_c.lower()):
                    desc_limpia = desc_c[len(clave_c):].lstrip(" .:-")
                else:
                    desc_limpia = desc_c
                etiqueta = f"{clave_c} — {desc_limpia[:60]}... ({u_norm})"
                conceptos_dict[etiqueta] = c

        if not estimaciones_dict:
            st.error("No hay periodos de estimación abiertos para este proyecto. Ve a la pestaña 'Estimaciones'.")
        elif not conceptos_dict:
            st.error("No hay conceptos en el catálogo. Ve a la pestaña 'Catálogo de Conceptos'.")
        else:
            c_est, c_con = st.columns([1, 2])
            est_seleccionada = c_est.selectbox("Periodo Activo", list(estimaciones_dict.keys()))
            concepto_seleccionado = c_con.selectbox("Concepto a Cuantificar", list(conceptos_dict.keys()))

            id_est = estimaciones_dict[est_seleccionada]
            obj_conc = conceptos_dict[concepto_seleccionado]
            id_conc = obj_conc["id"]
            u_base = normalizar_unidad(obj_conc["unidad"])

            # Detección de cambio de unidad: resetea dimensiones a cero sin borrar ubicación
            if "last_unidad_cap" not in st.session_state:
                st.session_state.last_unidad_cap = u_base

            if st.session_state.last_unidad_cap != u_base:
                st.session_state.last_unidad_cap = u_base
                st.session_state.dim_counter += 1
                st.rerun()

            st.markdown("---")
            st.markdown(f"**Concepto:** `{obj_conc['clave']}` | **Unidad en catálogo:** `{u_base}`")
            
            c_ver = st.session_state.cap_counter
            d_ver = f"{st.session_state.cap_counter}_{st.session_state.dim_counter}"

            # Ubicación
            col_loc1, col_loc2, col_loc3 = st.columns(3)
            localizacion = col_loc1.text_input("Localización", placeholder="Ej: VESTIDORES, BAÑOS...", key=f"input_loc_{c_ver}")
            eje = col_loc2.text_input("Eje", placeholder="Ej: 2, A-B...", key=f"input_eje_{c_ver}")
            tramo = col_loc3.text_input("Tramo", placeholder="Ej: 1-2, EJE C...", key=f"input_tramo_{c_ver}")

            # =========================================================
            # CONTROL DE CAMPOS ACTIVOS SEGÚN UNIDAD CONTRACTUAL
            # =========================================================
            es_m3 = (u_base == "m³")
            es_m2 = (u_base == "m²")
            es_lineal = (u_base in ["ml", "tramo"])
            es_litros = (u_base == "litros")
            es_conteo = (u_base in ["pza", "lote", "kg"])

            # Reglas de deshabilitación estrictas
            deshabilitar_alto = not es_m3
            deshabilitar_ancho = es_lineal or es_conteo or es_litros
            deshabilitar_largo = es_conteo or es_litros
            deshabilitar_litros = not es_litros

            etiqueta_ancho = "Ancho / Altura (m)" if es_m2 else "Ancho (m)"

            st.markdown("**Dimensiones Físicas:**")
            col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns(5)
            largo = col_d1.number_input("Largo (m)", min_value=0.0, value=0.0, step=0.5, key=f"num_largo_{d_ver}", disabled=deshabilitar_largo)
            ancho = col_d2.number_input(etiqueta_ancho, min_value=0.0, value=0.0, step=0.5, key=f"num_ancho_{d_ver}", disabled=deshabilitar_ancho)
            alto = col_d3.number_input("Alto (m)", min_value=0.0, value=0.0, step=0.5, key=f"num_alto_{d_ver}", disabled=deshabilitar_alto)
            litros = col_d4.number_input("Litros", min_value=0.0, value=0.0, step=0.5, key=f"num_litros_{d_ver}", disabled=deshabilitar_litros)
            piezas = col_d5.number_input("Piezas", min_value=1.0, value=1.0, step=1.0, key=f"num_piezas_{d_ver}")

            # =========================================================
            # LÓGICA DE CÁLCULO ESTRICTA Y BLINDADA
            # =========================================================
            val_largo = 0.0 if deshabilitar_largo else float(largo)
            val_ancho = 0.0 if deshabilitar_ancho else float(ancho)
            val_alto = 0.0 if deshabilitar_alto else float(alto)
            val_litros = 0.0 if deshabilitar_litros else float(litros)

            if es_m3:
                calc_preview = val_largo * val_ancho * val_alto * piezas
            elif es_m2:
                if val_largo == 0 or val_ancho == 0:
                    calc_preview = 0.0
                else:
                    calc_preview = val_largo * val_ancho * piezas
            elif es_lineal:
                calc_preview = val_largo * piezas
            elif es_litros:
                calc_preview = val_litros * piezas
            else: # pza, lote, kg
                calc_preview = piezas

            calc_preview = round(float(calc_preview), 3)

            # La unidad resultante siempre coincide con la del catálogo
            st.info(f"📐 Cantidad Calculada en tiempo real: **{calc_preview:.3f} {u_base}**")

            # Carga de archivos
            col_f1, col_f2 = st.columns(2)
            foto = col_f1.file_uploader("Fotografía de Evidencia", type=["jpg", "jpeg", "png"], key=f"file_foto_{c_ver}")
            croquis = col_f2.file_uploader("Croquis / Plano", type=["jpg", "jpeg", "png"], key=f"file_croquis_{c_ver}")

            # Guardar medición
            if st.button("💾 Guardar Medición en Generador", type="primary"):
                if calc_preview <= 0:
                    st.warning("La cantidad total calculada debe ser mayor a 0.")
                else:
                    url_foto = None
                    url_croquis = None

                    if foto:
                        ext = foto.name.split(".")[-1]
                        fname_f = f"{uuid.uuid4()}.{ext}"
                        supabase.storage.from_("evidencias").upload(fname_f, foto.getvalue(), {"content-type": foto.type})
                        url_foto = supabase.storage.from_("evidencias").get_public_url(fname_f)

                    if croquis:
                        ext = croquis.name.split(".")[-1]
                        fname_c = f"{uuid.uuid4()}.{ext}"
                        supabase.storage.from_("evidencias").upload(fname_c, croquis.getvalue(), {"content-type": croquis.type})
                        url_croquis = supabase.storage.from_("evidencias").get_public_url(fname_c)

                    data_med = {
                        "id_estimacion": id_est,
                        "id_concepto": id_conc,
                        "localizacion": localizacion.strip(),
                        "eje": eje.strip(),
                        "tramo": tramo.strip(),
                        "largo": val_largo,
                        "ancho": val_ancho,
                        "alto": val_alto,
                        "piezas": float(piezas),
                        "cantidad_total": calc_preview,
                        "url_foto": url_foto,
                        "url_croquis": url_croquis
                    }
                    supabase.table("mediciones_campo").insert(data_med).execute()
                    get_mediciones.clear(id_est)
                    st.session_state.cap_counter += 1
                    st.session_state.dim_counter += 1
                    st.success("✅ Medición guardada correctamente. Formulario reiniciado.")
                    st.rerun()

            # Resumen de mediciones
            st.markdown("### Mediciones registradas en este periodo:")
            mediciones_periodo = get_mediciones(id_est)

            if mediciones_periodo:
                rows = []
                meds_borrar_dict = {}
                for idx, m in enumerate(mediciones_periodo, start=1):
                    clave_c = m["catalogo_conceptos"]["clave"]
                    u_c = normalizar_unidad(m["catalogo_conceptos"]["unidad"])
                    rows.append({
                        "#": idx,
                        "Clave": clave_c,
                        "Localización": m["localizacion"],
                        "Eje-Tramo": f"{m['eje']} / {m['tramo']}",
                        "Medidas (L x An x Al)": f"{m['largo']} x {m['ancho']} x {m['alto']}",
                        "Pzas": m["piezas"],
                        "Cantidad": f"{m['cantidad_total']} {u_c}",
                        "Tiene Foto": "Sí" if m["url_foto"] else "No",
                        "Tiene Croquis": "Sí" if m["url_croquis"] else "No"
                    })
                    label_del = f"#{idx} — {clave_c} ({m['localizacion']} — {m['cantidad_total']} {u_c})"
                    meds_borrar_dict[label_del] = m

                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                with st.expander("🗑️ Eliminar una medición de este periodo"):
                    med_a_borrar_label = st.selectbox(
                        "Seleccionar medición a remover:", 
                        list(meds_borrar_dict.keys()), 
                        key=f"sel_med_del_{st.session_state.del_med_counter}"
                    )
                    obj_med_borrar = meds_borrar_dict[med_a_borrar_label]
                    
                    conf_med = st.checkbox(
                        "Confirmo eliminar esta medición", 
                        key=f"chk_del_med_{st.session_state.del_med_counter}"
                    )
                    
                    if st.button("Eliminar Medición Seleccionada", type="primary", disabled=not conf_med):
                        archivos_a_borrar = []
                        if obj_med_borrar.get("url_foto"):
                            nombre_f = extraer_nombre_archivo(obj_med_borrar["url_foto"])
                            if nombre_f: archivos_a_borrar.append(nombre_f)
                        if obj_med_borrar.get("url_croquis"):
                            nombre_c = extraer_nombre_archivo(obj_med_borrar["url_croquis"])
                            if nombre_c: archivos_a_borrar.append(nombre_c)

                        if archivos_a_borrar:
                            try:
                                supabase.storage.from_("evidencias").remove(archivos_a_borrar)
                            except Exception:
                                pass

                        supabase.table("mediciones_campo").delete().eq("id", obj_med_borrar["id"]).execute()
                        get_mediciones.clear(id_est)
                        st.session_state.del_med_counter += 1
                        st.success("Medición y evidencias asociadas eliminadas.")
                        st.rerun()
            else:
                st.write("No hay mediciones capturadas todavía para esta estimación.")