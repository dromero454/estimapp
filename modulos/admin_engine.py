"""
Módulo Administrativo (Super Admin Dashboard) para Estimapp
===========================================================
Provee telemetría global, directorio multiusuario, explorador y depuración de Supabase Storage,
y detector de evidencias huérfanas.
Requiere privilegios de Superadministrador (es_admin == True).
"""

import math
import time
from datetime import datetime
import pandas as pd
import streamlit as st
from supabase import Client

# Cuotas configurables para telemetría
MAX_DB_QUOTA_MB = 500
MAX_STORAGE_QUOTA_MB = 1000

# Arquitectura extensible de roles (preparada para añadir auditor, ejecutivo, etc.)
ROLES_CONFIGURABLES = [
    ("superadmin", "🛡️ Superadministrador"),
    ("residente", "👷 Residente de Obra"),
    # ("auditor", "🔍 Auditor"),
    # ("ejecutivo", "💼 Ejecutivo"),
]
ROLES_BADGES = {
    "superadmin": "🛡️ Superadministrador",
    "residente": "👷 Residente de Obra",
    "auditor": "🔍 Auditor",
    "ejecutivo": "💼 Ejecutivo",
}


def format_bytes(size_bytes: int) -> str:
    """Convierte un tamaño en bytes a una representación legible (KB, MB, GB)."""
    if size_bytes is None or size_bytes <= 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


def format_fecha(iso_str: str) -> str:
    """Formatea una fecha ISO a formato local YYYY-MM-DD HH:MM."""
    if not iso_str:
        return "-"
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str[:16].replace("T", " ")


def compactar_y_sincronizar_folios_bugs(supabase: Client) -> dict:
    """
    Compacta los folios de reportes_bugs para que sean estrictamente correlativos
    iniciando en BUG-001 sin huecos, sincronizando las rutas de archivos en Storage.
    """
    try:
        res = supabase.rpc("admin_compactar_folios_bugs").execute()
        datos = res.data or {}
        cambios = datos.get("cambios") or []
        for cambio in cambios:
            old_fol = cambio.get("old_folio")
            new_fol = cambio.get("new_folio")
            archivos_old = cambio.get("archivos_adjuntos") or []
            tkt_id = cambio.get("id")

            if archivos_old and old_fol and new_fol:
                archivos_new = []
                for ruta_vieja in archivos_old:
                    if ruta_vieja.startswith(f"{old_fol}/"):
                        nombre_archivo = ruta_vieja[len(f"{old_fol}/"):]
                        ruta_nueva = f"{new_fol}/{nombre_archivo}"
                        try:
                            supabase.storage.from_("bugs").move(ruta_vieja, ruta_nueva)
                            archivos_new.append(ruta_nueva)
                        except Exception:
                            archivos_new.append(ruta_vieja)
                    else:
                        archivos_new.append(ruta_vieja)

                supabase.table("reportes_bugs").update({"archivos_adjuntos": archivos_new}).eq("id", tkt_id).execute()
        return datos
    except Exception as e:
        return {"error": str(e)}


def render_admin_dashboard(supabase: Client):
    """
    Renderiza la consola de Superadministrador completa de Estimapp.
    """
    # Verificación estricta de privilegios en sesión
    if not st.session_state.get("es_admin"):
        st.error("⛔ Acceso restringido: Se requieren privilegios de Superadministrador para visualizar esta consola.")
        if st.button("⬅️ Volver a la aplicación"):
            st.session_state["vista_actual"] = "obra"
            st.rerun()
        st.stop()

    # Barra superior de la consola con botón de regreso
    col_titulo, col_volver = st.columns([3, 1])
    with col_titulo:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 12px; margin-top: 4px; margin-bottom: 8px;">
            <h2 style="margin: 0; padding: 0; font-size: 1.85rem; font-weight: 700; color: #0f172a;">
                🛡️ Consola de Superadministrador
            </h2>
            <span style="background: #e0e7ff; color: #4338ca; font-size: 0.72rem; font-weight: 700; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.05em; border: 1px solid #c7d2fe;">
                Super Admin
            </span>
        </div>
        <p style="margin: 0 0 16px 0; color: #64748b; font-size: 0.95rem;">
            Telemetría global en tiempo real, directorio de cuentas registradas y auditoría de almacenamiento de Estimapp.
        </p>
        """, unsafe_allow_html=True)
    with col_volver:
        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if st.button("⬅️ Volver a la aplicación", type="secondary", use_container_width=True, key="btn_volver_a_obra", help="Regresar a las pestañas de control de obra y residente"):
            st.session_state["vista_actual"] = "obra"
            st.rerun()

    # Pestañas de la consola administrativa
    tab_telemetria, tab_usuarios, tab_storage, tab_huerfanas, tab_incidencias = st.tabs([
        "📊 Métricas y Telemetría",
        "👥 Directorio de Usuarios",
        "🗄️ Explorador de Storage",
        "🔍 Detección de Huérfanos",
        "🐞 Gestión de Incidencias"
    ])

    # =============================================================
    # SECCIÓN A: MÉTRICAS Y TELEMETRÍA GLOBAL DEL SISTEMA
    # =============================================================
    with tab_telemetria:
        st.markdown("#### Telemetría Operativa y Balance de la Base de Datos")
        
        try:
            res_telem = supabase.rpc("get_admin_telemetria").execute()
            data_telem = res_telem.data or {}
        except Exception as e:
            st.error(f"Error al obtener métricas del servidor: {e}")
            data_telem = {}

        if data_telem:
            kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
            with kpi_col1:
                st.metric(
                    label="👥 Usuarios Registrados",
                    value=data_telem.get("total_usuarios", 0),
                    help="Cuentas activas en auth.users"
                )
            with kpi_col2:
                st.metric(
                    label="🏢 Proyectos Creados",
                    value=data_telem.get("total_proyectos", 0),
                    help="Contratos de obra pública y privada registrados"
                )
            with kpi_col3:
                st.metric(
                    label="📑 Estimaciones Oficiales",
                    value=data_telem.get("total_estimaciones", 0),
                    help="Periodos de estimación acumulados en el sistema"
                )
            with kpi_col4:
                st.metric(
                    label="📐 Mediciones en Campo",
                    value=data_telem.get("total_mediciones", 0),
                    help="Generadores de obra y registros fotográficos"
                )
            with kpi_col5:
                db_bytes = data_telem.get("db_size_bytes", 0)
                db_gb = db_bytes / (1000.0 ** 3)
                db_quota_gb = MAX_DB_QUOTA_MB / 1000.0
                db_mb = db_bytes / (1024.0 * 1024.0)
                pct_db = (db_mb / MAX_DB_QUOTA_MB) * 100.0 if MAX_DB_QUOTA_MB > 0 else 0.0
                st.metric(
                    label="💾 Base de Datos",
                    value=f"{db_gb:.2f} GB / {db_quota_gb:.2f} GB",
                    delta=f"{db_mb:.1f} MB ({pct_db:.1f}% cuota)",
                    delta_color="off",
                    help=f"Consumo físico reportado por pg_database_size: {db_bytes:,} bytes. Cuota máxima configurada: {MAX_DB_QUOTA_MB} MB."
                )

            st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
            st.markdown("##### Desglose de Registros por Tabla")

            conteos = data_telem.get("tabla_conteos", {})
            descripciones_tablas = {
                "proyectos": "Contratos y obras de infraestructura",
                "catalogo_conceptos": "Conceptos contratados por proyecto",
                "mediciones_campo": "Generadores de obra y mediciones de avance",
                "estimaciones": "Periodos de cobro y estimaciones generadas",
                "biblioteca_conceptos": "Catálogo maestro institucional (IMSS, PJF, etc.)",
                "instituciones": "Dependencias e instituciones dadas de alta",
                "perfiles": "Perfiles y metadatos de residentes y administradores",
                "reportes_bugs": "Tickets de soporte, reportes de incidencias y bitácora de parches",
                "proveedores": "Directorio de proveedores y casas de materiales",
                "personal_obra": "Directorio de cuadrillas, maestros y destajistas",
                "insumos_concepto": "Desglose fino de insumos y composición APU",
                "hitos_cobro": "Hitos financieros y cobro comercial de proyectos",
                "telemetria_clima": "Telemetría meteorológica histórica de periodos (Open-Meteo)",
            }

            rows_conteos = []
            total_filas = 0
            for tabla, count in conteos.items():
                total_filas += count
                rows_conteos.append({
                    "Tabla en Supabase": f"`public.{tabla}`",
                    "Descripción": descripciones_tablas.get(tabla, "Tabla del sistema"),
                    "Total Registros": count
                })

            df_conteos = pd.DataFrame(rows_conteos)
            if not df_conteos.empty:
                df_conteos = df_conteos.sort_values(by="Total Registros", ascending=False)
                st.dataframe(df_conteos, use_container_width=True, hide_index=True)
                st.caption(f"Total de registros activos en la base de datos relacional: **{total_filas:,} filas**.")
            else:
                st.info("No se encontraron registros en las tablas.")

            # --- Mantenimiento / Vaciado Controlado de Tablas ---
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            with st.expander("🛠️ Mantenimiento / Vaciado de Tablas", expanded=False):
                st.markdown("""
                <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px; margin-bottom: 14px;">
                    <p style="color: #991b1b; font-weight: 600; margin: 0 0 4px 0; font-size: 0.95rem;">
                        ⚠️ Zona Crítica: Purga Controlada de Base de Datos
                    </p>
                    <p style="color: #7f1d1d; margin: 0; font-size: 0.85rem;">
                        Esta herramienta vacía los registros de las tablas seleccionadas preservando estrictamente el orden de integridad referencial. Las cuentas de Superadministrador están protegidas permanentemente contra eliminación.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                tablas_disponibles = [
                    "reportes_bugs",
                    "telemetria_clima",
                    "mediciones_campo",
                    "insumos_concepto",
                    "hitos_cobro",
                    "estimaciones",
                    "catalogo_conceptos",
                    "proyectos",
                    "personal_obra",
                    "proveedores",
                    "biblioteca_conceptos",
                    "instituciones",
                    "perfiles",
                ]

                col_chk_all, _ = st.columns([2, 1])
                with col_chk_all:
                    chk_todas = st.checkbox(
                        "⚠️ Seleccionar todas las tablas",
                        key="admin_vaciado_chk_todas"
                    )

                tablas_seleccionadas = st.multiselect(
                    "Seleccionar tablas a vaciar:",
                    options=tablas_disponibles,
                    default=tablas_disponibles if chk_todas else [],
                    format_func=lambda t: f"public.{t} ({conteos.get(t, 0):,} registros)",
                    key="admin_vaciado_tablas_multiselect",
                    disabled=chk_todas
                )

                tablas_efectivas = tablas_disponibles if chk_todas else tablas_seleccionadas

                st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
                confirm_txt = st.text_input(
                    "Para proceder, escribe exactamente la palabra CONFIRMAR:",
                    placeholder="Escribe CONFIRMAR",
                    key="admin_vaciado_input_confirm"
                )

                confirm_es_valida = (confirm_txt.strip() == "CONFIRMAR")
                if not confirm_es_valida and confirm_txt.strip():
                    st.caption("❌ La palabra ingresada no coincide exactamente con 'CONFIRMAR'.")

                btn_vaciar = st.button(
                    "🚨 Vaciar Tablas Seleccionadas",
                    type="primary",
                    key="btn_vaciar_tablas_action",
                    disabled=(not confirm_es_valida or not tablas_efectivas)
                )

                if btn_vaciar:
                    if not confirm_es_valida:
                        st.error("Debes ingresar exactamente 'CONFIRMAR' para autorizar el vaciado.")
                    elif not tablas_efectivas:
                        st.warning("Debes seleccionar al menos una tabla para vaciar.")
                    else:
                        try:
                            with st.spinner("Vaciando tablas seleccionadas respetando dependencias referenciales..."):
                                # 1. Ejecutar vaciado transaccional seguro en PostgreSQL
                                res_vac = supabase.rpc("admin_truncate_tables", {"p_tables": tablas_efectivas}).execute()
                                conteos_purgados = res_vac.data or {}
                                total_purgado = sum(conteos_purgados.values()) if isinstance(conteos_purgados, dict) else 0

                                # 2. Solo tras confirmarse el vaciado en BD, purgar las evidencias asociadas en el bucket 'bugs'
                                if "reportes_bugs" in tablas_efectivas:
                                    try:
                                        res_bugs_storage = supabase.rpc("get_admin_storage_files").execute()
                                        archivos_bugs = [a.get("name") for a in (res_bugs_storage.data or []) if a.get("bucket_id") == "bugs"]
                                        if archivos_bugs:
                                            for i in range(0, len(archivos_bugs), 50):
                                                supabase.storage.from_("bugs").remove(archivos_bugs[i:i+50])
                                    except Exception as ex_b_stor:
                                        st.warning(f"Aviso al limpiar evidencias del bucket 'bugs': {ex_b_stor}")

                                st.success(f"✅ Vaciado completado exitosamente. Se eliminaron **{total_purgado:,}** registros.")
                                if isinstance(conteos_purgados, dict) and conteos_purgados:
                                    st.json(conteos_purgados)
                                time.sleep(1.5)
                                st.rerun()
                        except Exception as ex_vac:
                            st.error(f"Error al vaciar las tablas seleccionadas: {ex_vac}")
        else:
            st.warning("No se pudo cargar la telemetría del sistema.")

    # =============================================================
    # SECCIÓN B: DIRECTORIO DE USUARIOS
    # =============================================================
    with tab_usuarios:
        st.markdown("#### Directorio General de Usuarios Registrados")
        st.caption("Consulta centralizada de perfiles y actividad de residentes sin exponer credenciales sensibles ni hashes.")

        try:
            res_users = supabase.rpc("get_admin_directorio_usuarios").execute()
            usuarios_raw = res_users.data or []
        except Exception as e:
            st.error(f"Error al consultar el directorio de usuarios: {e}")
            usuarios_raw = []

        if usuarios_raw:
            col_search, col_stats = st.columns([2, 1])
            with col_search:
                filtro_texto = st.text_input(
                    "🔍 Filtrar por nombre, correo o empresa:",
                    placeholder="Escribe para buscar...",
                    key="filtro_directorio_admin"
                )
            with col_stats:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                st.write(f"Mostrando **{len(usuarios_raw)}** cuentas registradas.")

            rows_usr = []
            for u in usuarios_raw:
                nom_comp = f"{u.get('nombre') or ''} {u.get('apellido_paterno') or ''} {u.get('apellido_materno') or ''}".strip()
                if not nom_comp:
                    nom_comp = (u.get("email") or "").split("@")[0]

                rol_actual_str = u.get("rol") or ("superadmin" if u.get("es_admin") else "residente")
                rol_badge = ROLES_BADGES.get(rol_actual_str, "🛡️ Superadministrador" if u.get("es_admin") else "👷 Residente de Obra")
                
                rows_usr.append({
                    "Nombre": nom_comp,
                    "Correo Electrónico": u.get("email") or "-",
                    "Empresa / Despacho": u.get("empresa_despacho") or "Independiente",
                    "Rol": rol_badge,
                    "Proyectos Creados": u.get("proyectos_count", 0),
                    "Fecha de Registro": format_fecha(u.get("created_at"))
                })

            df_usuarios = pd.DataFrame(rows_usr)

            if filtro_texto.strip():
                term = filtro_texto.strip().lower()
                df_usuarios = df_usuarios[
                    df_usuarios["Nombre"].str.lower().str.contains(term) |
                    df_usuarios["Correo Electrónico"].str.lower().str.contains(term) |
                    df_usuarios["Empresa / Despacho"].str.lower().str.contains(term)
                ]

            st.dataframe(df_usuarios, use_container_width=True, hide_index=True)

            user_actual_id = st.session_state.get("user").id if st.session_state.get("user") else None

            # --- Modificación y Asignación Extensible de Roles ---
            st.markdown("---")
            st.markdown("##### 🎭 Modificación y Asignación de Roles")
            st.caption("Asigna o actualiza los privilegios de acceso del sistema para cualquier cuenta registrada.")

            opciones_usr_roles = []
            usr_role_dict = {}
            for u in usuarios_raw:
                nom = f"{u.get('nombre') or ''} {u.get('apellido_paterno') or ''}".strip()
                if not nom:
                    nom = (u.get("email") or "").split("@")[0]
                r_act = u.get("rol", "residente")
                r_lbl = ROLES_BADGES.get(r_act, r_act)
                lbl = f"{nom} ({u.get('email')}) — Rol actual: {r_lbl}"
                opciones_usr_roles.append(lbl)
                usr_role_dict[lbl] = u

            col_sel_u, col_sel_r, col_btn_r = st.columns([2, 1, 1])
            with col_sel_u:
                usr_seleccionado_label = st.selectbox(
                    "Seleccionar usuario para cambiar rol:",
                    options=opciones_usr_roles,
                    key="admin_role_select_user"
                )

            target_usr_obj = usr_role_dict.get(usr_seleccionado_label, {})
            rol_actual_target = target_usr_obj.get("rol", "residente")
            roles_keys = [r[0] for r in ROLES_CONFIGURABLES]
            rol_default_idx = roles_keys.index(rol_actual_target) if rol_actual_target in roles_keys else 0

            with col_sel_r:
                nuevo_rol_sel = st.selectbox(
                    "Nuevo rol asignado:",
                    options=roles_keys,
                    index=rol_default_idx,
                    format_func=lambda r: next((item[1] for item in ROLES_CONFIGURABLES if item[0] == r), r),
                    key="admin_role_select_new"
                )

            with col_btn_r:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                btn_guardar_rol = st.button("💾 Guardar Rol", type="primary", use_container_width=True, key="btn_guardar_nuevo_rol")

            if btn_guardar_rol:
                if not target_usr_obj:
                    st.warning("Selecciona un usuario válido.")
                elif target_usr_obj.get("id") == user_actual_id and nuevo_rol_sel != "superadmin":
                    st.error("⛔ No puedes revocar tus propios privilegios de Superadministrador.")
                else:
                    try:
                        with st.spinner("Actualizando rol en la base de datos..."):
                            supabase.rpc("admin_update_user_role", {
                                "p_user_id": target_usr_obj["id"],
                                "p_nuevo_rol": nuevo_rol_sel
                            }).execute()
                            st.success(f"✅ Se actualizó el rol de **{target_usr_obj.get('email')}** a **'{nuevo_rol_sel}'** exitosamente.")
                            st.rerun()
                    except Exception as ex_r:
                        st.error(f"Error al actualizar el rol: {ex_r}")

            # --- Mecanismo de Borrado Selectivo y Masivo de Usuarios (No Administradores) ---
            st.markdown("---")
            st.markdown("##### 🗑️ Gestión de Eliminación de Usuarios")

            user_actual_id = st.session_state.get("user").id if st.session_state.get("user") else None
            # Filtrar usuarios eliminables: estrictamente los que NO sean administradores y no sea la cuenta actual
            usuarios_eliminables = [
                u for u in usuarios_raw 
                if not u.get("es_admin") and str(u.get("id")) != str(user_actual_id)
            ]

            if not usuarios_eliminables:
                st.info("ℹ️ No hay usuarios no-administradores disponibles para eliminar.")
            else:
                opciones_eliminacion_usr = []
                usr_map = {}
                for u in usuarios_eliminables:
                    nom = f"{u.get('nombre') or ''} {u.get('apellido_paterno') or ''}".strip()
                    if not nom:
                        nom = (u.get("email") or "").split("@")[0]
                    emp = u.get("empresa_despacho") or "Independiente"
                    label = f"{nom} ({u.get('email')}) — {emp}"
                    opciones_eliminacion_usr.append(label)
                    usr_map[label] = u

                sel_usuarios = st.multiselect(
                    "Seleccionar usuarios a eliminar:",
                    options=opciones_eliminacion_usr,
                    key="admin_usuarios_multiselect"
                )

                del_all_usr_checked = st.checkbox(
                    "⚠️ Selecciona para eliminar todos los usuarios no administradores mostrados en la tabla.",
                    key="admin_usuarios_del_all_checkbox"
                )

                if st.button("Eliminar Seleccionados", type="primary", key="btn_eliminar_usuarios_action"):
                    targets_usr = []
                    if del_all_usr_checked:
                        targets_usr = usuarios_eliminables
                    elif sel_usuarios:
                        targets_usr = [usr_map[k] for k in sel_usuarios if k in usr_map]

                    if not targets_usr:
                        st.warning("⚠️ Debes seleccionar al menos un usuario del selector o marcar la casilla para eliminar todos los no administradores.")
                    else:
                        # Extraer IDs y garantizar que ninguno sea admin
                        ids_to_delete = [
                            u["id"] for u in targets_usr 
                            if not u.get("es_admin") and str(u.get("id")) != str(user_actual_id)
                        ]

                        if not ids_to_delete:
                            st.error("No se encontraron usuarios válidos o no administradores para eliminar.")
                        else:
                            try:
                                supabase.rpc("admin_delete_users", {"p_user_ids": ids_to_delete}).execute()
                                st.success(f"✅ Se eliminaron exitosamente **{len(ids_to_delete)}** usuario(s) y todos sus datos en cascada.")
                                st.rerun()
                            except Exception as ex_del:
                                st.error(f"Error al eliminar usuario(s): {ex_del}")
        else:
            st.info("No hay usuarios registrados disponibles.")

    # =============================================================
    # SECCIÓN C: EXPLORADOR DE STORAGE Y LIMPIEZA DE ARCHIVOS
    # =============================================================
    with tab_storage:
        st.markdown("#### Explorador de Storage y Limpieza de Archivos")
        st.caption("Supervisa el volumen de archivos en los buckets `evidencias` y `plantillas` con eliminación selectiva o masiva.")

        try:
            res_storage = supabase.rpc("get_admin_storage_files").execute()
            archivos_raw = res_storage.data or []
        except Exception as e:
            st.error(f"Error al consultar Supabase Storage: {e}")
            archivos_raw = []

        # Cálculo de métricas por bucket
        archivos_evidencias = [a for a in archivos_raw if a.get("bucket_id") == "evidencias"]
        archivos_plantillas = [a for a in archivos_raw if a.get("bucket_id") == "plantillas"]
        archivos_bugs = [a for a in archivos_raw if a.get("bucket_id") == "bugs"]

        bytes_evidencias = sum(a.get("size_bytes") or 0 for a in archivos_evidencias)
        bytes_plantillas = sum(a.get("size_bytes") or 0 for a in archivos_plantillas)
        bytes_bugs = sum(a.get("size_bytes") or 0 for a in archivos_bugs)
        bytes_totales = bytes_evidencias + bytes_plantillas + bytes_bugs

        st_c1, st_c2, st_c3, st_c4 = st.columns(4)
        with st_c1:
            st.metric(
                label="📁 Bucket 'evidencias'",
                value=f"{len(archivos_evidencias)} archivos",
                delta=format_bytes(bytes_evidencias),
                delta_color="off"
            )
        with st_c2:
            st.metric(
                label="📑 Bucket 'plantillas'",
                value=f"{len(archivos_plantillas)} archivos",
                delta=format_bytes(bytes_plantillas),
                delta_color="off"
            )
        with st_c3:
            st.metric(
                label="🐞 Bucket 'bugs'",
                value=f"{len(archivos_bugs)} archivos",
                delta=format_bytes(bytes_bugs),
                delta_color="off"
            )
        with st_c4:
            stor_gb = bytes_totales / (1000.0 ** 3)
            stor_quota_gb = MAX_STORAGE_QUOTA_MB / 1000.0
            st.metric(
                label="💾 Espacio Total Ocupado",
                value=f"{stor_gb:.3f} GB / {stor_quota_gb:.2f} GB",
                delta=f"{format_bytes(bytes_totales)} ({len(archivos_raw)} archivos)",
                delta_color="off",
                help=f"Almacenamiento total consumido en buckets de Supabase. Cuota máxima configurada: {MAX_STORAGE_QUOTA_MB} MB."
            )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        filtro_bucket = st.radio(
            "Filtrar archivos por bucket:",
            ["Todos", "evidencias", "plantillas", "bugs"],
            horizontal=True,
            key="filtro_storage_bucket"
        )

        archivos_mostrados = archivos_raw
        if filtro_bucket != "Todos":
            archivos_mostrados = [a for a in archivos_raw if a.get("bucket_id") == filtro_bucket]

        if archivos_mostrados:
            rows_files = []
            for f in archivos_mostrados:
                rows_files.append({
                    "Bucket": f.get("bucket_id"),
                    "Nombre de Archivo": f.get("name"),
                    "Tamaño": format_bytes(f.get("size_bytes") or 0),
                    "Fecha de Subida": format_fecha(f.get("created_at"))
                })
            df_files = pd.DataFrame(rows_files)
            st.dataframe(df_files, use_container_width=True, hide_index=True)

            # --- Mecanismo de Borrado Selectivo y Masivo ---
            st.markdown("---")
            st.markdown("##### 🗑️ Gestión de Eliminación de Archivos")

            opciones_eliminacion = [f"[{a['bucket_id']}] {a['name']}" for a in archivos_mostrados]
            archivos_dict = {f"[{a['bucket_id']}] {a['name']}": a for a in archivos_mostrados}

            sel_archivos = st.multiselect(
                "Seleccionar archivos a eliminar:",
                options=opciones_eliminacion,
                key="admin_storage_multiselect"
            )

            del_all_checked = st.checkbox(
                "⚠️ Selecciona para eliminar todos los archivos mostrados en la tabla.",
                key="admin_storage_del_all_checkbox"
            )

            # Botón de acción destacado
            if st.button("Eliminar Seleccionados", type="primary", key="btn_eliminar_storage_action"):
                archivos_a_borrar = []
                if del_all_checked:
                    archivos_a_borrar = archivos_mostrados
                elif sel_archivos:
                    archivos_a_borrar = [archivos_dict[k] for k in sel_archivos if k in archivos_dict]

                if not archivos_a_borrar:
                    st.warning("⚠️ Debes seleccionar al menos un archivo del selector o marcar la casilla para eliminar todos los mostrados.")
                else:
                    # Agrupar por bucket para ejecutar con el cliente oficial de Storage
                    agrupados = {}
                    for item in archivos_a_borrar:
                        b_id = item["bucket_id"]
                        if b_id not in agrupados:
                            agrupados[b_id] = []
                        agrupados[b_id].append(item["name"])

                    eliminados_total = 0
                    errores_borrado = []
                    for b_id, filenames in agrupados.items():
                        try:
                            # Lotes de 50 archivos para evitar saturación de request
                            for i in range(0, len(filenames), 50):
                                batch = filenames[i:i+50]
                                supabase.storage.from_(b_id).remove(batch)
                                eliminados_total += len(batch)
                        except Exception as ex_del:
                            errores_borrado.append(f"{b_id}: {ex_del}")

                    if eliminados_total > 0:
                        st.success(f"✅ Se eliminaron exitosamente **{eliminados_total}** archivo(s) de Supabase Storage.")
                        st.rerun()
                    if errores_borrado:
                        st.error("Ocurrió un error al eliminar algunos archivos: " + "; ".join(errores_borrado))
        else:
            st.info("No hay archivos en el bucket seleccionado.")

    # =============================================================
    # SECCIÓN D: DETECCIÓN DE HUÉRFANOS
    # =============================================================
    with tab_huerfanas:
        st.markdown("#### Detección de Evidencias Huérfanas")
        st.caption("Compara los archivos almacenados en el bucket `evidencias` contra las fotografías registradas en `mediciones_campo` para purgar imágenes sin asignación.")

        if st.button("🔍 Buscar evidencias huérfanas", key="btn_escanear_huerfanas", type="secondary"):
            st.session_state["admin_scan_huerfanas_realizado"] = True

        if st.session_state.get("admin_scan_huerfanas_realizado"):
            try:
                res_fotos = supabase.rpc("get_admin_fotos_registradas").execute()
                fotos_registradas = res_fotos.data or []

                res_storage_ev = supabase.rpc("get_admin_storage_files").execute()
                archivos_ev = [a for a in (res_storage_ev.data or []) if a.get("bucket_id") == "evidencias"]
            except Exception as e:
                st.error(f"Error al ejecutar el escaneo de evidencias: {e}")
                fotos_registradas = []
                archivos_ev = []

            # Extraer nombres base de las URLs registradas
            nombres_en_bd = set()
            for url in fotos_registradas:
                if url and isinstance(url, str):
                    # Extraer el nombre de archivo limpio
                    nombre_archivo = url.split("?")[0].split("/")[-1].strip()
                    if nombre_archivo:
                        nombres_en_bd.add(nombre_archivo)

            # Archivos huérfanos son los existentes en bucket pero que NO están en mediciones_campo
            huerfanos = [a for a in archivos_ev if a.get("name") not in nombres_en_bd]
            bytes_huerfanos = sum(h.get("size_bytes") or 0 for h in huerfanos)

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            if not huerfanos:
                st.success("🎉 ¡Excelente! No se detectaron evidencias huérfanas. Todas las fotografías en Storage pertenecen a mediciones activas.")
            else:
                st.warning(f"⚠️ Se detectaron **{len(huerfanos)} archivo(s) huérfano(s)** en el bucket 'evidencias', consumiendo **{format_bytes(bytes_huerfanos)}** de almacenamiento no referenciado.")

                rows_h = []
                for h in huerfanos:
                    rows_h.append({
                        "Nombre del Archivo Huérfano": h.get("name"),
                        "Tamaño": format_bytes(h.get("size_bytes") or 0),
                        "Fecha de Creación": format_fecha(h.get("created_at"))
                    })
                df_h = pd.DataFrame(rows_h)
                st.dataframe(df_h, use_container_width=True, hide_index=True)

                # Mecanismo de eliminación selectiva o masiva de huérfanos
                st.markdown("##### 🗑️ Purga de Evidencias Huérfanas")
                opciones_h_del = [h["name"] for h in huerfanos]

                sel_huerfanos = st.multiselect(
                    "Seleccionar evidencias huérfanas a eliminar:",
                    options=opciones_h_del,
                    key="admin_huerfanas_multiselect"
                )

                del_all_h_checked = st.checkbox(
                    "⚠️ Selecciona para eliminar todas las evidencias huérfanas mostradas en la tabla.",
                    key="admin_huerfanas_del_all_checkbox"
                )

                if st.button("Eliminar Evidencias Huérfanas Seleccionadas", type="primary", key="btn_eliminar_huerfanas_action"):
                    targets_h = []
                    if del_all_h_checked:
                        targets_h = opciones_h_del
                    elif sel_huerfanos:
                        targets_h = sel_huerfanos

                    if not targets_h:
                        st.warning("⚠️ Selecciona al menos una evidencia huérfana o marca la casilla para eliminar todas.")
                    else:
                        try:
                            eliminadas_cnt = 0
                            for i in range(0, len(targets_h), 50):
                                batch = targets_h[i:i+50]
                                supabase.storage.from_("evidencias").remove(batch)
                                eliminadas_cnt += len(batch)

                            st.success(f"✅ Se purgaron exitosamente **{eliminadas_cnt}** evidencias huérfanas de Storage.")
                            st.rerun()
                        except Exception as ex_h:
                            st.error(f"Error al eliminar evidencias huérfanas: {ex_h}")

    # =============================================================
    # SECCIÓN E: GESTIÓN DE INCIDENCIAS Y SEGUIMIENTO DE BUGS
    # =============================================================
    with tab_incidencias:
        st.markdown("#### Gestión Integral de Incidencias y Bug Tracker")
        st.caption("Consola técnica de tickets reportados por residentes y administradores para auditoría, reproducción y resolución continua.")

        # Garantizar que los folios estén compactados correlativamente desde BUG-001 sin huecos
        compactar_y_sincronizar_folios_bugs(supabase)

        try:
            res_bugs = supabase.rpc("get_admin_reportes_bugs").execute()
            tickets_raw = res_bugs.data or []
        except Exception as e_b:
            st.error(f"Error al cargar reportes de bugs: {e_b}")
            tickets_raw = []

        total_tkts = len(tickets_raw)
        abiertos = sum(1 for t in tickets_raw if t.get("estado") == "Abierto")
        en_rev = sum(1 for t in tickets_raw if t.get("estado") == "En Revisión")
        corregidos = sum(1 for t in tickets_raw if t.get("estado") == "Corregido")
        validados = sum(1 for t in tickets_raw if t.get("estado") == "Validado")
        descartados = sum(1 for t in tickets_raw if t.get("estado") == "Descartado")

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1:
            st.metric("Total Tickets", total_tkts)
        with m2:
            st.metric("🔴 Abiertos", abiertos)
        with m3:
            st.metric("🟡 En Revisión", en_rev)
        with m4:
            st.metric("🟢 Corregidos", corregidos)
        with m5:
            st.metric("🔵 Validados", validados)
        with m6:
            st.metric("⚪ Descartados", descartados)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        # Filtros superiores
        col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 2])
        with col_f1:
            filtro_estado = st.selectbox(
                "Filtrar por Estado:",
                ["Todos", "Abierto", "En Revisión", "Corregido", "Validado", "Descartado"],
                key="filtro_incidencias_estado"
            )
        with col_f2:
            filtro_cat = st.selectbox(
                "Filtrar por Categoría:",
                ["Todas", "Interfaz y Visualización", "Cálculos y Fórmulas", "Exportación de Archivos", "Persistencia y Guardado", "Rendimiento", "Otro"],
                key="filtro_incidencias_categoria"
            )
        with col_f3:
            filtro_q = st.text_input(
                "Buscar por Folio, Correo o Descripción:",
                placeholder="Ej. BUG-001, @correo.com...",
                key="filtro_incidencias_q"
            )

        tickets_filtrados = tickets_raw
        if filtro_estado != "Todos":
            tickets_filtrados = [t for t in tickets_filtrados if t.get("estado") == filtro_estado]
        if filtro_cat != "Todas":
            tickets_filtrados = [t for t in tickets_filtrados if t.get("categoria") == filtro_cat]
        if filtro_q.strip():
            q_clean = filtro_q.strip().lower()
            tickets_filtrados = [
                t for t in tickets_filtrados
                if q_clean in (t.get("folio") or "").lower()
                or q_clean in (t.get("email") or "").lower()
                or q_clean in (t.get("descripcion") or "").lower()
            ]

        if not tickets_filtrados:
            st.info("ℹ️ No hay tickets de incidencias registrados con los criterios seleccionados.")
        else:
            # Tabla global de incidencias (9 columnas estrictamente ordenadas)
            rows_incidencias = []
            for t in tickets_filtrados:
                tabs_list = t.get("tabs_afectadas") or []
                tabs_str = ", ".join(tabs_list) if isinstance(tabs_list, list) else str(tabs_list)
                adjuntos = t.get("archivos_adjuntos") or []
                adj_str = f"{len(adjuntos)} archivo(s)" if adjuntos else "Sin adjuntos"
                desc_corta = (t.get("descripcion") or "").replace("\n", " ").strip()
                if len(desc_corta) > 75:
                    desc_corta = desc_corta[:72] + "..."

                usuario_display = t.get("email") or t.get("nombre") or "-"
                comentarios_raw = (t.get("comentarios_revision") or "").replace("\n", " ").strip()
                comentarios_corta = (comentarios_raw[:52] + "...") if len(comentarios_raw) > 55 else comentarios_raw

                rows_incidencias.append({
                    "Folio": t.get("folio"),
                    "Fecha de Creación": format_fecha(t.get("created_at")),
                    "Última Modificación": format_fecha(t.get("updated_at")),
                    "Usuario": usuario_display,
                    "Pestañas Afectadas": tabs_str,
                    "Categoría": t.get("categoria"),
                    "Estado": t.get("estado"),
                    "Evidencias": adj_str,
                    "Descripción": desc_corta,
                    "Comentarios": comentarios_corta or "-",
                })

            df_incidencias = pd.DataFrame(rows_incidencias)
            st.dataframe(df_incidencias, use_container_width=True, hide_index=True)

            # Panel de detalle y control por ticket
            st.markdown("---")
            st.markdown("##### 🛠️ Panel de Detalle y Resolución de Incidencia")

            opciones_tkt = [f"{t['folio']} — {t['categoria']} ({t['estado']}) | {t.get('email', '')}" for t in tickets_filtrados]
            tkt_map = {f"{t['folio']} — {t['categoria']} ({t['estado']}) | {t.get('email', '')}": t for t in tickets_filtrados}

            sel_label = st.selectbox(
                "Selecciona un ticket para gestionar su estado y notas técnicas:",
                options=opciones_tkt,
                key="sel_tkt_control_admin"
            )
            tkt_activo = tkt_map[sel_label]

            # Tarjeta de detalle de la incidencia estructurada en 2 columnas proporcionales
            with st.container(border=True):
                col_info, col_evidencias = st.columns([1.1, 0.9])

                # Columna Izquierda: Gestión y Resolución Técnica
                with col_info:
                    estado_badges = {
                        "Abierto": "🔴 Abierto",
                        "En Revisión": "🟡 En Revisión",
                        "Corregido": "🟢 Corregido",
                        "Validado": "🔵 Validado",
                        "Descartado": "⚪ Descartado",
                    }
                    badge_actual = estado_badges.get(tkt_activo.get("estado"), tkt_activo.get("estado"))

                    st.markdown(f"### Ticket: `{tkt_activo.get('folio')}` &nbsp; `{badge_actual}`")

                    tabs_badge_list = tkt_activo.get("tabs_afectadas") or []
                    tabs_str_fmt = ", ".join([f"`{tb}`" for tb in tabs_badge_list]) if isinstance(tabs_badge_list, list) else f"`{tabs_badge_list}`"

                    st.markdown(
                        f"""
                        <div style="font-size: 0.88rem; color: #475569; margin-bottom: 12px; line-height: 1.6;">
                            <b>👤 Reportado por:</b> {tkt_activo.get('nombre', '')} (<code>{tkt_activo.get('email', '')}</code>) — <i>{tkt_activo.get('empresa', 'Independiente')}</i><br>
                            <b>📅 Fecha de creación:</b> {format_fecha(tkt_activo.get('created_at'))} &nbsp;|&nbsp; 
                            <b>🔄 Última actualización:</b> {format_fecha(tkt_activo.get('updated_at'))}<br>
                            <b>🏷️ Categoría:</b> <code>{tkt_activo.get('categoria')}</code><br>
                            <b>📌 Pestañas afectadas:</b> {tabs_str_fmt}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    st.markdown("**📝 Descripción detallada del problema:**")
                    st.info(tkt_activo.get("descripcion") or "Sin descripción proporcionada.")

                    st.markdown("---")
                    st.markdown("##### ⚙️ Gestión y Resolución Técnica")

                    estados_disponibles = ["Abierto", "En Revisión", "Corregido", "Validado", "Descartado"]
                    curr_est_idx = estados_disponibles.index(tkt_activo["estado"]) if tkt_activo.get("estado") in estados_disponibles else 0

                    nuevo_est_val = st.selectbox(
                        "Actualizar estado del ticket:",
                        options=estados_disponibles,
                        index=curr_est_idx,
                        key=f"sel_nuevo_estado_{tkt_activo['id']}"
                    )

                    notas_resolucion_val = st.text_area(
                        "Notas de resolución / Bitácora técnica del parche:",
                        value=tkt_activo.get("notas_resolucion") or "",
                        placeholder="Documenta la causa raíz, archivos modificados o notas del parche...",
                        height=95,
                        key=f"txt_notas_resolucion_{tkt_activo['id']}"
                    )

                    comentarios_revision_val = st.text_area(
                        "💬 Comentarios de Revisión / Feedback para Iteración:",
                        value=tkt_activo.get("comentarios_revision") or "",
                        placeholder="Escribe aquí tus observaciones o correcciones cuando regreses el ticket a 'En Revisión'...",
                        height=85,
                        help="Espacio para registrar el feedback del usuario y mantener la iteración continua de resolución.",
                        key=f"txt_comentarios_revision_{tkt_activo['id']}"
                    )

                    if st.button("💾 Guardar Cambios del Ticket", type="primary", use_container_width=True, key=f"btn_guardar_ticket_{tkt_activo['id']}"):
                        try:
                            supabase.rpc("admin_update_reporte_bug", {
                                "p_id": tkt_activo["id"],
                                "p_estado": nuevo_est_val,
                                "p_notas": (notas_resolucion_val or "").strip(),
                                "p_comentarios": (comentarios_revision_val or "").strip()
                            }).execute()
                            st.success(f"✅ Ticket **{tkt_activo['folio']}** actualizado a '{nuevo_est_val}' exitosamente.")
                            time.sleep(1.0)
                            st.rerun()
                        except Exception as ex_up_tkt:
                            st.error(f"Error al actualizar ticket: {ex_up_tkt}")

                    # Zona de Peligro / Eliminación
                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                    with st.expander("⚠️ Zona de Peligro: Eliminar Incidencia", expanded=False):
                        st.caption("Esta acción eliminará de forma irreversible el ticket en la base de datos y todos sus archivos asociados en el bucket 'bugs' de Supabase Storage.")
                        confirm_del = st.checkbox(
                            f"Confirmo que deseo eliminar definitivamente el ticket {tkt_activo.get('folio')}",
                            key=f"chk_confirm_del_bug_{tkt_activo['id']}"
                        )
                        if st.button("🗑️ Eliminar este Ticket", type="secondary", disabled=not confirm_del, use_container_width=True, key=f"btn_del_bug_{tkt_activo['id']}"):
                            try:
                                # 1. Eliminar registro en BD primero (integridad transaccional)
                                supabase.table("reportes_bugs").delete().eq("id", tkt_activo["id"]).execute()

                                # 2. Solo tras confirmarse el borrado en BD, purgar archivos del bucket 'bugs'
                                archivos_a_borrar = tkt_activo.get("archivos_adjuntos") or []
                                if archivos_a_borrar:
                                    try:
                                        supabase.storage.from_("bugs").remove(archivos_a_borrar)
                                    except Exception as ex_rem_storage:
                                        st.warning(f"Aviso al eliminar del bucket: {ex_rem_storage}")

                                # 3. Reordenar y compactar folios correlativos (BUG-001 ... BUG-N) y reubicar archivos en Storage
                                compactar_y_sincronizar_folios_bugs(supabase)

                                st.success(f"🗑️ Ticket {tkt_activo.get('folio')} eliminado y folios compactados correctamente.")
                                time.sleep(1.0)
                                st.rerun()
                            except Exception as ex_del_db:
                                st.error(f"Error al eliminar ticket: {ex_del_db}")

                # Columna Derecha: Galería Inteligente de Evidencias
                with col_evidencias:
                    st.markdown("##### 📎 Galería Inteligente de Evidencias")
                    adjuntos_activos = tkt_activo.get("archivos_adjuntos") or []
                    if not adjuntos_activos:
                        st.info("ℹ️ Este ticket no cuenta con evidencias adjuntas.")
                    else:
                        # Clasificar según extensión
                        docs_list = []
                        imgs_list = []
                        for ruta_adj in adjuntos_activos:
                            nombre_f = ruta_adj.split("/")[-1]
                            ext = nombre_f.lower().split(".")[-1] if "." in nombre_f else ""
                            if ext in ["png", "jpg", "jpeg", "webp"]:
                                imgs_list.append((ruta_adj, nombre_f, ext))
                            else:
                                docs_list.append((ruta_adj, nombre_f, ext))

                        # Construcción de la galería scrolleable sincronizada en altura
                        html_galeria = [
                            '<div style="max-height: 535px; overflow-y: auto; overflow-x: hidden; padding-right: 6px; scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent;">'
                        ]

                        # Sección A: Documentos y Hojas de Cálculo
                        if docs_list:
                            html_galeria.append(f'<div style="font-weight: 600; font-size: 0.88rem; color: #334155; margin-bottom: 8px;">📄 Documentos y Archivos ({len(docs_list)}):</div>')
                            for ruta_adj, nombre_f, ext in docs_list:
                                url_pub = supabase.storage.from_("bugs").get_public_url(ruta_adj)
                                icono = "📊" if ext in ["xlsx", "xls", "csv"] else ("📑" if ext == "pdf" else "📁")
                                html_galeria.append(
                                    f'<div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 10px; margin-bottom: 8px; background: #f8fafc; display: flex; justify-content: space-between; align-items: center; gap: 8px;">'
                                    f'<div style="font-size: 0.84rem; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500;" title="{nombre_f}">'
                                    f'{icono} <b>{nombre_f}</b>'
                                    f'</div>'
                                    f'<a href="{url_pub}" target="_blank" download style="display: inline-block; padding: 3px 8px; font-size: 0.76rem; border-radius: 4px; background: #ffffff; color: #0284c7; text-decoration: none; border: 1px solid #cbd5e1; font-weight: 500; white-space: nowrap; flex-shrink: 0;">'
                                    f'📥 Descargar'
                                    f'</a>'
                                    f'</div>'
                                )
                            html_galeria.append('<div style="height: 6px;"></div>')

                        # Sección B: Capturas de Pantalla e Imágenes (Cuadrícula uniforme encajonada)
                        if imgs_list:
                            html_galeria.append(f'<div style="font-weight: 600; font-size: 0.88rem; color: #334155; margin-bottom: 8px;">🖼️ Capturas de Pantalla e Imágenes ({len(imgs_list)}):</div>')
                            html_galeria.append('<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 6px;">')
                            for ruta_adj, nombre_f, ext in imgs_list:
                                url_pub = supabase.storage.from_("bugs").get_public_url(ruta_adj)
                                html_galeria.append(
                                    f'<div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px; background: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.04); text-align: center;">'
                                    f'<div style="width: 100%; height: 150px; overflow: hidden; border-radius: 6px; background: #f1f5f9; display: flex; align-items: center; justify-content: center;">'
                                    f'<img src="{url_pub}" alt="{nombre_f}" style="width: 100%; height: 100%; object-fit: cover; display: block;" loading="lazy" />'
                                    f'</div>'
                                    f'<div style="font-size: 0.74rem; color: #64748b; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: center;" title="{nombre_f}">'
                                    f'{nombre_f}'
                                    f'</div>'
                                    f'<div style="text-align: center; margin-top: 3px; margin-bottom: 2px;">'
                                    f'<a href="{url_pub}" target="_blank" style="font-size: 0.74rem; color: #0284c7; text-decoration: none; font-weight: 600; display: inline-block;">'
                                    f'🔍 Ver en resolución completa'
                                    f'</a>'
                                    f'</div>'
                                    f'</div>'
                                )
                            html_galeria.append('</div>')

                        html_galeria.append('</div>')
                        st.markdown("".join(html_galeria), unsafe_allow_html=True)
