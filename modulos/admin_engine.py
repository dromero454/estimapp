"""
Módulo Administrativo (Super Admin Dashboard) para Estimapp
===========================================================
Provee telemetría global, directorio multiusuario, explorador y depuración de Supabase Storage,
y detector de evidencias huérfanas.
Requiere privilegios de Superadministrador (es_admin == True).
"""

import math
from datetime import datetime
import pandas as pd
import streamlit as st
from supabase import Client


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
    tab_telemetria, tab_usuarios, tab_storage, tab_huerfanas = st.tabs([
        "📊 Métricas y Telemetría",
        "👥 Directorio de Usuarios",
        "🗄️ Explorador de Storage",
        "🔍 Detección de Huérfanos"
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
            kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
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
                "perfiles": "Perfiles y metadatos de residentes y administradores"
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

                rol_badge = "🛡️ Superadministrador" if u.get("es_admin") else "👷 Residente de Obra"
                
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

        bytes_evidencias = sum(a.get("size_bytes") or 0 for a in archivos_evidencias)
        bytes_plantillas = sum(a.get("size_bytes") or 0 for a in archivos_plantillas)
        bytes_totales = bytes_evidencias + bytes_plantillas

        st_c1, st_c2, st_c3 = st.columns(3)
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
                label="💾 Espacio Total Ocupado",
                value=format_bytes(bytes_totales),
                delta=f"{len(archivos_raw)} archivos totales",
                delta_color="off"
            )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        filtro_bucket = st.radio(
            "Filtrar archivos por bucket:",
            ["Todos", "evidencias", "plantillas"],
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
