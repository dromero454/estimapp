"""
Módulo de Gestión de Incidencias y Reporte de Bugs (Bug Tracker) para Estimapp
==============================================================================
Permite a usuarios y administradores levantar reportes de fallas con evidencia
múltiple desde la aplicación, registrándolos en Supabase Storage y Base de Datos.
"""

from datetime import datetime
import time
import streamlit as st
from supabase import Client

PESTANAS_MODULOS = [
    "Control Presupuestal",
    "Captura en Campo",
    "Estimaciones",
    "Catálogo del Proyecto",
    "Biblioteca Maestra",
    "Proyectos",
    "Perfil / Cuenta",
    "Consola Admin",
    "General",
]

CATEGORIAS_BUGS = [
    "Interfaz y Visualización",
    "Cálculos y Fórmulas",
    "Exportación de Archivos",
    "Persistencia y Guardado",
    "Rendimiento",
    "Otro",
]


@st.dialog("🐞 Reportar un problema o sugerencia", width="medium", on_dismiss="rerun")
def render_bug_report_dialog(supabase: Client, user) -> None:
    """
    Renderiza el diálogo modal para capturar un reporte de error o sugerencia.
    Guarda evidencias en el bucket 'bugs' y el ticket en 'public.reportes_bugs'.
    """
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
        key="bug_input_tabs",
    )

    # 2. Selector simple de categoría
    cat_sel = st.selectbox(
        "Categoría del problema:",
        options=CATEGORIAS_BUGS,
        index=0,
        help="Clasifica el tipo de error para priorizar su atención.",
        key="bug_input_categoria",
    )

    # 3. Área de texto obligatoria
    desc_sel = st.text_area(
        "Describe detalladamente qué estabas haciendo y qué falló *",
        placeholder="Ejemplo: Al capturar una estimación en el periodo 2 e intentar exportar a Excel, la cantidad acumulada no se actualizó...",
        height=120,
        help="La descripción detallada es obligatoria.",
        key="bug_input_descripcion",
    )

    # 4. Subida múltiple de evidencias
    archivos_evidencia = st.file_uploader(
        "Evidencias adjuntas (opcional - múltiples archivos):",
        type=["png", "jpg", "jpeg", "pdf", "xlsx", "csv"],
        accept_multiple_files=True,
        help="Adjunta capturas de pantalla, archivos PDF o plantillas Excel que evidencien el problema.",
        key="bug_input_archivos",
    )

    if archivos_evidencia:
        st.caption(f"📎 **{len(archivos_evidencia)}** archivo(s) seleccionado(s) para adjuntar al ticket.")

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    col_cancel, col_enviar = st.columns([1, 1.4])
    with col_cancel:
        if st.button("Cancelar", use_container_width=True, key="btn_cancelar_bug_modal"):
            st.rerun()

    with col_enviar:
        if st.button("🚀 Enviar Reporte", type="primary", use_container_width=True, key="btn_enviar_bug_modal"):
            desc_limpia = (desc_sel or "").strip()
            if not desc_limpia:
                st.error("⚠️ La descripción detallada del problema es obligatoria.")
                return

            if not tabs_sel:
                st.error("⚠️ Selecciona al menos una pestaña o módulo afectado.")
                return

            with st.spinner("Registrando ticket y subiendo evidencias a Supabase..."):
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

                    st.success(f"✅ ¡Reporte **{folio}** registrado exitosamente!")
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
