import streamlit as st
from supabase import create_client, Client
import uuid
import pandas as pd
import datetime

# =============================================================
# IMPORTACIÓN DE MÓDULOS DE BACKEND
# =============================================================
import importlib
import modulos.db_engine
importlib.reload(modulos.db_engine)

from modulos.auth_engine import render_login_card
from modulos.db_engine import (
    normalizar_unidad, unidades_list, get_proyectos, get_biblioteca_instituciones,
    get_biblioteca_conceptos, get_conceptos, get_estimaciones, get_mediciones,
    generar_plantilla_excel, extraer_nombre_archivo, optimizar_imagen,
    procesar_excel_importacion
)
from modulos.pdf_engine import generar_pdf_resumen_ejecutivo
from modulos.excel_engine import inyectar_datos_excel_imss, inyectar_datos_excel_pjf, generar_excel_estimapp, descargar_plantilla_supabase

# =============================================================
# CONFIGURACIÓN INICIAL Y CLIENTE SUPABASE
# =============================================================
st.set_page_config(page_title="Estimapp", page_icon="🏗", layout="wide")

if "supabase_client" not in st.session_state:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    st.session_state["supabase_client"] = create_client(url, key)

supabase: Client = st.session_state["supabase_client"]

# Detector universal de Logout (Rápido y persistente)
params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
if "logout" in params:
    if hasattr(st, "query_params"):
        try: del st.query_params["logout"]
        except Exception: pass
    else:
        st.experimental_set_query_params()
    try: supabase.auth.sign_out()
    except Exception: pass
    st.session_state.clear()
    st.rerun()

# =============================================================
# CSS (HEADER COMPLETO STICKY Y TABS)
# =============================================================
st.markdown("""
<style>
header[data-testid="stHeader"] { display: none !important; }
.block-container { padding-top: 0.5rem !important; padding-bottom: 2rem !important; }

/* El contenedor del Header completo fijado al techo */
div[data-testid="stElementContainer"]:has(.sticky-header) {
    position: sticky !important; 
    top: 0 !important; 
    z-index: 99 !important;
    background-color: var(--background-color, #ffffff) !important;
}

.sticky-header {
    background-color: var(--background-color, #ffffff) !important;
    padding-top: 4px; 
    padding-bottom: 4px;
    width: 100%;
}

/* Las Tabs pegadas exactamente debajo del Header completo */
div[data-baseweb="tab-list"], div[role="tablist"] {
    position: sticky !important; 
    top: 72px !important; /* Altura exacta del Header */
    z-index: 98 !important;
    background-color: var(--background-color, #ffffff) !important;
    padding-top: 4px !important; 
    padding-bottom: 4px !important;
    border-bottom: 1px solid rgba(0, 0, 0, 0.08) !important;
}

button[data-baseweb="tab"], button[data-baseweb="tab"] p, button[data-baseweb="tab"] span {
    font-size: 1.15rem !important; font-weight: 500 !important;
}

/* Botón de Salir con estilo idéntico a Streamlit */
.btn-salir-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 500;
    padding: 0.25rem 1rem;
    border-radius: 0.5rem;
    min-height: 38px;
    line-height: 1.6;
    color: #31333f !important;
    background-color: #ffffff;
    border: 1px solid rgba(49, 51, 63, 0.2);
    text-decoration: none !important;
    font-size: 0.95rem;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-salir-link:hover {
    border-color: #ff4b4b !important;
    color: #ff4b4b !important;
    background-color: #fff5f5;
    text-decoration: none !important;
}
</style>
""", unsafe_allow_html=True)

# Variables de estado globales
keys = ["del_proy_counter", "del_conc_counter", "del_est_counter", "ed_est_counter", "ed_cat_counter", "ed_med_counter", "ed_bib_counter", "ed_proy_counter", "del_med_counter", "cap_counter", "dim_counter", "bib_del_counter", "up_bib_key", "up_proy_key", "ms_lote_key", "new_cat_key", "cat_activa"]
for k in keys:
    if k not in st.session_state: st.session_state[k] = 0 if "counter" in k or "key" in k else "IMSS"

# Limpieza preventiva de claves obsoletas en sesión para evitar bucles de error persistentes
for legacy_k in ["editor_estimaciones", "editor_catalogo", "editor_mediciones", "editor_proyectos"]:
    if legacy_k in st.session_state:
        st.session_state.pop(legacy_k, None)

# =============================================================
# FLUJO DE AUTENTICACIÓN
# =============================================================
if "user" not in st.session_state or st.session_state["user"] is None:
    render_login_card(supabase)
    st.stop()

user_id = st.session_state["user"].id
perfil_usr = st.session_state.get("perfil", {})
nom_usr = perfil_usr.get("nombre") or st.session_state["user"].email.split("@")[0]
email_usr = st.session_state["user"].email
empresa_usr = perfil_usr.get("empresa_despacho") or "Independiente"

# =============================================================
# ENCABEZADO UNIFICADO STICKY (UN SOLO CONTENEDOR)
# =============================================================
st.markdown(f"""
<div class="sticky-header">
    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
        <!-- Lado Izquierdo: Logo + Institución + Subtítulo -->
        <div>
            <div style="display: flex; align-items: baseline; gap: 12px; flex-wrap: nowrap;">
                <h1 style='margin: 0; padding: 0; font-size: 2.3rem; line-height: 1.15; font-weight: 700; white-space: nowrap;'>
                    Estimapp <span style='font-family: "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji";'>🏗</span>
                </h1>
                <span style='font-size: 1.1rem; font-weight: 500; color: #6c757d; border-left: 2px solid #cbd5e1; padding-left: 12px; white-space: nowrap;'>
                    | {empresa_usr}
                </span>
            </div>
            <div style='color: #6c757d; font-size: 1.0rem; margin-top: 2px; margin-bottom: 2px;'>
                Control de avance físico y financiero de obra
            </div>
        </div>
        <!-- Lado Derecho: Usuario + Botón Salir -->
        <div style="display: flex; align-items: center; gap: 16px;">
            <div style='text-align: right; line-height: 1.25;'>
                <div style='font-weight: 600; font-size: 0.95rem; color: #1e293b;'>{nom_usr}</div>
                <div style='font-size: 0.8rem; color: #64748b;'>{email_usr}</div>
            </div>
            <a href="?logout=1" target="_self" class="btn-salir-link">Salir</a>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Generador de nombres dinámicos para evitar caché en descargas Excel
ts_descarga = int(datetime.datetime.now().timestamp())

# =============================================================
# INTERFAZ PRINCIPAL (6 PESTAÑAS)
# =============================================================
tab_dashboard, tab_captura, tab_estimaciones, tab_catalogo, tab_biblioteca, tab_proyectos = st.tabs([
    "📊 Control Presupuestal", "📐 Captura en Campo", "📑 Estimaciones", 
    "📚 Catálogo del Proyecto", "📖 Biblioteca Maestra de Conceptos", "🏢 Proyectos"
])

lista_proyectos = get_proyectos(user_id)
proyectos_dict = {p["nombre_obra"]: p["id"] for p in lista_proyectos} if lista_proyectos else {}

# -------------------------------------------------------------
# TAB 1: CONTROL PRESUPUESTAL (DASHBOARD)
# -------------------------------------------------------------
with tab_dashboard:
    st.markdown("### Control Presupuestal y Balance Contractual 🔗")
    if not proyectos_dict: st.info("Registra un proyecto para visualizar el análisis financiero.")
    else:
        proy_sel_dash = st.selectbox("Proyecto a Auditar", list(proyectos_dict.keys()), key="dash_proy")
        id_proy_dash = proyectos_dict[proy_sel_dash]
        proy_obj_actual = next((p for p in lista_proyectos if p["id"] == id_proy_dash), {})

        conceptos_dash = get_conceptos(id_proy_dash)
        estimaciones_dash = get_estimaciones(id_proy_dash)

        if not conceptos_dash: st.warning("Este proyecto no tiene conceptos en su catálogo.")
        else:
            dict_conceptos_info = {c["id"]: c for c in conceptos_dash}
            monto_contratado_total = sum(float(c.get("cantidad_contratada") or 0.0) * float(c.get("precio_unitario") or 0.0) for c in conceptos_dash)
            meds_por_est_conc = {}
            monto_estimado_global = 0.0
            conceptos_con_estimacion = set()

            for e in estimaciones_dash:
                meds = get_mediciones(e["id"])
                for m in meds:
                    c_id = m.get("id_concepto")
                    if c_id in dict_conceptos_info:
                        cant = float(m["cantidad_total"] or 0.0)
                        pu = float(dict_conceptos_info[c_id].get("precio_unitario") or 0.0)
                        meds_por_est_conc[(e["id"], c_id)] = meds_por_est_conc.get((e["id"], c_id), 0.0) + cant
                        monto_estimado_global += (cant * pu)
                        conceptos_con_estimacion.add(c_id)

            saldo_por_ejercer = round(monto_contratado_total - monto_estimado_global, 2)
            pct_global = round((monto_estimado_global / monto_contratado_total * 100), 2) if monto_contratado_total > 0 else 0.0

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Monto Contratado Total", f"${monto_contratado_total:,.2f}")
            kpi2.metric("Monto Estimado Acumulado", f"${monto_estimado_global:,.2f}")
            kpi3.metric("Saldo por Ejercer (Meta = $0)", f"${saldo_por_ejercer:,.2f}", delta=f"{saldo_por_ejercer:,.2f}", delta_color="inverse")
            kpi4.metric("Avance Financiero Global", f"{pct_global:.2f}%")

            st.progress(min(pct_global / 100.0, 1.0))
            st.markdown("---")

            filas_dash = []
            acumulados_cronologicos = {c["id"]: 0.0 for c in conceptos_dash}

            for e in estimaciones_dash:
                num_p = e["num_periodo"]
                label_est = f"Estimación #{num_p}"
                for c in conceptos_dash:
                    c_id = c["id"]
                    if (e["id"], c_id) in meds_por_est_conc:
                        cant_periodo = round(meds_por_est_conc[(e["id"], c_id)], 3)
                        acumulados_cronologicos[c_id] += cant_periodo
                        cant_acum = round(acumulados_cronologicos[c_id], 3)
                        cant_cont = float(c.get("cantidad_contratada") or 0.0)
                        pu = float(c.get("precio_unitario") or 0.0)
                        imp_periodo, imp_acum = round(cant_periodo * pu, 2), round(cant_acum * pu, 2)
                        saldo_vol, saldo_fin = round(cant_cont - cant_acum, 3), round((cant_cont * pu) - imp_acum, 2)
                        avance = round((cant_acum / cant_cont * 100), 1) if cant_cont > 0 else 0.0

                        if avance > 100.0: estatus_badge = f"🚨 Sobregirado (+{round(avance - 100.0, 1)}%)"
                        elif avance == 100.0: estatus_badge = "✅ Concluido (100%)"
                        else: estatus_badge = "🟢 En proceso"

                        filas_dash.append({
                            "Estimación": label_est, "Periodo": f"{e['periodo_inicio']} al {e['periodo_fin']}", "Estado": e.get("estado", "borrador"),
                            "Clave": c["clave"], "Unidad": normalizar_unidad(c["unidad"]),
                            "Cant. Contratada": cant_cont, "Cant. en Periodo": cant_periodo, "Cant. Acumulada": cant_acum,
                            "Saldo Físico": saldo_vol, "P.U. ($)": pu, "Importe Periodo ($)": imp_periodo,
                            "Importe Acumulado ($)": imp_acum, "Saldo Financiero ($)": saldo_fin,
                            "% Avance": avance, "Estatus": estatus_badge, "_sort_est": num_p, "_sort_avance": avance
                        })

            for c in conceptos_dash:
                if c["id"] not in conceptos_con_estimacion:
                    cant_cont, pu = float(c.get("cantidad_contratada") or 0.0), float(c.get("precio_unitario") or 0.0)
                    filas_dash.append({
                        "Estimación": "Sin estimar", "Periodo": "—", "Estado": "pendiente",
                        "Clave": c["clave"], "Unidad": normalizar_unidad(c["unidad"]),
                        "Cant. Contratada": cant_cont, "Cant. en Periodo": 0.0, "Cant. Acumulada": 0.0,
                        "Saldo Físico": cant_cont, "P.U. ($)": pu, "Importe Periodo ($)": 0.0,
                        "Importe Acumulado ($)": 0.0, "Saldo Financiero ($)": round(cant_cont * pu, 2),
                        "% Avance": 0.0, "Estatus": "⚪ Sin iniciar", "_sort_est": 9999, "_sort_avance": 0.0
                    })

            if filas_dash:
                df_dash = pd.DataFrame(filas_dash)
                df_dash = df_dash.sort_values(by=["_sort_est", "_sort_avance"], ascending=[True, False]).reset_index(drop=True)
                df_dash.insert(3, "#", range(1, len(df_dash) + 1))
                df_dash = df_dash.drop(columns=["_sort_est", "_sort_avance"])

                col_titulo_rep, col_btn_pdf = st.columns([3, 1])
                with col_titulo_rep:
                    st.markdown("##### Desglose por Estimación y Concepto (Auditoría Integral de Avance):")
                with col_btn_pdf:
                    pdf_bytes = generar_pdf_resumen_ejecutivo(
                        proy_info=proy_obj_actual, monto_cont=monto_contratado_total,
                        monto_est=monto_estimado_global, saldo_ejercer=saldo_por_ejercer,
                        pct_global=pct_global, df_conceptos=df_dash
                    )
                    fecha_gen = datetime.date.today().strftime("%d/%m/%Y")
                    contrato_nom = proy_obj_actual.get('contrato_no') or 'Obra'
                    st.download_button(
                        label="📄 Exportar Resumen Ejecutivo (PDF)", data=pdf_bytes,
                        file_name=f"Resumen_Ejecutivo_{contrato_nom}_{fecha_gen}.pdf",
                        mime="application/pdf", use_container_width=True
                    )

                # --- Dimensionamiento de Columnas ---
                # Estatus: Utiliza autosize nativo de Glide Data Grid (width=None), ajustándose exactamente al texto sin espacio en blanco sobrante.
                # Prioridad 2: % Avance (Intocable, ancho garantizado para barra gráfica y etiqueta %.1f%%)
                w_avance_dyn = 125

                # Prioridad 3: Clave (Elástica, cede ante Prioridades 1 y 2 si compiten por espacio, tope 220px)
                max_len_c = df_dash["Clave"].astype(str).map(len).max() if not df_dash.empty else 5
                w_clave_dyn = max(130, min(int(max_len_c * 8.5) + 25, 220))

                # Prioridad 4: Fechas de corte (Elástica, menor jerarquía, cede primero ante las demás, rango 170-205px)
                max_len_p = df_dash["Periodo"].astype(str).map(len).max() if not df_dash.empty else 15
                w_periodo_dyn = max(170, min(int(max_len_p * 7.8) + 20, 205))

                st.dataframe(
                    df_dash,
                    column_config={
                        "Estimación": st.column_config.TextColumn("Estimación", width=115),
                        "Periodo": st.column_config.TextColumn("Fechas de Corte", width=w_periodo_dyn),
                        "Estado": st.column_config.TextColumn("Estado", width=95),
                        "#": st.column_config.NumberColumn("#", width=50),
                        "Clave": st.column_config.TextColumn("Clave", width=w_clave_dyn),
                        "Unidad": st.column_config.TextColumn("Unidad", width=65),
                        "Cant. Contratada": st.column_config.NumberColumn("Cant. Contratada", width=105),
                        "Cant. en Periodo": st.column_config.NumberColumn("Cant. en Periodo", width=105),
                        "Cant. Acumulada": st.column_config.NumberColumn("Cant. Acumulada", width=105),
                        "Saldo Físico": st.column_config.NumberColumn("Saldo Físico", width=95),
                        "P.U. ($)": st.column_config.NumberColumn("P.U. ($)", format="$%.2f", width=90),
                        "Importe Periodo ($)": st.column_config.NumberColumn("Importe Periodo ($)", format="$%.2f", width=125),
                        "Importe Acumulado ($)": st.column_config.NumberColumn("Importe Acumulado ($)", format="$%.2f", width=125),
                        "Saldo Financiero ($)": st.column_config.NumberColumn("Saldo Financiero ($)", format="$%.2f", width=125),
                        "% Avance": st.column_config.ProgressColumn("% Avance", min_value=0, max_value=100, format="%.1f%%", width=w_avance_dyn),
                        "Estatus": st.column_config.TextColumn("Estatus"),
                    },
                    use_container_width=True, hide_index=True
                )

# -------------------------------------------------------------
# TAB 2: CAPTURA EN CAMPO
# -------------------------------------------------------------
with tab_captura:
    st.subheader("Captura de Mediciones y Evidencia")
    if not proyectos_dict: st.warning("Configura tu proyecto primero.")
    else:
        proy_sel_cap = st.selectbox("Proyecto", list(proyectos_dict.keys()), key="cap_proy")
        id_proy_cap = proyectos_dict[proy_sel_cap]
        lista_est_cap = get_estimaciones(id_proy_cap)
        estimaciones_dict = {f"Estimación #{e['num_periodo']} ({e['estado']})": e["id"] for e in lista_est_cap} if lista_est_cap else {}
        lista_conc_cap = get_conceptos(id_proy_cap)
        conceptos_dict = {}
        if lista_conc_cap:
            for c in lista_conc_cap:
                clave_c, desc_c, u_norm = c["clave"], c["descripcion"], normalizar_unidad(c["unidad"])
                desc_limpia = desc_c[len(clave_c):].lstrip(" .:-") if desc_c.lower().startswith(clave_c.lower()) else desc_c
                conceptos_dict[f"{clave_c} — {desc_limpia[:55]}... ({u_norm})"] = c

        if not estimaciones_dict: st.error("No hay periodos de estimación abiertos para este proyecto.")
        elif not conceptos_dict: st.error("No hay conceptos en el catálogo de este proyecto.")
        else:
            c_est, c_con = st.columns([1, 2])
            est_sel = c_est.selectbox("Periodo Activo", list(estimaciones_dict.keys()))
            conc_sel = c_con.selectbox("Concepto a Cuantificar", list(conceptos_dict.keys()))
            id_est = estimaciones_dict[est_sel]
            obj_conc = conceptos_dict[conc_sel]
            id_conc, u_base, pu_conc = obj_conc["id"], normalizar_unidad(obj_conc["unidad"]), float(obj_conc.get("precio_unitario") or 0.0)

            if "last_unidad_cap" not in st.session_state: st.session_state.last_unidad_cap = u_base
            if st.session_state.last_unidad_cap != u_base:
                st.session_state.last_unidad_cap = u_base
                st.session_state.dim_counter += 1
                st.rerun()

            st.markdown("---")
            st.markdown(f"**Concepto:** `{obj_conc['clave']}` | **Unidad:** `{u_base}` | **P.U. Contratado:** `${pu_conc:,.2f}`")
            
            c_ver = st.session_state.cap_counter
            d_ver = f"{st.session_state.cap_counter}_{st.session_state.dim_counter}"

            col_loc1, col_loc2, col_loc3 = st.columns(3)
            localizacion = col_loc1.text_input("Localización / Elemento *", placeholder="Ej: VESTIDORES - MURO FONDO...", key=f"input_loc_{c_ver}")
            eje = col_loc2.text_input("Eje", placeholder="Ej: 2, A-B...", key=f"input_eje_{c_ver}")
            tramo = col_loc3.text_input("Tramo", placeholder="Ej: 1-2, EJE C...", key=f"input_tramo_{c_ver}")

            es_m3, es_m2, es_kg, es_lt = (u_base=="m³"), (u_base=="m²"), (u_base=="kg"), (u_base=="litros")
            es_h, es_m3km, es_lin = (u_base=="mano de obra (h)"), (u_base=="m³/km"), (u_base in ["m", "tramo"])
            
            tipo_geom = "Rectangular / Cuadrada"
            if es_m2: tipo_geom = st.selectbox("Tipo de Geometría:", ["Rectangular / Cuadrada", "Triangular", "Trapecio Regular"], key=f"geom_sel_{d_ver}")

            if es_m2:
                if tipo_geom == "Triangular": label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto = "Base (m)", "Altura (m)", "Alto (m)", False, False, True
                elif tipo_geom == "Trapecio Regular": label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto = "Base Mayor - B (m)", "Base Menor - b (m)", "Altura - h (m)", False, False, False
                else: label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto = "Largo (m)", "Ancho / Altura (m)", "Alto (m)", False, False, True
                des_kg, des_litros, des_horas = True, True, True
            elif es_m3km:
                label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = "Distancia (km)", "Volumen (m³)", "Alto (m)", False, False, True, True, True, True
            elif es_m3: label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = "Largo (m)", "Ancho (m)", "Alto (m)", False, False, False, True, True, True
            elif es_kg: label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = "Largo (m)", "Ancho (m)", "Alto (m)", False, True, True, False, True, True
            elif es_lt: label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = "Largo (m)", "Ancho (m)", "Alto (m)", True, True, True, True, False, True
            elif es_h: label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = "Largo (m)", "Ancho (m)", "Alto (m)", True, True, True, True, True, False
            elif es_lin: label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = "Largo (m)", "Ancho (m)", "Alto (m)", False, True, True, True, True, True
            else: label_largo, label_ancho, label_alto, des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = "Largo (m)", "Ancho (m)", "Alto (m)", True, True, True, True, True, True

            col_d1, col_d2, col_d3, col_d4, col_d5, col_d6, col_d7 = st.columns(7)
            largo = col_d1.number_input(label_largo, min_value=0.0, value=0.0, step=0.5, key=f"nl_{d_ver}", disabled=des_largo)
            ancho = col_d2.number_input(label_ancho, min_value=0.0, value=0.0, step=0.5, key=f"nan_{d_ver}", disabled=des_ancho)
            alto = col_d3.number_input(label_alto, min_value=0.0, value=0.0, step=0.5, key=f"nal_{d_ver}", disabled=des_alto)
            kilos = col_d4.number_input("Kilos (kg)", min_value=0.0, value=0.0, step=0.5, key=f"nkg_{d_ver}", disabled=des_kg)
            litros = col_d5.number_input("Litros", min_value=0.0, value=0.0, step=0.5, key=f"nlt_{d_ver}", disabled=des_litros)
            horas = col_d6.number_input("Horas (h)", min_value=0.0, value=0.0, step=0.5, key=f"nhr_{d_ver}", disabled=des_horas)
            piezas = col_d7.number_input("Piezas", min_value=1.0, value=1.0, step=1.0, key=f"npz_{d_ver}")

            v_l, v_an, v_al = (0.0 if des_largo else float(largo)), (0.0 if des_ancho else float(ancho)), (0.0 if des_alto else float(alto))
            v_kg, v_lt, v_h = (0.0 if des_kg else float(kilos)), (0.0 if des_litros else float(litros)), (0.0 if des_horas else float(horas))

            if es_m2:
                if tipo_geom == "Triangular": calc_preview = (v_l * v_an / 2.0) * piezas
                elif tipo_geom == "Trapecio Regular": calc_preview = ((v_l + v_an) / 2.0) * v_al * piezas
                else: calc_preview = (v_l * v_an * piezas) if (v_l > 0 and v_an > 0) else 0.0
            elif es_m3km: calc_preview = v_l * v_an * piezas
            elif es_m3: calc_preview = v_l * v_an * v_al * piezas
            elif es_kg: calc_preview = (v_l * v_kg * piezas) if v_l > 0 else (v_kg * piezas)
            elif es_lt: calc_preview = v_lt * piezas
            elif es_h: calc_preview = v_h * piezas
            elif es_lin: calc_preview = v_l * piezas
            else: calc_preview = piezas

            calc_preview = round(float(calc_preview), 3)
            importe_preview = round(calc_preview * pu_conc, 2)
            st.info(f"📐 Cantidad Calculada: **{calc_preview:.3f} {u_base}** | Importe Estimado: **${importe_preview:,.2f} MXN**")

            col_f1, col_f2 = st.columns(2)
            foto = col_f1.file_uploader("Fotografía de Evidencia", type=["jpg", "jpeg", "png"], key=f"file_foto_{c_ver}")
            croquis = col_f2.file_uploader("Croquis / Plano", type=["jpg", "jpeg", "png"], key=f"file_croquis_{c_ver}")

            if st.button("💾 Guardar Medición en Generador", type="primary"):
                if calc_preview <= 0: st.warning("La cantidad debe ser mayor a 0.")
                elif not localizacion.strip(): st.warning("Debes indicar la Localización / Elemento.")
                else:
                    url_foto, url_croquis = None, None
                    if foto:
                        contenido_f, mime_f = optimizar_imagen(foto)
                        fname_f = f"{uuid.uuid4()}.jpg"
                        supabase.storage.from_("evidencias").upload(fname_f, contenido_f, {"content-type": mime_f})
                        url_foto = supabase.storage.from_("evidencias").get_public_url(fname_f)
                    if croquis:
                        contenido_c, mime_c = optimizar_imagen(croquis)
                        fname_c = f"{uuid.uuid4()}.jpg"
                        supabase.storage.from_("evidencias").upload(fname_c, contenido_c, {"content-type": mime_c})
                        url_croquis = supabase.storage.from_("evidencias").get_public_url(fname_c)

                    if es_kg: v_an = v_kg
                    elif es_lt: v_l = v_lt
                    elif es_h: v_l = v_h

                    supabase.table("mediciones_campo").insert({
                        "id_estimacion": id_est, "id_concepto": id_conc, "localizacion": localizacion.strip(),
                        "eje": eje.strip(), "tramo": tramo.strip(), "largo": v_l, "ancho": v_an, "alto": v_al,
                        "piezas": float(piezas), "cantidad_total": calc_preview, "url_foto": url_foto, "url_croquis": url_croquis
                    }).execute()
                    get_mediciones.clear()
                    st.session_state.cap_counter += 1
                    st.session_state.dim_counter += 1
                    st.success("✅ Medición guardada.")
                    st.rerun()

            st.markdown("### Mediciones registradas en este periodo:")
            st.caption("💡 *Haz doble clic sobre cualquier celda permitida para editar directamente su valor.*")
            mediciones_periodo = get_mediciones(id_est)

            if mediciones_periodo:
                rows, meds_borrar_dict, total_periodo_acum = [], {}, 0.0
                for idx, m in enumerate(mediciones_periodo, start=1):
                    clave_c, u_c, pu_c = m["catalogo_conceptos"]["clave"], normalizar_unidad(m["catalogo_conceptos"]["unidad"]), float(m["catalogo_conceptos"].get("precio_unitario") or 0.0)
                    cant_m = float(m["cantidad_total"] or 0.0)
                    imp_m = round(cant_m * pu_c, 2)
                    total_periodo_acum += imp_m
                    rows.append({
                        "#": idx, "id": m["id"], "Clave": clave_c, "Localización": m["localizacion"] or "",
                        "Eje": m["eje"] or "", "Tramo": m["tramo"] or "", "Largo / Factor": float(m["largo"] or 0.0),
                        "Ancho / Kilos": float(m["ancho"] or 0.0), "Alto": float(m["alto"] or 0.0), "Pzas": float(m["piezas"] or 1.0),
                        "Cantidad": cant_m, "Unidad": u_c, "P.U. ($)": pu_c, "Importe ($)": imp_m,
                        "Tiene Foto": "Sí" if m["url_foto"] else "No", "Tiene Croquis": "Sí" if m["url_croquis"] else "No"
                    })
                    meds_borrar_dict[f"#{idx} — {clave_c} ({m['localizacion']} — {cant_m} {u_c})"] = m

                df_meds = pd.DataFrame(rows)
                ed_med_key = f"editor_mediciones_{id_est}_{st.session_state.get('ed_med_counter', 0)}"
                edited_meds = st.data_editor(
                    df_meds.drop(columns=["id"]),
                    column_config={
                        "#": st.column_config.NumberColumn("#", disabled=True), "Clave": st.column_config.TextColumn("Clave", disabled=True),
                        "Cantidad": st.column_config.NumberColumn("Cantidad", disabled=True), "Unidad": st.column_config.TextColumn("Unidad", disabled=True),
                        "P.U. ($)": st.column_config.NumberColumn("P.U. ($)", format="$%.2f", disabled=True), "Importe ($)": st.column_config.NumberColumn("Importe ($)", format="$%.2f", disabled=True),
                        "Tiene Foto": st.column_config.TextColumn("Foto", disabled=True), "Tiene Croquis": st.column_config.TextColumn("Croquis", disabled=True),
                    },
                    use_container_width=True, hide_index=True, key=ed_med_key
                )

                if ed_med_key in st.session_state and st.session_state[ed_med_key].get("edited_rows", {}):
                    error_med_msg = None
                    cambios_med_guardados = 0

                    for row_str, col_vals in list(st.session_state[ed_med_key]["edited_rows"].items()):
                        try:
                            r_idx = int(row_str)
                        except ValueError:
                            continue
                        if r_idx >= len(rows):
                            continue

                        up_payload = {}
                        id_med_up = rows[r_idx]["id"]

                        for k in ["Localización", "Eje", "Tramo"]:
                            if k in col_vals:
                                up_payload[k.lower()] = str(col_vals[k] or "").strip()

                        for k in ["Largo / Factor", "Ancho / Kilos", "Alto", "Pzas"]:
                            if k in col_vals: 
                                val_k = col_vals[k]
                                try:
                                    val_fl = float(val_k) if val_k is not None and str(val_k).strip() not in ("", "None", "nan") else float(rows[r_idx][k])
                                except (ValueError, TypeError):
                                    val_fl = float(rows[r_idx][k])

                                if k == "Largo / Factor": up_payload["largo"] = val_fl
                                elif k == "Ancho / Kilos": up_payload["ancho"] = val_fl
                                elif k == "Pzas": up_payload["piezas"] = val_fl
                                else: up_payload["alto"] = val_fl

                        if any(k in col_vals for k in ["Largo / Factor", "Ancho / Kilos", "Alto", "Pzas"]):
                            def _safe_float(k_name):
                                v = col_vals.get(k_name)
                                if v is None or str(v).strip() in ("", "None", "nan"):
                                    return float(rows[r_idx][k_name])
                                try:
                                    return float(v)
                                except (ValueError, TypeError):
                                    return float(rows[r_idx][k_name])

                            l_val = _safe_float("Largo / Factor")
                            an_val = _safe_float("Ancho / Kilos")
                            al_val = _safe_float("Alto")
                            pz_val = _safe_float("Pzas")
                            u_item = rows[r_idx]["Unidad"]
                            
                            if u_item == "m³": c_calc = l_val * an_val * al_val * pz_val
                            elif u_item == "m²": c_calc = (l_val * an_val * pz_val) if (l_val > 0 and an_val > 0) else 0.0
                            elif u_item == "m³/km": c_calc = l_val * an_val * pz_val
                            elif u_item == "kg": c_calc = (l_val * an_val * pz_val) if l_val > 0 else (an_val * pz_val)
                            elif u_item in ["m", "tramo", "litros", "mano de obra (h)"]: c_calc = l_val * pz_val
                            else: c_calc = pz_val
                            up_payload["cantidad_total"] = round(c_calc, 3)

                        if up_payload:
                            try:
                                supabase.table("mediciones_campo").update(up_payload).eq("id", id_med_up).execute()
                                cambios_med_guardados += 1
                            except Exception as e:
                                error_med_msg = f"⚠️ Error al actualizar medición: {e}"
                                break

                    if error_med_msg:
                        st.toast(error_med_msg, icon="⚠️")
                        st.session_state["ed_med_counter"] = st.session_state.get("ed_med_counter", 0) + 1
                        st.session_state.pop(ed_med_key, None)
                        st.rerun()
                    elif cambios_med_guardados > 0:
                        get_mediciones.clear()
                        st.toast("✅ Medición actualizada.")
                        st.session_state["ed_med_counter"] = st.session_state.get("ed_med_counter", 0) + 1
                        st.session_state.pop(ed_med_key, None)
                        st.rerun()

                st.metric("Total Estimado en el Periodo (Sin I.V.A.)", f"${total_periodo_acum:,.2f} MXN")

                with st.expander("🗑 Eliminar Mediciones (Borrado Masivo)"):
                    meds_a_borrar_labels = st.multiselect("Seleccionar mediciones a remover:", list(meds_borrar_dict.keys()), key=f"sel_med_del_{st.session_state.del_med_counter}")
                    borrar_todas_meds = st.checkbox("⚠️ Selecciona para eliminar todas las mediciones mostradas en la tabla.", key=f"chk_todas_meds_{st.session_state.del_med_counter}")
                    if borrar_todas_meds: meds_a_borrar_labels = list(meds_borrar_dict.keys())

                    if st.button("Eliminar Seleccionadas", type="primary", disabled=len(meds_a_borrar_labels)==0, key=f"btn_del_meds_bulk_{st.session_state.del_med_counter}"):
                        ids_to_delete, archivos_a_borrar = [], []
                        for label in meds_a_borrar_labels:
                            obj_med_borrar = meds_borrar_dict[label]
                            ids_to_delete.append(obj_med_borrar["id"])
                            if obj_med_borrar.get("url_foto"):
                                nom_f = extraer_nombre_archivo(obj_med_borrar["url_foto"])
                                if nom_f: archivos_a_borrar.append(nom_f)
                            if obj_med_borrar.get("url_croquis"):
                                nom_c = extraer_nombre_archivo(obj_med_borrar["url_croquis"])
                                if nom_c: archivos_a_borrar.append(nom_c)

                        if archivos_a_borrar:
                            for chunk in [archivos_a_borrar[i:i+50] for i in range(0, len(archivos_a_borrar), 50)]:
                                try: supabase.storage.from_("evidencias").remove(chunk)
                                except: pass
                        if ids_to_delete:
                            for chunk in [ids_to_delete[i:i+50] for i in range(0, len(ids_to_delete), 50)]:
                                supabase.table("mediciones_campo").delete().in_("id", chunk).execute()
                        get_mediciones.clear()
                        st.session_state.del_med_counter += 1
                        st.success(f"{len(ids_to_delete)} mediciones eliminadas.")
                        st.rerun()

# -------------------------------------------------------------
# TAB 3: ESTIMACIONES
# -------------------------------------------------------------
with tab_estimaciones:
    st.subheader("Periodos de Estimación")
    if not proyectos_dict: st.warning("Registra un proyecto primero.")
    else:
        proy_sel_est = st.selectbox("Seleccionar Proyecto", list(proyectos_dict.keys()), key="est_proy")
        id_proy_est = proyectos_dict[proy_sel_est]

        estimaciones_proyecto = get_estimaciones(id_proy_est)
        periodos_existentes = {int(e["num_periodo"]) for e in estimaciones_proyecto if e.get("num_periodo") is not None} if estimaciones_proyecto else set()
        siguiente_num_periodo = (max(periodos_existentes) + 1) if periodos_existentes else 1

        col_est_nueva, col_est_baja = st.columns(2)
        with col_est_nueva:
            with st.expander("➕ Aperturar nueva estimación"):
                with st.form("form_nueva_estimacion", clear_on_submit=True):
                    col_e1, col_e2, col_e3 = st.columns(3)
                    num_periodo = col_e1.number_input(
                        "N° Estimación", min_value=1, step=1, value=siguiente_num_periodo,
                        key=f"num_est_input_{id_proy_est}_{st.session_state.get('ed_est_counter', 0)}"
                    )
                    f_ini = col_e2.date_input("Fecha Inicio")
                    f_fin = col_e3.date_input("Fecha Fin")
                    if st.form_submit_button("Abrir Periodo"):
                        if int(num_periodo) in periodos_existentes:
                            st.error(f"⚠️ La estimación #{int(num_periodo)} ya existe en este proyecto.")
                        elif f_fin < f_ini:
                            st.error("⚠️ La fecha de fin no puede ser anterior a la fecha de inicio.")
                        else:
                            try:
                                supabase.table("estimaciones").insert({
                                    "id_proyecto": id_proy_est, "num_periodo": int(num_periodo),
                                    "periodo_inicio": str(f_ini), "periodo_fin": str(f_fin), "estado": "borrador"
                                }).execute()
                                get_estimaciones.clear()
                                st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                                st.success(f"Estimación #{num_periodo} aperturada.")
                                st.rerun()
                            except Exception as e: st.error(f"Error al aperturar: {e}")

        dict_est_borrar = {f"#{idx} — Estimación #{e['num_periodo']} ({e['periodo_inicio']} al {e['periodo_fin']})": e["id"] for idx, e in enumerate(estimaciones_proyecto, start=1)} if estimaciones_proyecto else {}

        with col_est_baja:
            with st.expander("🗑️ Eliminar Estimación"):
                if not dict_est_borrar: st.info("No hay estimaciones registradas.")
                else:
                    est_del_sel = st.selectbox("Seleccionar estimación:", list(dict_est_borrar.keys()), key=f"del_est_sel_{st.session_state.del_est_counter}")
                    st.warning("⚠️ Al eliminar la estimación también se borrarán todas sus mediciones.")
                    if st.button("Eliminar Estimación", type="primary", disabled=not st.checkbox("Confirmo eliminar esta estimación", key=f"chk_del_est_{st.session_state.del_est_counter}")):
                        supabase.table("estimaciones").delete().eq("id", dict_est_borrar[est_del_sel]).execute()
                        get_estimaciones.clear()
                        get_mediciones.clear()
                        st.session_state.del_est_counter += 1
                        st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                        st.success("Estimación eliminada.")
                        st.rerun()

        if estimaciones_proyecto:
            st.markdown("##### Listado de Estimaciones:")
            st.caption("💡 *Haz doble clic en cualquier celda para cambiar de estado o corregir las fechas de corte.*")

            if "est_error_banner" in st.session_state and st.session_state["est_error_banner"]:
                st.error(st.session_state.pop("est_error_banner"))

            df_e = pd.DataFrame(estimaciones_proyecto)
            df_e.insert(0, "#", range(1, len(df_e) + 1))
            df_editor_data = df_e[["#", "num_periodo", "periodo_inicio", "periodo_fin", "estado"]].copy()
            df_editor_data["periodo_inicio"] = pd.to_datetime(df_editor_data["periodo_inicio"], errors="coerce").dt.date
            df_editor_data["periodo_fin"] = pd.to_datetime(df_editor_data["periodo_fin"], errors="coerce").dt.date

            ed_est_key = f"editor_estimaciones_{id_proy_est}_{st.session_state.get('ed_est_counter', 0)}"

            edited_table = st.data_editor(
                df_editor_data,
                column_config={
                    "#": st.column_config.NumberColumn("#", disabled=True),
                    "num_periodo": st.column_config.NumberColumn("N° Periodo", disabled=True),
                    "periodo_inicio": st.column_config.DateColumn("Fecha Inicio", format="YYYY-MM-DD", required=True),
                    "periodo_fin": st.column_config.DateColumn("Fecha Fin", format="YYYY-MM-DD", required=True),
                    "estado": st.column_config.SelectboxColumn("Estado de la Estimación", width="medium", options=["borrador", "en_revision", "aprobada"], required=True),
                },
                hide_index=True, use_container_width=True, key=ed_est_key
            )

            if ed_est_key in st.session_state and st.session_state[ed_est_key].get("edited_rows", {}):
                error_msg = None
                cambios_guardados = 0

                for row_idx_str, col_mod in list(st.session_state[ed_est_key]["edited_rows"].items()):
                    try:
                        r_idx = int(row_idx_str)
                    except ValueError:
                        continue
                    if r_idx >= len(estimaciones_proyecto):
                        continue

                    est_actual = estimaciones_proyecto[r_idx]
                    id_est_mod = est_actual["id"]
                    up_est = {}

                    if "estado" in col_mod:
                        val_est = str(col_mod["estado"]).strip() if col_mod["estado"] else ""
                        if val_est in ["borrador", "en_revision", "aprobada"]:
                            up_est["estado"] = val_est
                        else:
                            error_msg = "⚠️ El estado seleccionado no es válido."

                    for col_f in ["periodo_inicio", "periodo_fin"]:
                        if col_f in col_mod:
                            val_raw = col_mod[col_f]
                            if val_raw is None or pd.isna(val_raw) or str(val_raw).strip() in ("", "None", "nan", "NaT"):
                                error_msg = "⚠️ La fecha de inicio y la fecha de fin son obligatorias y no pueden quedar vacías."
                            else:
                                try:
                                    d_parsed = pd.to_datetime(str(val_raw).strip()).date()
                                    up_est[col_f] = d_parsed.strftime("%Y-%m-%d")
                                except Exception:
                                    error_msg = "⚠️ El formato de fecha no es válido (use AAAA-MM-DD)."

                    if not error_msg:
                        f_ini_check = up_est.get("periodo_inicio", est_actual.get("periodo_inicio"))
                        f_fin_check = up_est.get("periodo_fin", est_actual.get("periodo_fin"))
                        if f_ini_check and f_fin_check and str(f_fin_check) < str(f_ini_check):
                            error_msg = "⚠️ La fecha de fin no puede ser anterior a la fecha de inicio."

                    if error_msg:
                        break

                    if up_est:
                        try:
                            supabase.table("estimaciones").update(up_est).eq("id", id_est_mod).execute()
                            cambios_guardados += 1
                        except Exception as e:
                            error_msg = f"⚠️ Error al actualizar la estimación: {e}"
                            break

                if error_msg:
                    st.session_state["est_error_banner"] = error_msg
                    st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                    st.session_state.pop(ed_est_key, None)
                    st.rerun()
                elif cambios_guardados > 0:
                    get_estimaciones.clear()
                    st.toast("✅ Estimación actualizada.")
                    st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                    st.session_state.pop(ed_est_key, None)
                    st.rerun()

            st.markdown("---")
            st.markdown("##### 📥 Exportación Oficial (Formatos Institucionales y Libre)")
            col_exp_1, col_exp_2, col_exp_3 = st.columns([2, 1, 1])
            
            est_a_descargar = col_exp_1.selectbox("Estimación a Exportar:", [f"Estimación #{e['num_periodo']} (Del {e['periodo_inicio']} al {e['periodo_fin']})" for e in estimaciones_proyecto])
            formato_institucion = col_exp_2.selectbox("Formato de Salida:", ["IMSS", "Poder Judicial de la Federación", "Formato Estimapp"])
            proy_obj_actual = next((p for p in lista_proyectos if p["id"] == id_proy_est), {})
            
            with col_exp_3:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                btn_generar_excel = st.button("Preparar estimación en formato Excel", type="primary", use_container_width=True)

            if btn_generar_excel:
                idx_est_sel = [f"Estimación #{e['num_periodo']} (Del {e['periodo_inicio']} al {e['periodo_fin']})" for e in estimaciones_proyecto].index(est_a_descargar)
                est_obj_actual = estimaciones_proyecto[idx_est_sel]
                conceptos_cat = get_conceptos(id_proy_est)
                
                with st.spinner("Generando archivo..."):
                    try:
                        if formato_institucion == "IMSS":
                            plantilla_bytes = descargar_plantilla_supabase("plantillas", "plantilla_maestra_estimacion_imss.xlsx")
                            xlsx_generado = inyectar_datos_excel_imss(plantilla_bytes, proy_obj_actual, est_obj_actual, conceptos_cat, estimaciones_proyecto)
                            st.session_state["xls_name"] = f"Estimacion_{est_obj_actual['num_periodo']}_IMSS.xlsx"
                        elif formato_institucion == "Poder Judicial de la Federación":
                            plantilla_bytes = descargar_plantilla_supabase("plantillas", "plantilla_maestra_estimacion_pjf.xlsx")
                            xlsx_generado = inyectar_datos_excel_pjf(plantilla_bytes, proy_obj_actual, est_obj_actual, conceptos_cat, estimaciones_proyecto)
                            st.session_state["xls_name"] = f"Estimacion_{est_obj_actual['num_periodo']}_PJF.xlsx"
                        else:
                            xlsx_generado = generar_excel_estimapp(proy_obj_actual, est_obj_actual, conceptos_cat, estimaciones_proyecto)
                            st.session_state["xls_name"] = f"Estimacion_{est_obj_actual['num_periodo']}_Estimapp.xlsx"

                        st.session_state["xls_buffer"] = xlsx_generado
                    except Exception as e:
                        st.error(f"Error: {e}")

            def _on_descarga_excel_completada():
                st.session_state.pop("xls_buffer", None)
                st.session_state.pop("xls_name", None)

            if st.session_state.get("xls_buffer"):
                st.success("✅ Archivo listo para descarga.")
                btn_descarga = st.download_button(
                    "⬇️ Descargar Archivo",
                    data=st.session_state["xls_buffer"],
                    file_name=st.session_state.get("xls_name", "Estimacion.xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    on_click=_on_descarga_excel_completada,
                    key="btn_descarga_excel_estimacion"
                )
                if btn_descarga:
                    _on_descarga_excel_completada()
                    st.rerun()
            else:
                # Espacio visual reservado para evitar que el borde de la página quede pegado y permitir ver de antemano el área de descarga
                st.markdown("<div style='height: 120px; margin-top: 14px;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# TAB 4: CATÁLOGO DEL PROYECTO
# -------------------------------------------------------------
with tab_catalogo:
    st.subheader("Catálogo del Proyecto (Contrato de Obra)")
    if not proyectos_dict: st.warning("Primero debes registrar un proyecto.")
    else:
        proy_sel = st.selectbox("Seleccionar Proyecto Destino", list(proyectos_dict.keys()), key="cat_proy_2")
        proy_id = proyectos_dict[proy_sel]

        categorias_disp = get_biblioteca_instituciones(user_id)
        cat_sel = st.selectbox("Institución/catálogo maestro (Para importar):", categorias_disp, key="sel_cat_bib_2")
        conceptos_bib = get_biblioteca_conceptos(cat_sel, user_id)

        col_import1, col_import2 = st.columns(2)

        with col_import1:
            with st.expander("📦 Importación Lote desde Biblioteca"):
                if not conceptos_bib: st.info(f"No hay conceptos en '{cat_sel}'.")
                else:
                    opciones_lote = {f"{c['clave']} — {c['descripcion'][:60]}...": c for c in conceptos_bib}
                    seleccionados_lote = st.multiselect("Seleccionar conceptos:", list(opciones_lote.keys()), key=f"ms_lote_{st.session_state.ms_lote_key}")
                    if st.button("📥 Importar Seleccionados", type="primary") and seleccionados_lote:
                        registros_a_insertar = []
                        for sel in seleccionados_lote:
                            c_ref = opciones_lote[sel]
                            registros_a_insertar.append({
                                "id_proyecto": proy_id, 
                                "especialidad": c_ref.get("especialidad", ""),
                                "categoria": c_ref.get("categoria", ""),
                                "clave": c_ref["clave"], "descripcion": c_ref["descripcion"], 
                                "unidad": normalizar_unidad(c_ref["unidad"]),
                                "cantidad_contratada": 0.0, "precio_unitario": float(c_ref.get("precio_referencial") or 0.0)
                            })
                        if registros_a_insertar:
                            for chunk in [registros_a_insertar[i:i+50] for i in range(0, len(registros_a_insertar), 50)]:
                                supabase.table("catalogo_conceptos").insert(chunk).execute()
                            get_conceptos.clear()
                            st.session_state.ms_lote_key += 1
                            st.success(f"✅ {len(registros_a_insertar)} conceptos importados.")
                            st.rerun()

            with st.expander("📄 Importar Concepto Único desde Biblioteca"):
                if conceptos_bib:
                    opciones_unico = {f"{c['clave']} — {c['descripcion'][:55]}...": c for c in conceptos_bib}
                    obj_u = opciones_unico[st.selectbox("Concepto maestro:", list(opciones_unico.keys()), key="sel_unico")]
                    with st.form("form_importar_bib", clear_on_submit=True):
                        c_cu1, c_cu2 = st.columns(2)
                        cant_u = c_cu1.number_input("Cantidad Contratada", min_value=0.001, value=1.0, step=1.0)
                        pu_u = c_cu2.number_input("Precio Unitario ($)", min_value=0.0, value=float(obj_u.get("precio_referencial") or 0.0), step=10.0)
                        if st.form_submit_button("➕ Agregar al Contrato"):
                            supabase.table("catalogo_conceptos").insert({
                                "id_proyecto": proy_id, "especialidad": obj_u.get("especialidad"),
                                "categoria": obj_u.get("categoria"), "clave": obj_u["clave"], 
                                "descripcion": obj_u["descripcion"], "unidad": normalizar_unidad(obj_u["unidad"]),
                                "cantidad_contratada": cant_u, "precio_unitario": pu_u
                            }).execute()
                            get_conceptos.clear()
                            st.success("Concepto agregado.")
                            st.rerun()

        with col_import2:
            with st.expander("📂 Subir desde Excel (Carga Masiva al Contrato)"):
                st.download_button("📥 Descargar Plantilla Oficial Excel", data=generar_plantilla_excel("proyecto"), file_name=f"Plantilla_Cat_Proyecto_{ts_descarga}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                excel_proy = st.file_uploader("Sube plantilla llena:", type=["xlsx"], key=f"up_proy_{st.session_state.up_proy_key}")
                if excel_proy and st.button("Subir e Insertar al Proyecto", type="primary"):
                    try:
                        df_up = pd.read_excel(excel_proy)
                        ok, error_msg, records = procesar_excel_importacion(df_up, tipo="proyecto")
                        if not ok:
                            st.error(f"⚠️ {error_msg}")
                        elif not records:
                            st.warning("⚠️ No se encontraron filas con datos válidos (clave y descripción requeridas).")
                        else:
                            for r in records:
                                r["id_proyecto"] = proy_id
                            for chunk in [records[i:i+50] for i in range(0, len(records), 50)]:
                                supabase.table("catalogo_conceptos").insert(chunk).execute()
                            get_conceptos.clear()
                            st.session_state.up_proy_key += 1
                            st.success(f"✅ {len(records)} conceptos cargados exitosamente.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error procesando el archivo: {e}")

            with st.expander("➕ Alta manual (Concepto Extraordinario)"):
                with st.form("form_concepto_manual", clear_on_submit=True):
                    esp_m = st.text_input("Especialidad (Opcional)", placeholder="Ej: 01 PRELIMINARES")
                    cat_m = st.text_input("Categoría / Partida (Opcional)", placeholder="Ej: 1.1")
                    clave_m = st.text_input("Clave de Concepto *", placeholder="Ej: OC01-015-126")
                    unidad_m = st.selectbox("Unidad", unidades_list)
                    desc_m = st.text_area("Descripción detallada *", placeholder="Ingrese la descripción completa...")
                    c_cant_m, c_pu_m = st.columns(2)
                    cant_m = c_cant_m.number_input("Cantidad Contratada", min_value=0.001, value=1.0, step=1.0)
                    pu_m = c_pu_m.number_input("Precio Unitario ($)", min_value=0.0, value=0.0, step=10.0)
                    
                    if st.form_submit_button("Guardar en Catálogo"):
                        if not clave_m.strip() or not desc_m.strip(): st.error("Clave y descripción obligatorias.")
                        else:
                            supabase.table("catalogo_conceptos").insert({
                                "id_proyecto": proy_id, "especialidad": esp_m.strip(), "categoria": cat_m.strip(),
                                "clave": clave_m.strip(), "descripcion": desc_m.strip(), "unidad": normalizar_unidad(unidad_m), 
                                "cantidad_contratada": cant_m, "precio_unitario": pu_m
                            }).execute()
                            get_conceptos.clear()
                            st.success("✅ Guardado exitosamente.")
                            st.rerun()

        conceptos_proyecto = get_conceptos(proy_id)
        dict_conc_borrar = {f"#{idx} — {c['clave']} ({c['descripcion'][:45]}...)": c for idx, c in enumerate(conceptos_proyecto, start=1)} if conceptos_proyecto else {}

        with st.expander("🗑️ Eliminar Conceptos del Contrato (Borrado en Cascada)"):
            st.warning("Nota: Eliminar conceptos del catálogo borrará irreversiblemente las mediciones y avances físicos asociados a ellos en este proyecto para proteger la conciliación del Dashboard.")
            conc_a_borrar_labels = st.multiselect("Seleccionar conceptos:", list(dict_conc_borrar.keys()), key=f"del_conc_sel_{st.session_state.del_conc_counter}")
            borrar_todos_conc = st.checkbox("⚠️ Selecciona para eliminar todos los conceptos mostrados en la tabla.", key=f"chk_todos_conc_{st.session_state.del_conc_counter}")
            if borrar_todos_conc: conc_a_borrar_labels = list(dict_conc_borrar.keys())

            if st.button("Eliminar Seleccionados", type="primary", disabled=len(conc_a_borrar_labels)==0, key=f"btn_del_cat_bulk_{st.session_state.del_conc_counter}"):
                ids_to_delete = [dict_conc_borrar[label]["id"] for label in conc_a_borrar_labels]
                if ids_to_delete:
                    for chunk in [ids_to_delete[i:i+50] for i in range(0, len(ids_to_delete), 50)]:
                        supabase.table("mediciones_campo").delete().in_("id_concepto", chunk).execute()
                        supabase.table("catalogo_conceptos").delete().in_("id", chunk).execute()
                get_conceptos.clear()
                get_mediciones.clear()
                st.session_state.del_conc_counter += 1
                st.success(f"{len(ids_to_delete)} conceptos eliminados.")
                st.rerun()

        if conceptos_proyecto:
            st.markdown("##### Presupuesto Oficial del Proyecto (Editor Directo):")
            st.caption("💡 *Haz doble clic sobre cualquier celda (clave, descripción, unidad, cantidad o precio) para modificarla directamente.*")
            df_c = pd.DataFrame(conceptos_proyecto)
            df_c.insert(0, "#", range(1, len(df_c) + 1))
            
            # Limpieza y formateo seguro de valores
            df_c["clave"] = df_c["clave"].fillna("").astype(str)
            df_c["categoria"] = df_c["categoria"].fillna("").astype(str)
            df_c["especialidad"] = df_c["especialidad"].fillna("").astype(str)
            df_c["descripcion"] = df_c["descripcion"].fillna("").astype(str)
            df_c["cantidad_contratada"] = pd.to_numeric(df_c["cantidad_contratada"], errors="coerce").fillna(0.0).astype(float)
            df_c["precio_unitario"] = pd.to_numeric(df_c["precio_unitario"], errors="coerce").fillna(0.0).astype(float)
            
            ed_cat_key = f"editor_catalogo_{proy_id}_{st.session_state.get('ed_cat_counter', 0)}"

            edited_catalogo = st.data_editor(
                df_c[["#", "clave", "especialidad", "categoria", "unidad", "cantidad_contratada", "precio_unitario", "descripcion"]],
                column_config={
                    "#": st.column_config.NumberColumn("#", disabled=True),
                    "clave": st.column_config.TextColumn("Clave", required=True),
                    "especialidad": st.column_config.TextColumn("Especialidad"),
                    "categoria": st.column_config.TextColumn("Categoría"),
                    "unidad": st.column_config.SelectboxColumn("Unidad", options=unidades_list, required=True),
                    "cantidad_contratada": st.column_config.NumberColumn("Cant. Contratada", min_value=0.0, step=1.0, required=True),
                    "precio_unitario": st.column_config.NumberColumn("P.U. ($)", format="$%.2f", min_value=0.0, step=10.0, required=True),
                    "descripcion": st.column_config.TextColumn("Descripción")
                },
                use_container_width=True,
                hide_index=True,
                key=ed_cat_key
            )

            if ed_cat_key in st.session_state and st.session_state[ed_cat_key].get("edited_rows", {}):
                error_cat_msg = None
                cambios_cat_guardados = 0

                for row_str, col_vals in list(st.session_state[ed_cat_key]["edited_rows"].items()):
                    try:
                        r_idx = int(row_str)
                    except ValueError:
                        continue
                    if r_idx >= len(conceptos_proyecto):
                        continue

                    conc_actual = conceptos_proyecto[r_idx]
                    id_conc_mod = conc_actual["id"]
                    up_payload = {}

                    # 1. Clave obligatoria: no permitir vacíos ni None
                    if "clave" in col_vals:
                        val_clave = col_vals["clave"]
                        if val_clave is None or not str(val_clave).strip():
                            error_cat_msg = "⚠️ La clave del concepto es obligatoria y no puede quedar vacía."
                            break
                        up_payload["clave"] = str(val_clave).strip()

                    # 2. Textos opcionales
                    for campo in ["especialidad", "categoria", "descripcion"]:
                        if campo in col_vals:
                            up_payload[campo] = str(col_vals[campo] or "").strip()

                    # 3. Unidad obligatoria
                    if "unidad" in col_vals:
                        val_u = col_vals["unidad"]
                        if val_u:
                            up_payload["unidad"] = normalizar_unidad(val_u)
                        else:
                            error_cat_msg = "⚠️ La unidad del concepto es obligatoria."
                            break

                    # 4. Cantidad contratada: protección contra None/empty
                    if "cantidad_contratada" in col_vals:
                        val_c = col_vals["cantidad_contratada"]
                        if val_c is None or str(val_c).strip() in ("", "None", "nan"):
                            up_payload["cantidad_contratada"] = float(conc_actual.get("cantidad_contratada") or 0.0)
                        else:
                            try:
                                up_payload["cantidad_contratada"] = max(0.0, float(val_c))
                            except (ValueError, TypeError):
                                up_payload["cantidad_contratada"] = float(conc_actual.get("cantidad_contratada") or 0.0)

                    # 5. Precio unitario: protección contra None/empty
                    if "precio_unitario" in col_vals:
                        val_p = col_vals["precio_unitario"]
                        if val_p is None or str(val_p).strip() in ("", "None", "nan"):
                            up_payload["precio_unitario"] = float(conc_actual.get("precio_unitario") or 0.0)
                        else:
                            try:
                                up_payload["precio_unitario"] = max(0.0, float(val_p))
                            except (ValueError, TypeError):
                                up_payload["precio_unitario"] = float(conc_actual.get("precio_unitario") or 0.0)

                    if up_payload:
                        try:
                            supabase.table("catalogo_conceptos").update(up_payload).eq("id", id_conc_mod).execute()
                            cambios_cat_guardados += 1
                        except Exception as e:
                            error_cat_msg = f"⚠️ Error al actualizar el concepto: {e}"
                            break

                if error_cat_msg:
                    st.toast(error_cat_msg, icon="⚠️")
                    st.session_state["ed_cat_counter"] = st.session_state.get("ed_cat_counter", 0) + 1
                    st.session_state.pop(ed_cat_key, None)
                    st.rerun()
                elif cambios_cat_guardados > 0:
                    get_conceptos.clear()
                    st.toast("✅ Catálogo actualizado.")
                    st.session_state["ed_cat_counter"] = st.session_state.get("ed_cat_counter", 0) + 1
                    st.session_state.pop(ed_cat_key, None)
                    st.rerun()

# -------------------------------------------------------------
# TAB 5: BIBLIOTECA MAESTRA GLOBAL
# -------------------------------------------------------------
with tab_biblioteca:
    st.markdown("### 📖 Biblioteca Maestra de Conceptos (Global)")
    st.caption("Administra el tabulador institucional de precios y claves para usar en múltiples contratos.")
    
    cats_bib = get_biblioteca_instituciones(user_id)
    if "pending_cat_activa" in st.session_state:
        st.session_state["cat_activa"] = st.session_state.pop("pending_cat_activa")
    elif "cat_activa" not in st.session_state or st.session_state["cat_activa"] not in cats_bib:
        st.session_state["cat_activa"] = cats_bib[0] if cats_bib else "IMSS"
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        with st.container(border=True):
            st.markdown("**1. Selecciona o elimina una institución/catálogo maestro:**")
            c_bc1, c_bc2 = st.columns([3, 1])
            cat_bib_sel = c_bc1.selectbox("Institución:", cats_bib, key="cat_activa", label_visibility="collapsed")

            if c_bc2.button("Eliminar", type="primary", use_container_width=True):
                if cat_bib_sel:
                    supabase.table("instituciones").delete().eq("nombre", cat_bib_sel).execute()
                    supabase.table("biblioteca_conceptos").delete().eq("institucion", cat_bib_sel).execute()
                    get_biblioteca_instituciones.clear()
                    get_biblioteca_conceptos.clear()
                    st.session_state["pending_cat_activa"] = "IMSS"
                    st.rerun()

    with col_b2:
        with st.container(border=True):
            st.markdown("**2. Crea una institución/catálogo maestro:**")
            with st.form("form_crear_institucion", border=False):
                c_nc1, c_nc2 = st.columns([3, 1])
                nueva_inst = c_nc1.text_input("Nombre de institución:", label_visibility="collapsed", key=f"input_nueva_cat_{st.session_state.new_cat_key}", placeholder="Ej: ISSSTE, SEDENA...")
                btn_crear = c_nc2.form_submit_button("Crear", use_container_width=True)
                if btn_crear and nueva_inst.strip():
                    inst_limpia = nueva_inst.strip()
                    res_chk = supabase.table("instituciones").select("id").eq("nombre", inst_limpia).or_(f"user_id.eq.{user_id},user_id.is.null").execute()
                    if not res_chk.data:
                        supabase.table("instituciones").insert({
                            "nombre": inst_limpia,
                            "user_id": user_id
                        }).execute()
                    get_biblioteca_instituciones.clear()
                    st.session_state["pending_cat_activa"] = inst_limpia
                    st.session_state["msg_exito_cat"] = True
                    st.session_state.new_cat_key += 1
                    st.rerun()
            
            if st.session_state.get("msg_exito_cat"):
                st.success("✅ Institución creada exitosamente")
                st.session_state["msg_exito_cat"] = False

    col_bib_alta, col_bib_del = st.columns(2)
    with col_bib_alta:
        with st.expander("📂 Subir Biblioteca desde Excel (Carga Masiva)"):
            st.download_button("📥 Descargar Plantilla Excel de Biblioteca", data=generar_plantilla_excel("biblioteca"), file_name=f"Plantilla_Bib_Global_{ts_descarga}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            excel_bib = st.file_uploader("Sube plantilla llena:", type=["xlsx"], key=f"up_bib_{st.session_state.up_bib_key}")
            if excel_bib and st.button("Cargar a Biblioteca Global", type="primary"):
                try:
                    df_b = pd.read_excel(excel_bib)
                    ok, error_msg, records_b = procesar_excel_importacion(df_b, tipo="biblioteca")
                    if not ok:
                        st.error(f"⚠️ {error_msg}")
                    elif not records_b:
                        st.warning("⚠️ No se encontraron filas con datos válidos (clave y descripción requeridas).")
                    else:
                        for r in records_b:
                            r["user_id"] = user_id
                            r["institucion"] = cat_bib_sel
                        for chunk in [records_b[i:i+50] for i in range(0, len(records_b), 50)]:
                            supabase.table("biblioteca_conceptos").insert(chunk).execute()
                        get_biblioteca_conceptos.clear()
                        get_biblioteca_instituciones.clear()
                        st.session_state.up_bib_key += 1
                        st.success(f"✅ {len(records_b)} conceptos guardados en {cat_bib_sel}.")
                        st.rerun()
                except Exception as e: 
                    st.error(f"Error procesando el archivo: {e}")
        
        with st.expander("➕ Alta manual (Concepto Maestro)"):
            with st.form("form_alta_bib", clear_on_submit=True):
                esp_m = st.text_input("Especialidad (Opcional)", placeholder="Ej: 01 PRELIMINARES")
                cat_m = st.text_input("Categoría / Partida (Opcional)", placeholder="Ej: 1.1")
                clave_m = st.text_input("Clave de Concepto *", placeholder="Ej: OC01-015-126")
                unidad_m = st.selectbox("Unidad", unidades_list)
                desc_m = st.text_area("Descripción detallada *", placeholder="Ingrese la descripción completa...")
                pu_m = st.number_input("Precio Unitario ($)", min_value=0.0, value=0.0, step=10.0)
                if st.form_submit_button("Guardar en Biblioteca"):
                    if not clave_m.strip() or not desc_m.strip(): 
                        st.error("Clave y descripción son obligatorias.")
                    else:
                        supabase.table("biblioteca_conceptos").insert({
                            "user_id": user_id, 
                            "institucion": cat_bib_sel, 
                            "especialidad": esp_m.strip(), 
                            "categoria": cat_m.strip(),
                            "clave": clave_m.strip(), 
                            "descripcion": desc_m.strip(), 
                            "unidad": normalizar_unidad(unidad_m), 
                            "precio_referencial": pu_m
                        }).execute()
                        get_biblioteca_conceptos.clear()
                        get_biblioteca_instituciones.clear()
                        st.success("✅ Guardado exitosamente.")
                        st.rerun()

    lista_admin_bib = get_biblioteca_conceptos(cat_bib_sel, user_id)
    dict_del_bib = {f"#{idx} — {c['clave']} ({c['descripcion'][:50]}...)": c["id"] for idx, c in enumerate(lista_admin_bib, start=1)} if lista_admin_bib else {}

    with col_bib_del:
        with st.expander("🗑️ Eliminar Conceptos Maestros (Borrado Masivo)"):
            sel_del_bib_labels = st.multiselect("Seleccionar conceptos maestros:", list(dict_del_bib.keys()), key=f"del_bib_{st.session_state.bib_del_counter}")
            borrar_toda_cat = st.checkbox("⚠️ Selecciona para eliminar todos los conceptos mostrados en la tabla.", key=f"chk_toda_cat_{st.session_state.bib_del_counter}")
            if borrar_toda_cat: 
                sel_del_bib_labels = list(dict_del_bib.keys())

            if st.button("Eliminar Seleccionados", type="primary", disabled=len(sel_del_bib_labels)==0, key=f"btn_del_bib_bulk_{st.session_state.bib_del_counter}"):
                ids_to_delete = [dict_del_bib[label] for label in sel_del_bib_labels]
                if ids_to_delete:
                    for chunk in [ids_to_delete[i:i+50] for i in range(0, len(ids_to_delete), 50)]:
                        supabase.table("biblioteca_conceptos").delete().in_("id", chunk).execute()
                get_biblioteca_conceptos.clear()
                st.session_state.bib_del_counter += 1
                st.success(f"{len(ids_to_delete)} conceptos eliminados.")
                st.rerun()

    if lista_admin_bib:
        st.markdown(f"##### Conceptos en Institución: {cat_bib_sel} (Editor Directo):")
        st.caption("💡 *Haz doble clic sobre cualquier celda para modificar la base maestra.*")
        df_admin = pd.DataFrame(lista_admin_bib)
        df_admin.insert(0, "#", range(1, len(df_admin) + 1))
        
        df_admin["clave"] = df_admin["clave"].fillna("").astype(str)
        df_admin["categoria"] = df_admin["categoria"].fillna("").astype(str)
        df_admin["especialidad"] = df_admin["especialidad"].fillna("").astype(str)
        df_admin["descripcion"] = df_admin["descripcion"].fillna("").astype(str)
        df_admin["precio_referencial"] = pd.to_numeric(df_admin["precio_referencial"], errors="coerce").fillna(0.0).astype(float)
        
        ed_bib_key = f"editor_biblioteca_{cat_bib_sel}_{st.session_state.get('ed_bib_counter', 0)}"

        edited_bib = st.data_editor(
            df_admin[["#", "clave", "especialidad", "categoria", "unidad", "precio_referencial", "descripcion"]],
            column_config={
                "#": st.column_config.NumberColumn("#", disabled=True), 
                "clave": st.column_config.TextColumn("Clave", required=True),
                "especialidad": st.column_config.TextColumn("Especialidad"), 
                "categoria": st.column_config.TextColumn("Categoría"),
                "unidad": st.column_config.SelectboxColumn("Unidad", options=unidades_list, required=True),
                "precio_referencial": st.column_config.NumberColumn("Precio Unitario ($)", format="$%.2f", min_value=0.0, step=10.0, required=True),
                "descripcion": st.column_config.TextColumn("Descripción")
            },
            use_container_width=True, 
            hide_index=True, 
            key=ed_bib_key
        )
        
        if ed_bib_key in st.session_state and st.session_state[ed_bib_key].get("edited_rows", {}):
            error_bib_msg = None
            cambios_bib_guardados = 0

            for row_str, col_vals in list(st.session_state[ed_bib_key]["edited_rows"].items()):
                try:
                    r_idx = int(row_str)
                except ValueError:
                    continue
                if r_idx >= len(lista_admin_bib):
                    continue

                bib_actual = lista_admin_bib[r_idx]
                id_bib_mod = bib_actual["id"]
                up_b = {}

                if "clave" in col_vals:
                    val_c = col_vals["clave"]
                    if val_c is None or not str(val_c).strip():
                        error_bib_msg = "⚠️ La clave del concepto maestro es obligatoria y no puede quedar vacía."
                        break
                    up_b["clave"] = str(val_c).strip()

                for campo in ["especialidad", "categoria", "descripcion"]:
                    if campo in col_vals: 
                        up_b[campo] = str(col_vals[campo] or "").strip()

                if "unidad" in col_vals: 
                    if col_vals["unidad"]:
                        up_b["unidad"] = normalizar_unidad(col_vals["unidad"])
                    else:
                        error_bib_msg = "⚠️ La unidad del concepto maestro es obligatoria."
                        break

                if "precio_referencial" in col_vals: 
                    val_pr = col_vals["precio_referencial"]
                    if val_pr is None or str(val_pr).strip() in ("", "None", "nan"):
                        up_b["precio_referencial"] = float(bib_actual.get("precio_referencial") or 0.0)
                    else:
                        try:
                            up_b["precio_referencial"] = max(0.0, float(val_pr))
                        except (ValueError, TypeError):
                            up_b["precio_referencial"] = float(bib_actual.get("precio_referencial") or 0.0)

                if up_b:
                    try:
                        supabase.table("biblioteca_conceptos").update(up_b).eq("id", id_bib_mod).execute()
                        cambios_bib_guardados += 1
                    except Exception as e:
                        error_bib_msg = f"⚠️ Error al actualizar el concepto maestro: {e}"
                        break

            if error_bib_msg:
                st.toast(error_bib_msg, icon="⚠️")
                st.session_state["ed_bib_counter"] = st.session_state.get("ed_bib_counter", 0) + 1
                st.session_state.pop(ed_bib_key, None)
                st.rerun()
            elif cambios_bib_guardados > 0:
                get_biblioteca_conceptos.clear()
                st.toast("✅ Concepto maestro actualizado.")
                st.session_state["ed_bib_counter"] = st.session_state.get("ed_bib_counter", 0) + 1
                st.session_state.pop(ed_bib_key, None)
                st.rerun()
    else:
        st.info(f"ℹ️ La institución '{cat_bib_sel}' no tiene conceptos registrados aún. Utiliza las opciones de arriba para importar desde Excel o dar de alta conceptos manualmente.")

# -------------------------------------------------------------
# TAB 6: PROYECTOS (DATOS GENERALES)
# -------------------------------------------------------------
with tab_proyectos:
    st.markdown("### Gestión de Proyectos 🏢")
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
                
                if st.form_submit_button("Guardar Proyecto"):
                    if not nombre_obra.strip(): st.error("El nombre de la obra es obligatorio.")
                    else:
                        supabase.table("proyectos").insert({
                            "user_id": user_id, "nombre_obra": nombre_obra.strip(), "descripcion_sintetica": descripcion_sintetica.strip(),
                            "ubicacion": ubicacion.strip(), "unidad": unidad.strip(), "contrato_no": contrato_no.strip(),
                            "concurso_no": concurso_no.strip(), "contratista": contratista.strip(), "residente_obra": residente.strip()
                        }).execute()
                        get_proyectos.clear()
                        st.success("✅ Proyecto registrado con éxito.")
                        st.rerun()

    proy_dict_delete = {f"#{idx} — {p['nombre_obra'][:70]}... ({p.get('contrato_no') or 'S/C'})": p["id"] for idx, p in enumerate(lista_proyectos, start=1)} if lista_proyectos else {}

    with col_p_baja:
        with st.expander("🗑 Eliminar Proyecto"):
            if not proy_dict_delete: st.info("No hay proyectos registrados para eliminar.")
            else:
                proy_del_sel = st.selectbox("Seleccionar proyecto a borrar:", list(proy_dict_delete.keys()), key=f"del_proy_sel_{st.session_state.del_proy_counter}")
                st.warning("⚠️ Eliminar un proyecto borrará en cascada todo su catálogo, estimaciones y mediciones.")
                if st.button("Eliminar Proyecto", type="primary", disabled=not st.checkbox("Confirmo la eliminación definitiva del proyecto", key=f"chk_del_proy_{st.session_state.del_proy_counter}")):
                    supabase.table("proyectos").delete().eq("id", proy_dict_delete[proy_del_sel]).execute()
                    get_proyectos.clear()
                    st.session_state.del_proy_counter += 1
                    st.success("Proyecto eliminado correctamente.")
                    st.rerun()

    if lista_proyectos:
        st.markdown("##### Proyectos Registrados:")
        st.caption("💡 *Haz doble clic sobre cualquier campo para actualizar los datos oficiales del contrato.*")
        df_p = pd.DataFrame(lista_proyectos)
        df_p.insert(0, "#", range(1, len(df_p) + 1))
        cols_mostrar = ["#", "nombre_obra", "unidad", "contrato_no", "concurso_no", "ubicacion", "contratista", "residente_obra"]
        for c_m in cols_mostrar[1:]: df_p[c_m] = df_p[c_m].fillna("").astype(str)

        ed_proy_key = f"editor_proyectos_{st.session_state.get('ed_proy_counter', 0)}"
        edited_proy = st.data_editor(
            df_p[cols_mostrar],
            column_config={
                "#": st.column_config.NumberColumn("#", disabled=True), "nombre_obra": st.column_config.TextColumn("Nombre de la Obra", required=True),
                "unidad": st.column_config.TextColumn("Unidad Médica"), "contrato_no": st.column_config.TextColumn("Contrato N°"),
                "concurso_no": st.column_config.TextColumn("Licitación N°"), "ubicacion": st.column_config.TextColumn("Ubicación"),
                "contratista": st.column_config.TextColumn("Contratista"), "residente_obra": st.column_config.TextColumn("Residente / Supervisor")
            },
            use_container_width=True, hide_index=True, key=ed_proy_key
        )

        if ed_proy_key in st.session_state and st.session_state[ed_proy_key].get("edited_rows", {}):
            error_p_msg = None
            cambios_p_guardados = 0
            for row_str, col_vals in list(st.session_state[ed_proy_key]["edited_rows"].items()):
                try:
                    r_idx = int(row_str)
                except ValueError:
                    continue
                if r_idx >= len(lista_proyectos):
                    continue

                id_proy_mod = lista_proyectos[r_idx]["id"]
                up_p = {}

                if "nombre_obra" in col_vals:
                    val_nom = col_vals["nombre_obra"]
                    if val_nom is None or not str(val_nom).strip():
                        error_p_msg = "⚠️ El nombre de la obra es obligatorio y no puede quedar vacío."
                        break
                    up_p["nombre_obra"] = str(val_nom).strip()

                for campo in ["unidad", "contrato_no", "concurso_no", "ubicacion", "contratista", "residente_obra"]:
                    if campo in col_vals:
                        up_p[campo] = str(col_vals[campo] or "").strip()

                if up_p:
                    try:
                        supabase.table("proyectos").update(up_p).eq("id", id_proy_mod).execute()
                        cambios_p_guardados += 1
                    except Exception as e:
                        error_p_msg = f"⚠️ Error al actualizar el proyecto: {e}"
                        break

            if error_p_msg:
                st.toast(error_p_msg, icon="⚠️")
                st.session_state["ed_proy_counter"] = st.session_state.get("ed_proy_counter", 0) + 1
                st.session_state.pop(ed_proy_key, None)
                st.rerun()
            elif cambios_p_guardados > 0:
                get_proyectos.clear()
                st.toast("✅ Datos de la obra actualizados.")
                st.session_state["ed_proy_counter"] = st.session_state.get("ed_proy_counter", 0) + 1
                st.session_state.pop(ed_proy_key, None)
                st.rerun()