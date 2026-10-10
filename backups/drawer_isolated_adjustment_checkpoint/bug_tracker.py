"""
Módulo de Gestión de Incidencias y Reporte de Bugs (Bug Tracker) para Estimapp
==============================================================================
Permite a usuarios y administradores levantar reportes de fallas con evidencia
múltiple desde la aplicación, registrándolos en Supabase Storage y Base de Datos.
"""

from datetime import datetime
import time
import base64
import uuid
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from supabase import Client

_clipboard_component_dir = Path(__file__).parent / "clipboard_component"
clipboard_paste_box = components.declare_component(
    "clipboard_paste_box",
    path=str(_clipboard_component_dir.resolve())
)

PESTANAS_MODULOS = [
    "General",
    "Resumen Financiero",
    "Control Presupuestal",
    "Captura en Campo",
    "Estimaciones y Raya",
    "Estimaciones",
    "Catálogo del Proyecto",
    "Biblioteca Maestra",
    "Personal y Cuadrillas",
    "Proveedores",
    "Proyectos",
    "Perfil / Cuenta",
    "Consola Admin",
]

CATEGORIAS_BUGS = [
    "Interfaz y Visualización",
    "Cálculos y Fórmulas",
    "Exportación de Archivos",
    "Persistencia y Guardado",
    "Rendimiento",
    "Otro",
]


def limpiar_estado_bug() -> None:
    """
    Limpia completamente el estado del diálogo modal para garantizar
    que siempre abra en su estado default, sin residuos de sesiones previas.
    """
    st.session_state["mostrar_dialogo_bug"] = False
    st.session_state["bug_screenshots_pegados"] = []
    st.session_state["last_pasted_ts"] = None
    st.session_state["bug_form_version"] = st.session_state.get("bug_form_version", 0) + 1
    # Limpiar cualquier clave residual de widgets asociados al modal
    for k in list(st.session_state.keys()):
        if k.startswith("bug_input_") or k.startswith("bug_clipboard_") or k.startswith("btn_cancelar_bug_") or k.startswith("btn_enviar_bug_"):
            try:
                del st.session_state[k]
            except Exception:
                pass


def cerrar_dialogo_bug() -> None:
    """Callback invocado por Streamlit al descartar el diálogo (botón X o clic fuera del modal)."""
    limpiar_estado_bug()


def _cb_eliminar_screenshot_bug(sc_id: str) -> None:
    """Callback para eliminar una captura y renumerar consecutivamente sin huecos."""
    if "bug_screenshots_pegados" in st.session_state:
        st.session_state["bug_screenshots_pegados"] = [
            x for x in st.session_state["bug_screenshots_pegados"] if x["id"] != sc_id
        ]
        for idx, item in enumerate(st.session_state["bug_screenshots_pegados"], start=1):
            item["nombre"] = f"screenshot_{idx}.png"


@st.dialog("🐞 Reportar un problema o sugerencia", width="medium", on_dismiss=cerrar_dialogo_bug)
def render_bug_report_dialog(supabase: Client, user) -> None:
    """
    Renderiza el diálogo modal para capturar un reporte de error o sugerencia.
    Guarda evidencias en el bucket 'bugs' y el ticket en 'public.reportes_bugs'.
    """
    v = st.session_state.get("bug_form_version", 0)

    st.markdown(
        """
        <p style="color: #64748b; font-size: 0.92rem; margin-top: -6px; margin-bottom: 14px;">
            Describe el problema detectado para que nuestro equipo técnico lo reproduzca y solucione a la brevedad.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # 1. Selector múltiple de pestañas / módulos afectados
    tabs_sel = st.multiselect(
        "Pestañas / Módulos afectados:",
        options=PESTANAS_MODULOS,
        default=["General"],
        help="Indica en qué secciones de la aplicación observaste la anomalía.",
        key=f"bug_input_tabs_{v}",
    )

    # 2. Selector simple de categoría
    cat_sel = st.selectbox(
        "Categoría del problema:",
        options=CATEGORIAS_BUGS,
        index=0,
        help="Clasifica el tipo de error para priorizar su atención.",
        key=f"bug_input_categoria_{v}",
    )

    # 3. Área de texto obligatoria
    desc_sel = st.text_area(
        "Describe detalladamente qué estabas haciendo y qué falló *",
        placeholder="Ejemplo: Al capturar una estimación en el periodo 2 e intentar exportar a Excel, la cantidad acumulada no se actualizó...",
        height=120,
        help="La descripción detallada es obligatoria.",
        key=f"bug_input_descripcion_{v}",
    )

    # 4. Evidencias en dos columnas paralelas al 50%
    col_archivos, col_clipboard = st.columns(2)

    with col_archivos:
        archivos_evidencia = st.file_uploader(
            "Evidencias adjuntas (opcional - múltiples archivos):",
            type=["png", "jpg", "jpeg", "pdf", "xlsx", "csv"],
            accept_multiple_files=True,
            help="Adjunta capturas de pantalla, archivos PDF o plantillas Excel que evidencien el problema.",
            key=f"bug_input_archivos_{v}",
        )
        if archivos_evidencia:
            st.caption(f"📎 **{len(archivos_evidencia)}** archivo(s) seleccionado(s).")

    with col_clipboard:
        st.markdown(
            """
            <div style="height: 24px; display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                <span style="font-size: 0.875rem; font-weight: 400; color: #31333f; line-height: 24px;">
                    Screenshots (Opcional - múltiples archivos):
                </span>
                <span title="Haz clic en el recuadro o presiona Ctrl + V para pegar imágenes directamente desde tu portapapeles." style="cursor: help; color: #64748b; font-size: 0.85rem;">ℹ️</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        pasted_data = clipboard_paste_box(key=f"bug_clipboard_component_{v}")

        if "bug_screenshots_pegados" not in st.session_state:
            st.session_state["bug_screenshots_pegados"] = []

        if pasted_data and isinstance(pasted_data, dict) and "dataUrl" in pasted_data:
            ts = pasted_data.get("timestamp")
            if ts and st.session_state.get("last_pasted_ts") != ts:
                st.session_state["last_pasted_ts"] = ts
                data_url = pasted_data["dataUrl"]
                try:
                    header, encoded = data_url.split(";base64,", 1)
                    b_data = base64.b64decode(encoded)
                    idx = len(st.session_state["bug_screenshots_pegados"]) + 1
                    st.session_state["bug_screenshots_pegados"].append({
                        "id": str(uuid.uuid4())[:8],
                        "nombre": f"screenshot_{idx}.png",
                        "bytes": b_data,
                        "size_kb": round(len(b_data) / 1024, 1),
                    })
                except Exception as ex_b64:
                    st.error(f"Error procesando captura: {ex_b64}")

        if st.session_state["bug_screenshots_pegados"]:
            st.caption(f"📸 **{len(st.session_state['bug_screenshots_pegados'])}** captura(s) del portapapeles:")
            num_sc = len(st.session_state["bug_screenshots_pegados"])
            # Contenedor scrolleable con altura acotada cuando hay más de 3 capturas (exactamente 3 visibles a la par)
            cont_sc = st.container(height=158, border=False) if num_sc > 3 else st.container()
            with cont_sc:
                for s in list(st.session_state["bug_screenshots_pegados"]):
                    c_txt, c_del = st.columns([4, 1])
                    with c_txt:
                        st.caption(f"🖼️ **{s['nombre']}** ({s['size_kb']} KB)")
                    with c_del:
                        st.button(
                            "❌",
                            key=f"del_sc_{s['id']}",
                            help=f"Eliminar {s['nombre']}",
                            on_click=_cb_eliminar_screenshot_bug,
                            args=(s["id"],),
                        )

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    col_cancel, col_enviar = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", use_container_width=True, key=f"btn_cancelar_bug_modal_{v}"):
            limpiar_estado_bug()
            st.rerun()

    with col_enviar:
        if st.button("🚀 Enviar Reporte", type="primary", use_container_width=True, key=f"btn_enviar_bug_modal_{v}"):
            desc_limpia = (desc_sel or "").strip()
            if not desc_limpia:
                st.error("⚠️ La descripción detallada del problema es obligatoria.")
                return

            if not tabs_sel:
                st.error("⚠️ Selecciona al menos una pestaña o módulo afectado.")
                return

            with st.spinner("Registrando ticket..."):
                try:
                    # 1. Obtener siguiente folio correlativo atómico (con reset limpio a BUG-001 si está vacía)
                    folio = None
                    try:
                        res_fol = supabase.rpc("obtener_siguiente_folio_bug").execute()
                        if res_fol.data:
                            folio = res_fol.data
                    except Exception:
                        pass

                    if not folio:
                        try:
                            res_cnt = supabase.table("reportes_bugs").select("id", count="exact").execute()
                            total_reg = res_cnt.count or 0
                            folio = f"BUG-{str(total_reg + 1).zfill(3)}"
                        except Exception:
                            folio = f"BUG-{int(datetime.now().timestamp())}"

                    # 2. Subir evidencias a Supabase Storage bucket 'bugs'
                    rutas_subidas = []
                    # A) Archivos tradicionales de file_uploader
                    if archivos_evidencia:
                        for f in archivos_evidencia:
                            nombre_limpio = f.name.replace(" ", "_")
                            ruta_storage = f"{folio}/{nombre_limpio}"
                            bytes_archivo = f.getvalue()
                            content_type = f.type or "application/octet-stream"

                            try:
                                supabase.storage.from_("bugs").upload(
                                    ruta_storage,
                                    bytes_archivo,
                                    file_options={"content-type": content_type, "upsert": "true"},
                                )
                                rutas_subidas.append(ruta_storage)
                            except Exception as ex_upload:
                                st.warning(f"No se pudo subir {f.name}: {ex_upload}")

                    # B) Screenshots pegados desde portapapeles
                    if st.session_state.get("bug_screenshots_pegados"):
                        for s in st.session_state["bug_screenshots_pegados"]:
                            ruta_storage = f"{folio}/{s['nombre']}"
                            try:
                                supabase.storage.from_("bugs").upload(
                                    ruta_storage,
                                    s["bytes"],
                                    file_options={"content-type": "image/png", "upsert": "true"},
                                )
                                rutas_subidas.append(ruta_storage)
                            except Exception as ex_upload:
                                st.warning(f"No se pudo subir {s['nombre']}: {ex_upload}")

                    # 3. Insertar registro en public.reportes_bugs
                    nuevo_ticket = {
                        "folio": folio,
                        "user_id": user.id,
                        "tabs_afectadas": tabs_sel,
                        "categoria": cat_sel,
                        "descripcion": desc_limpia,
                        "archivos_adjuntos": rutas_subidas,
                        "estado": "Abierto",
                    }

                    supabase.table("reportes_bugs").insert(nuevo_ticket).execute()
                    limpiar_estado_bug()

                    st.success(f"Reporte {folio} registrado!")
                    time.sleep(1.2)
                    st.rerun()

                except Exception as ex_reg:
                    # Rollback de archivos recién subidos si la base de datos rechaza la inserción
                    if rutas_subidas:
                        try:
                            supabase.storage.from_("bugs").remove(rutas_subidas)
                        except Exception:
                            pass
                    st.error(f"❌ Error al registrar el reporte de bug: {ex_reg}")


# Re-exportación para retrocompatibilidad
from modulos.drawer_tracker import render_bug_tracking_drawer, _cb_eliminar_screenshot_drawer

