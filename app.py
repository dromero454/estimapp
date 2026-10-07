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
import modulos.auth_engine
import modulos.admin_engine
import modulos.bug_tracker
import modulos.pdf_engine
import modulos.personal_engine
import modulos.proveedores_engine
import modulos.proyectos_engine
import modulos.catalogo_engine
import modulos.biblioteca_engine
importlib.reload(modulos.db_engine)
importlib.reload(modulos.auth_engine)
importlib.reload(modulos.admin_engine)
importlib.reload(modulos.bug_tracker)
importlib.reload(modulos.pdf_engine)
importlib.reload(modulos.personal_engine)
importlib.reload(modulos.proveedores_engine)
importlib.reload(modulos.proyectos_engine)
importlib.reload(modulos.catalogo_engine)
importlib.reload(modulos.biblioteca_engine)

from modulos.auth_engine import render_login_card, render_user_profile_dialog
from modulos.admin_engine import render_admin_dashboard
from modulos.bug_tracker import render_bug_report_dialog
from modulos.catalogo_engine import render_catalogo_tab
from modulos.biblioteca_engine import render_biblioteca_tab
from modulos.personal_engine import render_personal_tab
from modulos.proveedores_engine import render_proveedores_tab
from modulos.proyectos_engine import render_proyectos_tab
from modulos.db_engine import (
    normalizar_unidad, unidades_list, admite_decimales, get_proyectos, get_biblioteca_instituciones,
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

# Detector universal de Logout y Acceso a Cuenta
params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
if "logout" in params:
    if hasattr(st, "query_params"):
        try: del st.query_params["logout"]
        except Exception: pass
    else:
        st.experimental_set_query_params()
    try: supabase.auth.sign_out()
    except Exception: pass
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

if "cuenta" in params or "perfil" in params:
    if hasattr(st, "query_params"):
        for qk in ["cuenta", "perfil"]:
            try: del st.query_params[qk]
            except Exception: pass
    else:
        st.experimental_set_query_params()
    st.session_state["mostrar_dialogo_cuenta"] = True

if "mode" in params and params["mode"] == "restablecer":
    st.session_state["auth_mode"] = "restablecer"
    if hasattr(st, "query_params"):
        try: del st.query_params["mode"]
        except Exception: pass
    st.rerun()

# Detector de Enlace de Recuperación de Contraseña (Supabase Auth)
if "error" in params or "error_description" in params:
    desc = params.get("error_description", "El enlace de recuperación es inválido o ha expirado.")
    st.session_state["error_recuperacion"] = f"⚠️ {desc}"
    st.session_state["auth_mode"] = "login"
    if hasattr(st, "query_params"):
        st.query_params.clear()
    st.rerun()

if ("type" in params and params.get("type") == "recovery") or "access_token" in params or "code" in params:
    acc_token = params.get("access_token")
    ref_token = params.get("refresh_token")
    auth_code = params.get("code")
    if acc_token and ref_token:
        try:
            res = supabase.auth.set_session(acc_token, ref_token)
            if res.user:
                st.session_state["recovery_user"] = res.user
                st.session_state["auth_mode"] = "restablecer"
            else:
                st.session_state["error_recuperacion"] = "El enlace de recuperación es inválido o ha expirado. Por favor solicita uno nuevo."
                st.session_state["auth_mode"] = "login"
        except Exception:
            st.session_state["error_recuperacion"] = "El enlace de recuperación es inválido o ha expirado. Por favor solicita uno nuevo."
            st.session_state["auth_mode"] = "login"
    elif auth_code:
        try:
            res = supabase.auth.exchange_code_for_session({"auth_code": auth_code})
            if res.user:
                st.session_state["recovery_user"] = res.user
                st.session_state["auth_mode"] = "restablecer"
            else:
                st.session_state["error_recuperacion"] = "El enlace de recuperación es inválido o ha expirado. Por favor solicita uno nuevo."
                st.session_state["auth_mode"] = "login"
        except Exception:
            st.session_state["error_recuperacion"] = "El enlace de recuperación es inválido o ha expirado. Por favor solicita uno nuevo."
            st.session_state["auth_mode"] = "login"

    if hasattr(st, "query_params"):
        st.query_params.clear()
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

div[data-testid="stElementContainer"]:has(.sticky-header) div[data-testid="stMarkdownContainer"] {
    margin-bottom: 0 !important;
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
    top: calc(var(--sticky-header-height, 98px) - 2px) !important; /* Altura dinámica del Header con solape anti-ranura */
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

.user-link {
    color: #1e293b !important;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 0.95rem;
    transition: color 0.15s ease, text-decoration 0.15s ease;
    cursor: pointer;
    display: inline-block;
}

.user-link:hover {
    color: #2563eb !important;
    text-decoration: underline !important;
}

.admin-link {
    color: #4338ca !important;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 0.78rem;
    background: #e0e7ff;
    padding: 2px 7px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: 1px solid #c7d2fe;
    transition: all 0.15s ease;
    cursor: pointer;
}

.admin-link:hover {
    background-color: #c7d2fe !important;
    color: #312e81 !important;
    text-decoration: none !important;
}

.bug-link {
    color: #b91c1c !important;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 0.78rem;
    background: #fee2e2;
    padding: 2px 7px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: 1px solid #fecaca;
    transition: all 0.15s ease;
    cursor: pointer;
}

.bug-link:hover {
    background-color: #fecaca !important;
    color: #991b1b !important;
    text-decoration: none !important;
}

/* Ocultar disparadores técnicos del diálogo de perfil, consola admin y reporte de bugs */
div[data-testid="stElementContainer"]:has(#btn-trigger-mi-perfil-anchor),
div[data-testid="stElementContainer"]:has(button[key="btn_trigger_mi_perfil"]),
div[data-testid="stElementContainer"]:has(button[key="btn_trigger_admin_console"]),
div[data-testid="stElementContainer"]:has(button[key="btn_trigger_reportar_bug"]) {
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

div[data-testid="stElementContainer"]:has(iframe[title="streamlit.components.v1.html"]) {
    position: absolute !important;
    width: 0px !important;
    height: 0px !important;
    opacity: 0 !important;
    pointer-events: none !important;
    overflow: hidden !important;
    border: none !important;
    margin: 0 !important;
    padding: 0 !important;
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
nom_solo = (perfil_usr.get("nombre") or "").strip()
nom_usr = nom_solo if nom_solo else (st.session_state["user"].email.split("@")[0])
email_usr = st.session_state["user"].email
empresa_usr = perfil_usr.get("empresa_despacho") or "Independiente"

# Privilegios de Superadministrador y Rol del Usuario
if "es_admin" not in st.session_state:
    if perfil_usr and "es_admin" in perfil_usr:
        st.session_state["rol"] = perfil_usr.get("rol", "residente")
        st.session_state["es_admin"] = bool(perfil_usr.get("es_admin", False)) or (st.session_state["rol"] == "superadmin")
    else:
        try:
            perf_db = supabase.table("perfiles").select("es_admin, rol").eq("id", user_id).execute()
            if perf_db.data:
                st.session_state["rol"] = perf_db.data[0].get("rol", "residente")
                st.session_state["es_admin"] = bool(perf_db.data[0].get("es_admin", False)) or (st.session_state["rol"] == "superadmin")
            else:
                st.session_state["rol"] = "residente"
                st.session_state["es_admin"] = False
        except Exception:
            st.session_state["rol"] = "residente"
            st.session_state["es_admin"] = False

es_admin_usr = bool(st.session_state.get("es_admin", False))
if "vista_actual" not in st.session_state:
    st.session_state["vista_actual"] = "obra"

admin_link_html = ""
if es_admin_usr:
    admin_link_html = '<div style="margin-top: 4px;"><a href="javascript:void(0)" class="admin-link" title="Consola de Superadministrador">🛡️ Consola Administrador</a></div>'

bug_link_html = '<div style="margin-top: 4px;"><a href="javascript:void(0)" class="bug-link" title="Reportar un problema o sugerencia">🐞 ¿Tienes un problema?</a></div>'

# =============================================================
# ENCABEZADO UNIFICADO STICKY (UN SOLO CONTENEDOR)
# =============================================================
st.markdown(f"""<div class="sticky-header">
<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
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
Control de avance físico y financiero de obra pública y privada
</div>
</div>
<div style="display: flex; align-items: center; gap: 16px;">
<div style='text-align: right; line-height: 1.25;'>
<div>
<a href="javascript:void(0)" class="user-link" title="Haz clic para ver y editar tu perfil">
{nom_usr}
</a>
</div>
<div style='font-size: 0.8rem; color: #64748b;'>{email_usr}</div>
{admin_link_html}
{bug_link_html}
</div>
<a href="?logout=1" target="_self" class="btn-salir-link">Salir</a>
</div>
</div>
</div>""", unsafe_allow_html=True)

# Disparador en segundo plano para alternar a la consola de administración
if st.button("Alternar Consola Admin", key="btn_trigger_admin_console"):
    if st.session_state.get("vista_actual") == "admin":
        st.session_state["vista_actual"] = "obra"
    else:
        st.session_state["vista_actual"] = "admin"
    st.rerun()

# Disparador en segundo plano para abrir el modal de perfil sin recargar la página
if st.button("Abrir Perfil", key="btn_trigger_mi_perfil"):
    st.session_state["mostrar_dialogo_cuenta"] = True

# Disparador en segundo plano para abrir el modal de reporte de bugs
if st.button("Reportar Problema", key="btn_trigger_reportar_bug"):
    st.session_state["mostrar_dialogo_bug"] = True

import streamlit.components.v1 as components
components.html("""
<script>
const doc = window.parent.document;
function hideAndBindTrigger() {
    // 0. Sincronizar altura exacta del sticky-header con la variable CSS de las pestañas
    const header = doc.querySelector('.sticky-header');
    if (header) {
        const h = Math.ceil(header.getBoundingClientRect().height);
        if (h > 0) {
            doc.documentElement.style.setProperty('--sticky-header-height', `${h}px`);
        }
    }

    // 1. Ocultar los contenedores de los botones técnicos
    ['Abrir Perfil', 'Alternar Consola Admin', 'Reportar Problema'].forEach(txt => {
        const btn = Array.from(doc.querySelectorAll('button')).find(b => b.innerText.includes(txt));
        if (btn) {
            const container = btn.closest('div[data-testid="stElementContainer"]');
            if (container && container.style.display !== 'none') {
                container.style.display = 'none';
            }
        }
    });

    // 2. Vincular el hipervínculo del usuario en el sticky-header
    const link = doc.querySelector('.sticky-header .user-link');
    if (link && !link.dataset.bound) {
        link.dataset.bound = "true";
        link.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const b = Array.from(doc.querySelectorAll('button')).find(btn => btn.innerText.includes('Abrir Perfil'));
            if (b) {
                b.click();
            }
        });
    }

    // 3. Vincular el enlace de la consola de administrador en el sticky-header
    const adminLink = doc.querySelector('.sticky-header .admin-link');
    if (adminLink && !adminLink.dataset.bound) {
        adminLink.dataset.bound = "true";
        adminLink.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const b = Array.from(doc.querySelectorAll('button')).find(btn => btn.innerText.includes('Alternar Consola Admin'));
            if (b) {
                b.click();
            }
        });
    }

    // 4. Vincular el enlace de reporte de bug en el sticky-header
    const bugLink = doc.querySelector('.sticky-header .bug-link');
    if (bugLink && !bugLink.dataset.bound) {
        bugLink.dataset.bound = "true";
        bugLink.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const b = Array.from(doc.querySelectorAll('button')).find(btn => btn.innerText.includes('Reportar Problema'));
            if (b) {
                b.click();
            }
        });
    }
}
hideAndBindTrigger();
setInterval(hideAndBindTrigger, 200);
</script>
""", height=0, width=0)

# Modal de Cuenta / Perfil si fue invocado (se consume inmediatamente para evitar que reaparezca en reruns)
if st.session_state.get("mostrar_dialogo_cuenta"):
    st.session_state["mostrar_dialogo_cuenta"] = False
    render_user_profile_dialog(supabase, st.session_state["user"], st.session_state.get("perfil", {}))

# Modal de Reporte de Bug si fue invocado (se consume inmediatamente para evitar que reaparezca en reruns)
if st.session_state.get("mostrar_dialogo_bug"):
    st.session_state["mostrar_dialogo_bug"] = False
    render_bug_report_dialog(supabase, st.session_state["user"])

# =============================================================
# CONMUTACIÓN DE VISTAS: CONSOLA DE ADMINISTRADOR
# =============================================================
if st.session_state.get("vista_actual") == "admin" and es_admin_usr:
    render_admin_dashboard(supabase)
    st.stop()

# Generador de nombres dinámicos para evitar caché en descargas Excel
ts_descarga = int(datetime.datetime.now().timestamp())

# =============================================================
# INTERFAZ PRINCIPAL (8 PESTAÑAS UNIVERSALES)
# =============================================================
tab_dashboard, tab_captura, tab_estimaciones, tab_catalogo, tab_biblioteca, tab_personal, tab_proveedores, tab_proyectos = st.tabs([
    "📊 Resumen Financiero", "📐 Captura en Campo", "📑 Estimaciones y Raya", 
    "📚 Catálogo del Proyecto", "📖 Biblioteca Maestra", "👷 Personal y Cuadrillas",
    "🚚 Proveedores", "🏢 Proyectos"
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
                        "Cant. Contratada": st.column_config.NumberColumn("Cant. Contratada", format="%.2f", width=105),
                        "Cant. en Periodo": st.column_config.NumberColumn("Cant. en Periodo", format="%.2f", width=105),
                        "Cant. Acumulada": st.column_config.NumberColumn("Cant. Acumulada", format="%.2f", width=105),
                        "Saldo Físico": st.column_config.NumberColumn("Saldo Físico", format="%.2f", width=95),
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
                    archivos_subidos_tmp = []
                    try:
                        if foto:
                            contenido_f, mime_f = optimizar_imagen(foto)
                            fname_f = f"{uuid.uuid4()}.jpg"
                            supabase.storage.from_("evidencias").upload(fname_f, contenido_f, {"content-type": mime_f})
                            url_foto = supabase.storage.from_("evidencias").get_public_url(fname_f)
                            archivos_subidos_tmp.append(fname_f)
                        if croquis:
                            contenido_c, mime_c = optimizar_imagen(croquis)
                            fname_c = f"{uuid.uuid4()}.jpg"
                            supabase.storage.from_("evidencias").upload(fname_c, contenido_c, {"content-type": mime_c})
                            url_croquis = supabase.storage.from_("evidencias").get_public_url(fname_c)
                            archivos_subidos_tmp.append(fname_c)

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
                    except Exception as ex_ins_med:
                        if archivos_subidos_tmp:
                            try: supabase.storage.from_("evidencias").remove(archivos_subidos_tmp)
                            except: pass
                        st.error(f"Error al guardar medición: {ex_ins_med}")

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

                        try:
                            # 1. Eliminar primero de la base de datos para garantizar integridad
                            if ids_to_delete:
                                for chunk in [ids_to_delete[i:i+50] for i in range(0, len(ids_to_delete), 50)]:
                                    supabase.table("mediciones_campo").delete().in_("id", chunk).execute()

                            # 2. Solo tras confirmarse la eliminación en BD, purgar fotos de Storage
                            if archivos_a_borrar:
                                for chunk in [archivos_a_borrar[i:i+50] for i in range(0, len(archivos_a_borrar), 50)]:
                                    try: supabase.storage.from_("evidencias").remove(chunk)
                                    except: pass

                            get_mediciones.clear()
                            st.session_state.del_med_counter += 1
                            st.success(f"{len(ids_to_delete)} mediciones eliminadas.")
                            st.rerun()
                        except Exception as ex_del_m:
                            st.error(f"Error al eliminar mediciones: {ex_del_m}")

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
                        id_est_del = dict_est_borrar[est_del_sel]
                        try:
                            # 1. Recolectar evidencias de las mediciones asociadas a esta estimación
                            archivos_ev_est = []
                            try:
                                res_meds_est = supabase.table("mediciones_campo").select("url_foto, url_croquis").eq("id_estimacion", id_est_del).execute()
                                for m_row in (res_meds_est.data or []):
                                    if m_row.get("url_foto"):
                                        nf = extraer_nombre_archivo(m_row["url_foto"])
                                        if nf: archivos_ev_est.append(nf)
                                    if m_row.get("url_croquis"):
                                        nc = extraer_nombre_archivo(m_row["url_croquis"])
                                        if nc: archivos_ev_est.append(nc)
                            except Exception:
                                pass

                            # 2. Borrar primero en base de datos (PostgreSQL ejecuta CASCADE en mediciones_campo)
                            supabase.table("estimaciones").delete().eq("id", id_est_del).execute()

                            # 3. Solo tras éxito en BD, purgar archivos físicos de Storage
                            if archivos_ev_est:
                                for chunk_ev in [archivos_ev_est[i:i+50] for i in range(0, len(archivos_ev_est), 50)]:
                                    try: supabase.storage.from_("evidencias").remove(chunk_ev)
                                    except: pass

                            get_estimaciones.clear()
                            get_mediciones.clear()
                            st.session_state.del_est_counter += 1
                            st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                            st.success("Estimación y mediciones asociadas eliminadas correctamente.")
                            st.rerun()
                        except Exception as ex_del_est:
                            st.error(f"Error al eliminar estimación: {ex_del_est}")

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
            
            # Restricción de plantillas institucionales (IMSS y PJF) exclusivamente para Ingrid
            email_sesion_norm = (getattr(st.session_state.get("user"), "email", "") or email_usr or "").lower().strip()
            if email_sesion_norm == "ingrid.gutierrez2904@gmail.com":
                opciones_formato_excel = ["IMSS", "Poder Judicial de la Federación", "Formato Estimapp"]
            else:
                opciones_formato_excel = ["Formato Estimapp"]

            formato_institucion = col_exp_2.selectbox("Formato de Salida:", opciones_formato_excel)
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
    render_catalogo_tab(supabase, user_id, lista_proyectos, get_conceptos)

# -------------------------------------------------------------
# TAB 5: BIBLIOTECA MAESTRA GLOBAL
# -------------------------------------------------------------
with tab_biblioteca:
    render_biblioteca_tab(supabase, user_id)


# -------------------------------------------------------------
# TAB 6: PERSONAL Y CUADRILLAS
# -------------------------------------------------------------
with tab_personal:
    render_personal_tab(supabase, user_id)

# -------------------------------------------------------------
# TAB 7: PROVEEDORES COMERCIALES
# -------------------------------------------------------------
with tab_proveedores:
    render_proveedores_tab(supabase, user_id)

# -------------------------------------------------------------
# TAB 8: GESTIÓN DE PROYECTOS Y GEORREFERENCIACIÓN
# -------------------------------------------------------------
with tab_proyectos:
    render_proyectos_tab(supabase, user_id, lista_proyectos, get_proyectos)