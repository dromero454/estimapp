import streamlit as st
import pandas as pd
from supabase import Client

GIROS_LIST = [
    "Materiales",
    "Fletes / Retiro",
    "Acabados",
    "Maquinaria",
    "Ferretería y Tlapalería",
    "Prefabricados",
    "Servicios e Instalaciones",
    "Otros"
]


def render_proveedores_tab(supabase: Client, user_id: str):
    """
    Renderiza la pestaña Tab 7: Directorio de Proveedores Comerciales.
    Permite el registro, edición de catálogos de suministro y subcontratos.
    """
    st.markdown("### Directorio de Proveedores Comerciales 🚚")
    st.caption("Directorio de casas de materiales, distribuidores, plantas de concreto, acarreos y servicios de subcontrato del despacho.")

    # Contador de versión para reseteo limpio de formularios
    if "proveedor_form_counter" not in st.session_state:
        st.session_state["proveedor_form_counter"] = 0
    pv_counter = st.session_state["proveedor_form_counter"]

    if "ed_proveedor_counter" not in st.session_state:
        st.session_state["ed_proveedor_counter"] = 0

    col_alta, col_baja = st.columns([1, 1])

    # -------------------------------------------------------------
    # SECCIÓN 1: FORMULARIO DE ALTA RÁPIDA
    # -------------------------------------------------------------
    with col_alta:
        with st.expander("➕ Registrar Nuevo Proveedor", expanded=False):
            with st.form(f"form_proveedor_{pv_counter}", clear_on_submit=True):
                nombre_comercial = st.text_input(
                    "Nombre Comercial / Razón Social *",
                    placeholder="Ej: Concretos Tolteca, Ferretera Central...",
                    key=f"prov_nombre_{pv_counter}"
                )

                c_con, c_tel = st.columns(2)
                with c_con:
                    contacto = st.text_input(
                        "Persona de Contacto / Asesor",
                        placeholder="Ej: Ing. Carlos Morales",
                        key=f"prov_contacto_{pv_counter}"
                    )
                with c_tel:
                    telefono = st.text_input(
                        "Teléfono / WhatsApp",
                        placeholder="Ej: 312 000 0000",
                        key=f"prov_tel_{pv_counter}"
                    )

                giro = st.selectbox(
                    "Giro Comercial *",
                    options=GIROS_LIST,
                    index=0,
                    key=f"prov_giro_{pv_counter}"
                )

                btn_guardar_prov = st.form_submit_button("Guardar Proveedor", type="primary", use_container_width=True)

                if btn_guardar_prov:
                    if not nombre_comercial or not nombre_comercial.strip():
                        st.error("⚠️ El nombre comercial o razón social es obligatorio.")
                    else:
                        try:
                            supabase.table("proveedores").insert({
                                "user_id": user_id,
                                "nombre_comercial": nombre_comercial.strip(),
                                "contacto": contacto.strip() if contacto else None,
                                "telefono": telefono.strip() if telefono else None,
                                "giro": giro
                            }).execute()

                            st.session_state["proveedor_form_counter"] += 1
                            st.success(f"✅ Proveedor '{nombre_comercial.strip()}' registrado exitosamente.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al registrar proveedor: {ex}")

    # -------------------------------------------------------------
    # SECCIÓN 2: CONSULTA DE PROVEEDORES ACTIVOS
    # -------------------------------------------------------------
    try:
        res_prov = supabase.table("proveedores")\
            .select("id, nombre_comercial, contacto, telefono, giro, created_at")\
            .eq("user_id", user_id)\
            .order("id")\
            .execute()
        proveedores_list = res_prov.data or []
    except Exception as ex_list:
        st.error(f"Error al consultar el directorio de proveedores: {ex_list}")
        proveedores_list = []

    # -------------------------------------------------------------
    # SECCIÓN 3: DAR DE BAJA PROVEEDOR (DEFENSIVO)
    # -------------------------------------------------------------
    with col_baja:
        with st.expander("🗑️ Dar de Baja Proveedor", expanded=False):
            if not proveedores_list:
                st.info("No hay proveedores registrados para dar de baja.")
            else:
                prov_dict_del = {
                    f"#{p['id']} — {p['nombre_comercial']} ({p.get('giro', 'Materiales')})": p["id"]
                    for p in proveedores_list
                }
                prov_sel_del = st.selectbox(
                    "Seleccionar comercio a dar de baja:",
                    options=list(prov_dict_del.keys()),
                    key=f"del_prov_sel_{pv_counter}"
                )
                st.caption("ℹ️ *Los insumos asociados en composiciones APU preservan sus descripciones y costos sin afectación (ON DELETE SET NULL).*")
                
                chk_del = st.checkbox(
                    "Confirmo la baja de este proveedor",
                    key=f"chk_del_prov_{pv_counter}"
                )
                btn_del = st.button(
                    "Eliminar Proveedor",
                    type="primary",
                    disabled=not chk_del,
                    key=f"btn_del_prov_action_{pv_counter}"
                )

                if btn_del and chk_del:
                    id_prov_del = prov_dict_del[prov_sel_del]
                    try:
                        supabase.table("proveedores").delete().eq("id", id_prov_del).execute()
                        st.session_state["proveedor_form_counter"] += 1
                        st.success("✅ Proveedor eliminado del directorio.")
                        st.rerun()
                    except Exception as ex_del:
                        st.error(f"Error al eliminar proveedor: {ex_del}")

    # -------------------------------------------------------------
    # SECCIÓN 4: VISUALIZACIÓN, BÚSQUEDA Y EDICIÓN INTERACTIVA
    # -------------------------------------------------------------
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    if not proveedores_list:
        st.info("🚚 Aún no has registrado proveedores o casas de materiales. Da de alta al primero usando el formulario superior.")
        return

    # Barra de búsqueda y filtrado ágil
    col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
    with col_s1:
        filtro_txt = st.text_input(
            "🔍 Buscar proveedor por razón social, contacto o teléfono:",
            placeholder="Escribe para buscar...",
            key="filtro_prov_txt"
        )
    with col_s2:
        filtro_giro = st.selectbox(
            "Filtrar por giro comercial:",
            options=["Todos"] + GIROS_LIST,
            key="filtro_prov_giro"
        )
    with col_s3:
        st.metric(
            label="📦 Total Proveedores",
            value=len(proveedores_list)
        )

    # Filtrado local sin recargas anómalas
    filtrados = proveedores_list
    if filtro_txt and filtro_txt.strip():
        txt_lower = filtro_txt.strip().lower()
        filtrados = [
            p for p in filtrados
            if txt_lower in (p.get("nombre_comercial") or "").lower()
            or txt_lower in (p.get("contacto") or "").lower()
            or txt_lower in (p.get("telefono") or "").lower()
        ]

    if filtro_giro != "Todos":
        filtrados = [p for p in filtrados if p.get("giro") == filtro_giro]

    st.markdown("##### Directorio Comercial Activo")
    st.caption("💡 *Edita directamente las celdas de la tabla para actualizar la información del proveedor.*")

    if not filtrados:
        st.info("No se encontraron proveedores que coincidan con los criterios de búsqueda.")
        return

    df_prov = pd.DataFrame(filtrados)
    df_prov.insert(0, "#", range(1, len(df_prov) + 1))
    df_prov["contacto"] = df_prov["contacto"].fillna("").astype(str)
    df_prov["telefono"] = df_prov["telefono"].fillna("").astype(str)

    cols_ed = ["#", "nombre_comercial", "contacto", "telefono", "giro"]
    ed_prov_key = f"editor_proveedores_{st.session_state['ed_proveedor_counter']}"

    edited_df = st.data_editor(
        df_prov[cols_ed],
        column_config={
            "#": st.column_config.NumberColumn("#", disabled=True),
            "nombre_comercial": st.column_config.TextColumn("Razón Social / Nombre Comercial", required=True),
            "contacto": st.column_config.TextColumn("Contacto / Asesor"),
            "telefono": st.column_config.TextColumn("Teléfono / WhatsApp"),
            "giro": st.column_config.SelectboxColumn("Giro Comercial", options=GIROS_LIST, required=True)
        },
        use_container_width=True,
        hide_index=True,
        key=ed_prov_key
    )

    # Detección y guardado de cambios en celdas editadas
    if ed_prov_key in st.session_state and st.session_state[ed_prov_key].get("edited_rows", {}):
        cambios_guardados = 0
        error_guardado = None

        for row_str, col_vals in list(st.session_state[ed_prov_key]["edited_rows"].items()):
            try:
                r_idx = int(row_str)
            except ValueError:
                continue

            if r_idx >= len(filtrados):
                continue

            id_mod = filtrados[r_idx]["id"]
            up_payload = {}

            if "nombre_comercial" in col_vals:
                v_nom = col_vals["nombre_comercial"]
                if not v_nom or not str(v_nom).strip():
                    error_guardado = "La razón social del proveedor no puede quedar vacía."
                    break
                up_payload["nombre_comercial"] = str(v_nom).strip()

            if "contacto" in col_vals:
                up_payload["contacto"] = str(col_vals["contacto"] or "").strip()

            if "telefono" in col_vals:
                up_payload["telefono"] = str(col_vals["telefono"] or "").strip()

            if "giro" in col_vals:
                up_payload["giro"] = str(col_vals["giro"])

            if up_payload:
                try:
                    supabase.table("proveedores").update(up_payload).eq("id", id_mod).execute()
                    cambios_guardados += 1
                except Exception as ex_up:
                    error_guardado = f"Error al guardar cambios: {ex_up}"
                    break

        if error_guardado:
            st.toast(f"⚠️ {error_guardado}", icon="⚠️")
            st.session_state["ed_proveedor_counter"] += 1
            st.session_state.pop(ed_prov_key, None)
            st.rerun()
        elif cambios_guardados > 0:
            st.toast("✅ Datos de proveedores actualizados correctamente.", icon="✅")
            st.session_state["ed_proveedor_counter"] += 1
            st.session_state.pop(ed_prov_key, None)
            st.rerun()
