"""
Módulo del Drawer Lateral ("To-Go") de Seguimiento de Problemas para Estimapp
=============================================================================
Provee la barra lateral derecha persistente exclusiva para Superadministradores.
Permite auditar, editar y dar retroalimentación a tickets activos mientras se navega
por la aplicación principal o por la consola administrativa.

Aislado con @st.fragment para garantizar que todas las interacciones dentro del drawer
se ejecuten de forma local sin disparar reruns en la interfaz principal ni en las pestañas.
"""

from datetime import datetime
import time
import base64
import uuid
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from supabase import Client
from modulos.bug_tracker import PESTANAS_MODULOS, CATEGORIAS_BUGS, clipboard_paste_box


def _cb_eliminar_screenshot_drawer(sc_id: str) -> None:
    """Callback para eliminar una captura en el drawer y renumerar consecutivamente."""
    if "drawer_screenshots_pegados" in st.session_state:
        st.session_state["drawer_screenshots_pegados"] = [
            x for x in st.session_state["drawer_screenshots_pegados"] if x["id"] != sc_id
        ]
        for idx, item in enumerate(st.session_state["drawer_screenshots_pegados"], start=1):
            item["nombre"] = f"screenshot_{idx}.png"


@st.fragment
def render_bug_tracking_drawer(supabase: Client, user, perfil: dict) -> None:
    """
    Renderiza la Barra Lateral Derecha (Drawer "To-Go") de Seguimiento de Problemas.
    Exclusiva para Superadministradores. Permite auditar, editar y retroalimentar
    tickets activos mientras navegan libremente por la aplicación principal.
    Aislada con @st.fragment para garantizar estabilidad visual y evitar recargas en la app principal.
    """
    def _cb_cerrar_drawer_tracking():
        st.session_state["mostrar_drawer_tracking"] = False
        st.session_state["drawer_screenshots_pegados"] = []
        st.session_state["drawer_last_pasted_ts"] = None
        st.rerun(scope="app")

    # 1. Inyección de Estilos CSS Especializados (Opción B: Empuje Suave de Pantalla - Ancho 400px)
    st.markdown(
        """
        <style>
        /* Drawer anclado al lateral derecho con scroll independiente (ancho ajustado a 400px) */
        .st-key-drawer_tracking_panel {
            position: fixed !important;
            top: 0 !important;
            right: 0 !important;
            width: 400px !important;
            max-width: 95vw !important;
            height: 100vh !important;
            background: #ffffff !important;
            box-shadow: -8px 0 32px rgba(15, 23, 42, 0.22) !important;
            z-index: 999990 !important;
            overflow-y: auto !important;
            border-left: 1px solid #cbd5e1 !important;
            padding: 18px 16px 45px 16px !important;
            box-sizing: border-box !important;
            transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease !important;
            animation: drawerSlideIn 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }
        @keyframes drawerSlideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
        }

        /* Empuje suave de la aplicación principal para dejar 100% visible la interfaz (Opción B) */
        [data-testid="stMain"], .stMain {
            margin-right: 400px !important;
            max-width: calc(100% - 400px) !important;
            transition: margin-right 0.25s cubic-bezier(0.16, 1, 0.3, 1), max-width 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }
        /* Ajustar padding-right del contenedor principal para que el perfil quede pegado junto al drawer */
        [data-testid="stMain"] [data-testid="stMainBlockContainer"] {
            padding-right: 28px !important;
            transition: padding-right 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }
        .sticky-header {
            width: 100% !important;
        }

        /* Alinear botón ✕ exactamente al borde derecho del contenedor y en la misma cota del encabezado */
        .st-key-btn_drawer_close_top {
            position: absolute !important;
            top: 18px !important;
            right: 16px !important;
            z-index: 999999 !important;
        }
        .st-key-btn_drawer_close_top button {
            width: 32px !important;
            min-width: 32px !important;
            height: 32px !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-radius: 6px !important;
            font-size: 1.1rem !important;
            line-height: 1 !important;
            border: 1px solid #cbd5e1 !important;
            background: #f8fafc !important;
            color: #475569 !important;
            transition: all 0.15s ease !important;
        }
        .st-key-btn_drawer_close_top button:hover {
            background: #fee2e2 !important;
            border-color: #fca5a5 !important;
            color: #dc2626 !important;
        }

        /* Ocultar completamente la leyenda '200MB per file...' */
        .st-key-drawer_tracking_panel [data-testid="stFileUploaderDropzoneInstructions"] {
            display: none !important;
        }
        /* Dropzone de subida: 48px cuando está vacío a la par de Pegar Captura */
        .st-key-drawer_tracking_panel [data-testid="stFileUploaderDropzone"]:not(:has([data-testid="stFileChips"])) {
            min-height: 48px !important;
            height: 48px !important;
            padding: 4px 8px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        /* Cuando contiene archivos subidos, crece de forma limpia y estiliza los chips */
        .st-key-drawer_tracking_panel [data-testid="stFileUploaderDropzone"]:has([data-testid="stFileChips"]) {
            min-height: 48px !important;
            height: auto !important;
            padding: 4px 6px !important;
            display: flex !important;
            flex-direction: column !important;
        }
        /* Lista de chips de archivos scrolleable con altura máxima de 158px (igual a screens) */
        .st-key-drawer_tracking_panel [data-testid="stFileChips"] {
            max-height: 158px !important;
            overflow-y: auto !important;
            width: 100% !important;
            display: flex !important;
            flex-direction: column !important;
            gap: 4px !important;
        }
        .st-key-drawer_tracking_panel [data-testid="stFileChips"] > div {
            min-height: 38px !important;
            width: 100% !important;
        }
        .st-key-drawer_tracking_panel [data-testid="stFileUploaderDropzone"] button {
            padding: 4px 10px !important;
            font-size: 0.82rem !important;
        }

        /* Reducción del 25% en tipografía, íconos de ayuda (?) y altura de los 4 selectores superiores */
        .st-key-drawer_top_selectors_block div[data-testid="stElementContainer"] {
            margin-bottom: 2px !important;
        }
        .st-key-drawer_top_selectors_block label[data-testid="stWidgetLabel"] {
            margin-bottom: 1px !important;
            min-height: auto !important;
        }
        .st-key-drawer_top_selectors_block label[data-testid="stWidgetLabel"] p,
        .st-key-drawer_top_selectors_block label[data-testid="stWidgetLabel"] span {
            font-size: 0.68rem !important;
            font-weight: 500 !important;
            line-height: 1.15 !important;
            color: #475569 !important;
        }
        .st-key-drawer_top_selectors_block [data-testid="stTooltipIcon"] {
            transform: scale(0.75) !important;
            transform-origin: center !important;
            margin-left: 2px !important;
        }
        .st-key-drawer_top_selectors_block [data-testid="stTooltipIcon"] svg {
            width: 12px !important;
            height: 12px !important;
        }
        /* Controles y cajas de selección React Aria & BaseWeb (-25% altura y texto) */
        .st-key-drawer_top_selectors_block .stSelectbox input,
        .st-key-drawer_top_selectors_block .stMultiSelect input,
        .st-key-drawer_top_selectors_block div[role="group"] input,
        .st-key-drawer_top_selectors_block div[data-baseweb="select"] input {
            font-size: 0.72rem !important;
            height: 26px !important;
            line-height: 26px !important;
        }
        .st-key-drawer_top_selectors_block div[role="group"],
        .st-key-drawer_top_selectors_block div[data-baseweb="select"] {
            min-height: 28px !important;
            height: 28px !important;
            padding-top: 1px !important;
            padding-bottom: 1px !important;
            padding-left: 8px !important;
            padding-right: 8px !important;
            font-size: 0.72rem !important;
        }
        /* Tarjetitas / Tags de Pestañas afectadas (-25% escala armoniosa) */
        .st-key-drawer_top_selectors_block [data-tag] {
            height: 17px !important;
            min-height: 17px !important;
            max-height: 17px !important;
            line-height: 15px !important;
            font-size: 0.60rem !important;
            padding: 0 5px !important;
            margin: 2px 3px 2px 0 !important;
            border-radius: 3px !important;
            display: inline-flex !important;
            align-items: center !important;
        }
        .st-key-drawer_top_selectors_block [data-tag] > span {
            font-size: 0.60rem !important;
            line-height: 15px !important;
        }
        .st-key-drawer_top_selectors_block [data-tag] > button {
            font-size: 0.60rem !important;
            width: 12px !important;
            height: 12px !important;
            padding: 0 !important;
            margin-left: 2px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        .st-key-drawer_top_selectors_block [data-tag] svg {
            width: 7px !important;
            height: 7px !important;
        }
        .st-key-drawer_top_selectors_block div[data-testid="stMultiSelectTagsContainer"] {
            padding: 2px 4px !important;
            min-height: 24px !important;
        }

        /* Contenedor scrolleable unificado para Descripción, Notas y Comentarios */
        .st-key-drawer_textareas_block {
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            background-color: #f8fafc !important;
            padding: 8px 10px !important;
            box-sizing: border-box !important;
            margin-top: 4px !important;
            margin-bottom: 8px !important;
        }
        .st-key-drawer_textareas_block [data-testid="stElementContainer"] {
            flex-shrink: 0 !important;
            flex-grow: 0 !important;
            margin-bottom: 10px !important;
        }
        .st-key-drawer_textareas_block .stTextArea {
            flex-shrink: 0 !important;
        }
        .st-key-drawer_textareas_block label[data-testid="stWidgetLabel"] p {
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            color: #334155 !important;
        }

        /* Botón de eliminación de screenshots nítido y centrado */
        .st-key-drawer_tracking_panel div[class*="del_sc_drawer_"] {
            width: auto !important;
            display: flex !important;
            justify-content: flex-end !important;
            align-items: center !important;
        }
        .st-key-drawer_tracking_panel div[class*="del_sc_drawer_"] button {
            padding: 0 !important;
            min-width: 28px !important;
            width: 28px !important;
            height: 28px !important;
            min-height: 28px !important;
            line-height: 1 !important;
            font-size: 0.85rem !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-radius: 6px !important;
            color: #64748b !important;
            border: 1px solid #cbd5e1 !important;
            background: #ffffff !important;
            transition: all 0.15s ease !important;
        }
        .st-key-drawer_tracking_panel div[class*="del_sc_drawer_"] button:hover {
            background: #fee2e2 !important;
            border-color: #fca5a5 !important;
            color: #dc2626 !important;
        }
        .st-key-drawer_tracking_panel div[class*="del_sc_drawer_"] button div,
        .st-key-drawer_tracking_panel div[class*="del_sc_drawer_"] button p {
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 0.85rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="drawer_tracking_panel"):
        # Encabezado del Drawer con botón de cierre ✕ perfectamente alineado a la derecha
        col_hdr_title, col_hdr_btn = st.columns([5.5, 0.9])
        with col_hdr_title:
            st.markdown(
                """
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 1.25rem; font-weight: 700; color: #1e293b;">🐞 Seguimiento</span>
                    <span style="background: #e0f2fe; color: #0369a1; padding: 2px 7px; border-radius: 9999px; font-size: 0.70rem; font-weight: 600;">Superadmin</span>
                </div>
                <div style="font-size: 0.80rem; color: #64748b; margin-top: 2px; margin-bottom: 8px;">
                    Auditoría y feedback de tickets activos.
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_hdr_btn:
            st.button("✕", key="btn_drawer_close_top", on_click=_cb_cerrar_drawer_tracking)

        # 2. Cargar tickets de trabajo activo (To-Do para el Superadmin: Abierto, En Revisión, Corregido, Bajo Consideración)
        try:
            res_tkts = (
                supabase.table("reportes_bugs")
                .select("*")
                .in_("estado", ["Abierto", "En Revisión", "Corregido", "Bajo Consideración"])
                .order("folio", desc=False)
                .execute()
            )
            tickets_activos = res_tkts.data or []
        except Exception as ex_db:
            st.error(f"Error cargando tickets de incidencias: {ex_db}")
            tickets_activos = []

        if not tickets_activos:
            st.info("🎉 ¡Todo al día! No hay tickets pendientes de revisión o resolución en este momento.")
            return

        # 3. Selector de Ticket con búsqueda integrada
        tkt_options = []
        tkt_map = {}
        for t in tickets_activos:
            desc_corta = (t.get("descripcion") or "").replace("\n", " ").strip()
            if len(desc_corta) > 36:
                desc_corta = desc_corta[:33] + "..."
            label = f"{t.get('folio')} — {t.get('categoria', 'General')} ({t.get('estado', 'Abierto')}) | {desc_corta}"
            tkt_options.append(label)
            tkt_map[label] = t

        # Determinar índice seleccionado previo si existe
        prev_id = st.session_state.get("drawer_active_tkt_id")
        def_idx = 0
        if prev_id:
            for idx_o, lbl in enumerate(tkt_options):
                if tkt_map[lbl]["id"] == prev_id:
                    def_idx = idx_o
                    break

        with st.container(key="drawer_top_selectors_block"):
            sel_tkt_label = st.selectbox(
                "Seleccionar ticket para auditar o editar:",
                options=tkt_options,
                index=def_idx,
                key="drawer_select_tkt_box",
                help="Selecciona cualquier ticket activo en el sistema para ver y actualizar sus datos."
            )

            tkt_activo = tkt_map[sel_tkt_label]

            # Resetear capturas si cambió de ticket
            if st.session_state.get("drawer_active_tkt_id") != tkt_activo["id"]:
                st.session_state["drawer_active_tkt_id"] = tkt_activo["id"]
                st.session_state["drawer_screenshots_pegados"] = []
                st.session_state["drawer_last_pasted_ts"] = None

            tkt_id = tkt_activo["id"]
            folio = tkt_activo.get("folio", "BUG-???")

            # 4. Selector modificable del Estado del Ticket
            estados_disponibles = ["Abierto", "En Revisión", "Corregido", "Bajo Consideración", "Validado", "Descartado"]
            curr_estado = tkt_activo.get("estado", "Abierto")
            idx_estado = estados_disponibles.index(curr_estado) if curr_estado in estados_disponibles else 0

            nuevo_estado = st.selectbox(
                "Estado del ticket:",
                options=estados_disponibles,
                index=idx_estado,
                key=f"drawer_sel_estado_{tkt_id}",
                help="Modifica el estatus para pasar de Corregido a En Revisión o viceversa."
            )

            # 5. Selectores de Pestañas y Categorías a Ancho Completo (sin truncamientos visuales)
            curr_tabs = tkt_activo.get("tabs_afectadas") or ["General"]
            if not isinstance(curr_tabs, list):
                curr_tabs = [curr_tabs]
            curr_tabs_valid = [x for x in curr_tabs if x in PESTANAS_MODULOS] or ["General"]

            nuevas_tabs = st.multiselect(
                "Pestañas afectadas:",
                options=PESTANAS_MODULOS,
                default=curr_tabs_valid,
                key=f"drawer_sel_tabs_{tkt_id}",
                help="Pestañas donde se presenta la anomalía."
            )

            curr_cat = tkt_activo.get("categoria", "Interfaz y Visualización")
            idx_cat = CATEGORIAS_BUGS.index(curr_cat) if curr_cat in CATEGORIAS_BUGS else 0

            nueva_cat = st.selectbox(
                "Categoría del problema:",
                options=CATEGORIAS_BUGS,
                index=idx_cat,
                key=f"drawer_sel_cat_{tkt_id}",
                help="Clasificación temática del fallo."
            )

        # Contenedor unificado y scrolleable para Descripción, Notas y Comentarios
        with st.container(key="drawer_textareas_block", height=350):
            # 6. Descripción del Usuario (Modificable / Editable)
            nueva_desc = st.text_area(
                "Descripción detallada del problema (Editable):",
                value=tkt_activo.get("descripcion") or "",
                height=140,
                key=f"drawer_txt_desc_{tkt_id}",
                help="Edita o clarifica detalles para que el agente comprenda con exactitud la falla."
            )

            # 7. Notas de Resolución / Bitácora Técnica del Parche (Editable)
            nuevas_notas = st.text_area(
                "Notas de resolución / Bitácora técnica del parche:",
                value=tkt_activo.get("notas_resolucion") or "",
                placeholder="Documenta la causa raíz, archivos modificados o notas técnicas acumulativas...",
                height=180,
                key=f"drawer_txt_notas_{tkt_id}",
                help="Bitácora técnica de soluciones del agente. Admite longitud ilimitada."
            )

            # 8. Comentarios de Revisión / Feedback para Iteración
            nuevos_comentarios = st.text_area(
                "💬 Comentarios de Revisión / Feedback para Iteración:",
                value=tkt_activo.get("comentarios_revision") or "",
                placeholder="Escribe aquí tus observaciones o correcciones cuando regreses el ticket a 'En Revisión'...",
                height=120,
                key=f"drawer_txt_comentarios_{tkt_id}",
                help="Este comentario sobreescribirá el anterior al guardar para mantener la iteración limpia y enfocada."
            )

        # Muestra de evidencias actuales si existen
        evidencias_previas = tkt_activo.get("archivos_adjuntos") or []
        if evidencias_previas:
            badges_html = " ".join([
                f'<span style="background: #f1f5f9; color: #475569; padding: 2px 7px; border-radius: 4px; font-size: 0.76rem; border: 1px solid #cbd5e1;">📎 {p.split("/")[-1]}</span>'
                for p in evidencias_previas
            ])
            st.markdown(
                f"""
                <div style="margin-top: 4px; margin-bottom: 8px;">
                    <div style="font-size: 0.8rem; font-weight: 600; color: #64748b; margin-bottom: 3px;">Evidencias actuales registradas ({len(evidencias_previas)}):</div>
                    <div style="display: flex; gap: 6px; flex-wrap: wrap;">{badges_html}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # 9. Evidencias Adjuntas y Screenshots (Layout 50% / 50% Compacto y Nivelado)
        col_archivos, col_clipboard = st.columns(2)

        with col_archivos:
            archivos_nuevos = st.file_uploader(
                "Evidencias (archivos):",
                type=["png", "jpg", "jpeg", "pdf", "xlsx", "csv"],
                accept_multiple_files=True,
                help="Si subes nuevos archivos, reemplazarán las evidencias viejas en Storage.",
                key=f"drawer_uploader_{tkt_id}",
            )
            if archivos_nuevos:
                st.caption(f"📎 **{len(archivos_nuevos)}** nuevo(s).")

        with col_clipboard:
            st.markdown(
                """
                <div style="height: 24px; display: flex; align-items: center; gap: 4px; margin-bottom: 4px;">
                    <span style="font-size: 0.875rem; font-weight: 400; color: #31333f; line-height: 24px;">
                        Screenshots:
                    </span>
                    <span title="Haz clic en el recuadro o presiona Ctrl + V para pegar imágenes directamente desde tu portapapeles." style="cursor: help; color: #64748b; font-size: 0.85rem;">ℹ️</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            pasted_data_drawer = clipboard_paste_box(compact=True, key=f"drawer_clipboard_component_{tkt_id}")

            if "drawer_screenshots_pegados" not in st.session_state:
                st.session_state["drawer_screenshots_pegados"] = []

            if pasted_data_drawer and isinstance(pasted_data_drawer, dict) and "dataUrl" in pasted_data_drawer:
                ts_d = pasted_data_drawer.get("timestamp")
                if ts_d and st.session_state.get("drawer_last_pasted_ts") != ts_d:
                    st.session_state["drawer_last_pasted_ts"] = ts_d
                    data_url_d = pasted_data_drawer["dataUrl"]
                    try:
                        header_d, encoded_d = data_url_d.split(";base64,", 1)
                        b_data_d = base64.b64decode(encoded_d)
                        idx_d = len(st.session_state["drawer_screenshots_pegados"]) + 1
                        st.session_state["drawer_screenshots_pegados"].append({
                            "id": str(uuid.uuid4())[:8],
                            "nombre": f"screenshot_{idx_d}.png",
                            "bytes": b_data_d,
                            "size_kb": round(len(b_data_d) / 1024, 1),
                        })
                    except Exception as ex_b64_d:
                        st.error(f"Error procesando captura: {ex_b64_d}")

            if st.session_state["drawer_screenshots_pegados"]:
                st.caption(f"📸 **{len(st.session_state['drawer_screenshots_pegados'])}** captura(s) del portapapeles:")
                num_sc_d = len(st.session_state["drawer_screenshots_pegados"])
                cont_sc_d = st.container(height=68, border=False) if num_sc_d > 1 else st.container()
                with cont_sc_d:
                    for s in list(st.session_state["drawer_screenshots_pegados"]):
                        c_txt_d, c_del_d = st.columns([3.6, 1.2])
                        with c_txt_d:
                            st.caption(f"🖼️ **{s['nombre']}** ({s['size_kb']} KB)")
                        with c_del_d:
                            st.button(
                                "✕",
                                key=f"del_sc_drawer_{s['id']}",
                                help=f"Eliminar {s['nombre']}",
                                on_click=_cb_eliminar_screenshot_drawer,
                                args=(s["id"],),
                            )

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # 10. Botones de Pie (Layout 50% / 50%)
        col_cancelar, col_actualizar = st.columns(2)
        with col_cancelar:
            st.button("Cancelar", use_container_width=True, key=f"btn_drawer_cancel_{tkt_id}", on_click=_cb_cerrar_drawer_tracking)

        with col_actualizar:
            if st.button("💾 Actualizar Reporte", type="primary", use_container_width=True, key=f"btn_drawer_update_{tkt_id}"):
                desc_limpia = (nueva_desc or "").strip()
                if not desc_limpia:
                    st.error("⚠️ La descripción detallada del problema no puede estar vacía.")
                    return

                if not nuevas_tabs:
                    st.error("⚠️ Selecciona al menos una pestaña afectada.")
                    return

                with st.spinner(f"Actualizando {folio}..."):
                    try:
                        rutas_finales = list(tkt_activo.get("archivos_adjuntos") or [])
                        nuevos_scs = st.session_state.get("drawer_screenshots_pegados", [])
                        hay_nuevas_evidencias = bool(archivos_nuevos) or bool(nuevos_scs)

                        # "Plot Twist": Si se adjuntan nuevas evidencias, purgar archivos viejos de Storage primero
                        if hay_nuevas_evidencias:
                            if rutas_finales:
                                try:
                                    supabase.storage.from_("bugs").remove(rutas_finales)
                                except Exception as ex_purge:
                                    st.warning(f"Aviso al limpiar evidencias previas: {ex_purge}")
                            rutas_finales = []

                            # Subir nuevos archivos tradicionales
                            if archivos_nuevos:
                                for f in archivos_nuevos:
                                    nombre_limpio = f.name.replace(" ", "_")
                                    ruta_storage = f"{folio}/{nombre_limpio}"
                                    bytes_f = f.getvalue()
                                    content_type = f.type or "application/octet-stream"
                                    try:
                                        supabase.storage.from_("bugs").upload(
                                            ruta_storage,
                                            bytes_f,
                                            file_options={"content-type": content_type, "upsert": "true"},
                                        )
                                        rutas_finales.append(ruta_storage)
                                    except Exception as ex_up_f:
                                        st.warning(f"No se pudo subir {f.name}: {ex_up_f}")

                            # Subir capturas del portapapeles
                            if nuevos_scs:
                                for s in nuevos_scs:
                                    ruta_storage = f"{folio}/{s['nombre']}"
                                    try:
                                        supabase.storage.from_("bugs").upload(
                                            ruta_storage,
                                            s["bytes"],
                                            file_options={"content-type": "image/png", "upsert": "true"},
                                        )
                                        rutas_finales.append(ruta_storage)
                                    except Exception as ex_up_s:
                                        st.warning(f"No se pudo subir {s['nombre']}: {ex_up_s}")

                        # Actualizar registro en base de datos
                        update_payload = {
                            "estado": nuevo_estado,
                            "tabs_afectadas": nuevas_tabs,
                            "categoria": nueva_cat,
                            "descripcion": desc_limpia,
                            "notas_resolucion": (nuevas_notas or "").strip() or None,
                            "comentarios_revision": (nuevos_comentarios or "").strip() or None,
                            "archivos_adjuntos": rutas_finales,
                            "updated_at": datetime.now().isoformat(),
                        }

                        supabase.table("reportes_bugs").update(update_payload).eq("id", tkt_id).execute()

                        # Limpieza de estado local
                        st.session_state["drawer_screenshots_pegados"] = []
                        st.session_state["drawer_last_pasted_ts"] = None
                        st.session_state["drawer_active_tkt_id"] = None

                        st.success(f"Reporte {folio} actualizado exitosamente!")
                        time.sleep(0.5)
                        st.rerun(scope="app")

                    except Exception as ex_up_all:
                        st.error(f"❌ Error al actualizar el reporte de bug: {ex_up_all}")
