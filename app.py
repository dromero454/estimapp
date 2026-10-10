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
import modulos.dashboard_engine
import modulos.mediciones_engine
import modulos.estimaciones_engine
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
importlib.reload(modulos.dashboard_engine)
importlib.reload(modulos.mediciones_engine)
importlib.reload(modulos.estimaciones_engine)

from modulos.auth_engine import render_login_card, render_user_profile_dialog
from modulos.admin_engine import render_admin_dashboard
from modulos.bug_tracker import render_bug_report_dialog, render_bug_tracking_drawer, limpiar_estado_bug
from modulos.dashboard_engine import render_dashboard_tab
from modulos.mediciones_engine import render_mediciones_tab
from modulos.estimaciones_engine import render_estimaciones_tab
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

.tracking-link {
    color: #854d0e !important;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 0.78rem;
    background: #fef9c3;
    padding: 2px 7px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: 1px solid #fde047;
    transition: all 0.15s ease;
    cursor: pointer;
}

.tracking-link:hover {
    background-color: #fef08a !important;
    border-color: #facc15 !important;
    color: #713f12 !important;
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

/* Transición suave global de la aplicación principal al abrir o cerrar paneles laterales */
[data-testid="stMain"], .stMain {
    transition: margin-right 0.25s cubic-bezier(0.16, 1, 0.3, 1), max-width 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
}
[data-testid="stMain"] [data-testid="stMainBlockContainer"] {
    transition: padding-right 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

/* Blindaje permanente para que el panel lateral Drawer NUNCA renderice inline en el flujo de la página */
.st-key-drawer_tracking_panel {
    position: fixed !important;
    top: 0 !important;
    right: 0 !important;
    width: 400px !important;
    max-width: 95vw !important;
    height: 100vh !important;
    min-height: 100vh !important;
    background: #ffffff !important;
    box-shadow: -8px 0 32px rgba(15, 23, 42, 0.22) !important;
    z-index: 999990 !important;
    overflow-y: auto !important;
    border-left: 1px solid #cbd5e1 !important;
    padding: 18px 16px 45px 16px !important;
    box-sizing: border-box !important;
    transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease !important;
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
tracking_link_html = ""
if es_admin_usr:
    admin_link_html = '<div style="margin-top: 4px;"><a href="javascript:void(0)" class="admin-link" title="Consola de Superadministrador">🛡️ Consola Administrador</a></div>'
    tracking_link_html = '<div style="margin-top: 4px;"><a href="javascript:void(0)" class="tracking-link" title="Seguimiento e Iteración de Incidencias">🐞 Seguimiento de bugs</a></div>'

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
{tracking_link_html}
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
    limpiar_estado_bug()
    st.session_state["mostrar_dialogo_bug"] = True

# Disparador en segundo plano para alternar el drawer de seguimiento de bugs
def _cb_toggle_tracking_drawer():
    st.session_state["mostrar_drawer_tracking"] = not st.session_state.get("mostrar_drawer_tracking", False)

st.button("Alternar Drawer Tracking", key="btn_trigger_tracking_drawer", on_click=_cb_toggle_tracking_drawer)

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
    ['Abrir Perfil', 'Alternar Consola Admin', 'Reportar Problema', 'Alternar Drawer Tracking'].forEach(txt => {
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

    // 5. Vincular el enlace de seguimiento de problemas en el sticky-header
    const trackingLink = doc.querySelector('.sticky-header .tracking-link');
    if (trackingLink && !trackingLink.dataset.bound) {
        trackingLink.dataset.bound = "true";
        trackingLink.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const b = Array.from(doc.querySelectorAll('button')).find(btn => btn.innerText.includes('Alternar Drawer Tracking'));
            if (b) {
                b.click();
            }
        });
    }

    // 6. Transición suave de salida (Slide-Out) del drawer al pulsar en Cerrar o Cancelar
    if (!doc.dataset.drawerCloseBound) {
        doc.dataset.drawerCloseBound = "true";
        doc.addEventListener('click', (e) => {
            const target = e.target;
            if (!target) return;
            const isClose = target.closest('.st-key-btn_drawer_close_top') || 
                            target.closest('[class*="btn_drawer_cancel_"]');
            if (isClose) {
                const panel = doc.querySelector('.st-key-drawer_tracking_panel');
                if (panel) {
                    panel.style.setProperty('transform', 'translateX(100%)', 'important');
                    panel.style.setProperty('box-shadow', 'none', 'important');
                }
                const main = doc.querySelector('[data-testid="stMain"], .stMain');
                if (main) {
                    main.style.setProperty('margin-right', '0px', 'important');
                    main.style.setProperty('max-width', '100%', 'important');
                }
            }
        }, true);
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

# Modal de Reporte de Bug si fue invocado
if st.session_state.get("mostrar_dialogo_bug"):
    render_bug_report_dialog(supabase, st.session_state["user"])

# =============================================================
# CONMUTACIÓN DE VISTAS: CONSOLA DE ADMINISTRADOR O PESTAÑAS DE OBRA
# =============================================================
if st.session_state.get("vista_actual") == "admin" and es_admin_usr:
    render_admin_dashboard(supabase)
else:
    # Generador de nombres dinámicos para evitar caché en descargas Excel
    ts_descarga = int(datetime.datetime.now().timestamp())

    # -------------------------------------------------------------
    # INTERFAZ PRINCIPAL (8 PESTAÑAS UNIVERSALES)
    # -------------------------------------------------------------
    LISTA_TABS_OBRA = [
        "📊 Resumen Financiero", "📐 Captura en Campo", "📑 Estimaciones y Raya", 
        "📚 Catálogo del Proyecto", "📖 Biblioteca Maestra", "👷 Personal y Cuadrillas",
        "🚚 Proveedores", "🏢 Proyectos"
    ]

    tab_dashboard, tab_captura, tab_estimaciones, tab_catalogo, tab_biblioteca, tab_personal, tab_proveedores, tab_proyectos = st.tabs(
        LISTA_TABS_OBRA,
        key="tab_obra_activa"
    )

    lista_proyectos = get_proyectos(user_id)
    proyectos_dict = {p["nombre_obra"]: p["id"] for p in lista_proyectos} if lista_proyectos else {}

    # -------------------------------------------------------------
    # TAB 1: CONTROL PRESUPUESTAL (DASHBOARD)
    # -------------------------------------------------------------
    with tab_dashboard:
        render_dashboard_tab(supabase, user_id, lista_proyectos, get_conceptos, get_estimaciones, get_mediciones)

    # -------------------------------------------------------------
    # TAB 2: CAPTURA EN CAMPO
    # -------------------------------------------------------------
    with tab_captura:
        render_mediciones_tab(supabase, user_id, lista_proyectos, get_estimaciones, get_conceptos, get_mediciones)

    # -------------------------------------------------------------
    # TAB 3: ESTIMACIONES Y RAYA
    # -------------------------------------------------------------
    with tab_estimaciones:
        render_estimaciones_tab(supabase, user_id, lista_proyectos, get_estimaciones, get_conceptos, get_mediciones)

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

# =============================================================
# BARRA LATERAL DERECHA (DRAWER TO-GO) DE SEGUIMIENTO DE BUGS
# =============================================================
# Renderizado al final de la página para que la jerarquía y deltas de las 8 pestañas
# permanezcan 100% estables, eliminando por completo cualquier parpadeo o duplicación.
if es_admin_usr and st.session_state.get("mostrar_drawer_tracking"):
    render_bug_tracking_drawer(supabase, st.session_state["user"], st.session_state.get("perfil", {}))