import streamlit as st
import pandas as pd
from supabase import Client

# Especialidades estándar de mano de obra
ESPECIALIDADES_LIST = [
    "Albañilería",
    "Fierrero",
    "Pintura",
    "Plomería",
    "Electricidad",
    "Peón",
    "Carpintería",
    "Herrería",
    "Yesero / Tablarroca",
    "Otro"
]


def render_personal_tab(supabase: Client, user_id: str):
    """
    Renderiza la pestaña Tab 6: Directorio de Personal de Obra y Cuadrillas.
    Permite el registro, edición de jornales base y gestión de destajistas.
    """
    st.markdown("### Directorio de Personal y Cuadrillas 👷")
    st.caption("Control centralizado de trabajadores, destajistas y cuadrillas de obra con tarifas base por jornal para nómina y raya.")

    # Contador de versión para reseteo limpio de formularios
    if "personal_form_counter" not in st.session_state:
        st.session_state["personal_form_counter"] = 0
    p_counter = st.session_state["personal_form_counter"]

    if "ed_personal_counter" not in st.session_state:
        st.session_state["ed_personal_counter"] = 0

    col_alta, col_baja = st.columns([1, 1])

    # -------------------------------------------------------------
    # SECCIÓN 1: FORMULARIO DE ALTA RÁPIDA
    # -------------------------------------------------------------
    with col_alta:
        with st.expander("➕ Registrar Nuevo Trabajador / Destajista", expanded=False):
            with st.form(f"form_personal_{p_counter}", clear_on_submit=True):
                nombre = st.text_input(
                    "Nombre completo *",
                    placeholder="Ej: Juan Pérez García",
                    key=f"pers_nombre_{p_counter}"
                )

                c_esp, c_jor = st.columns(2)
                with c_esp:
                    especialidad = st.selectbox(
                        "Especialidad / Oficio *",
                        options=ESPECIALIDADES_LIST,
                        index=0,
                        key=f"pers_especialidad_{p_counter}"
                    )
                with c_jor:
                    costo_jornal = st.number_input(
                        "Costo Jornal Base ($) *",
                        min_value=0.0,
                        value=500.0,
                        step=50.0,
                        format="%.2f",
                        key=f"pers_jornal_{p_counter}",
                        help="Tarifa de referencia diaria para cálculo de liquidación de raya."
                    )

                telefono = st.text_input(
                    "Teléfono de contacto / WhatsApp",
                    placeholder="Ej: 312 123 4567",
                    key=f"pers_telefono_{p_counter}"
                )

                btn_guardar_pers = st.form_submit_button("Guardar Trabajador", type="primary", use_container_width=True)

                if btn_guardar_pers:
                    if not nombre or not nombre.strip():
                        st.error("⚠️ El nombre del trabajador es obligatorio.")
                    else:
                        try:
                            supabase.table("personal_obra").insert({
                                "user_id": user_id,
                                "nombre": nombre.strip(),
                                "especialidad": especialidad,
                                "costo_jornal_base": round(float(costo_jornal), 2),
                                "telefono": telefono.strip() if telefono else None
                            }).execute()

                            st.session_state["personal_form_counter"] += 1
                            st.success(f"✅ Trabajador '{nombre.strip()}' registrado exitosamente.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error al registrar trabajador: {ex}")

    # -------------------------------------------------------------
    # SECCIÓN 2: CONSULTA DE TRABAJADORES ACTIVOS
    # -------------------------------------------------------------
    try:
        res_pers = supabase.table("personal_obra")\
            .select("id, nombre, especialidad, costo_jornal_base, telefono, created_at")\
            .eq("user_id", user_id)\
            .order("id")\
            .execute()
        personal_list = res_pers.data or []
    except Exception as ex_list:
        st.error(f"Error al consultar el personal registrado: {ex_list}")
        personal_list = []

    # -------------------------------------------------------------
    # SECCIÓN 3: DAR DE BAJA TRABAJADOR (DEFENSIVO)
    # -------------------------------------------------------------
    with col_baja:
        with st.expander("🗑️ Dar de Baja Trabajador", expanded=False):
            if not personal_list:
                st.info("No hay trabajadores registrados para dar de baja.")
            else:
                pers_dict_del = {
                    f"#{p['id']} — {p['nombre']} ({p.get('especialidad', 'Oficio')})": p["id"]
                    for p in personal_list
                }
                pers_sel_del = st.selectbox(
                    "Seleccionar trabajador a dar de baja:",
                    options=list(pers_dict_del.keys()),
                    key=f"del_pers_sel_{p_counter}"
                )
                st.caption("ℹ️ *Los generadores y mediciones de avance pasados se conservan intactos sin perder importes ni datos contables (ON DELETE SET NULL).*")
                
                chk_del = st.checkbox(
                    "Confirmo la baja de este trabajador",
                    key=f"chk_del_pers_{p_counter}"
                )
                btn_del = st.button(
                    "Eliminar Trabajador",
                    type="primary",
                    disabled=not chk_del,
                    key=f"btn_del_pers_action_{p_counter}"
                )

                if btn_del and chk_del:
                    id_pers_del = pers_dict_del[pers_sel_del]
                    try:
                        supabase.table("personal_obra").delete().eq("id", id_pers_del).execute()
                        st.session_state["personal_form_counter"] += 1
                        st.success("✅ Trabajador eliminado del directorio.")
                        st.rerun()
                    except Exception as ex_del:
                        st.error(f"Error al eliminar trabajador: {ex_del}")

    # -------------------------------------------------------------
    # SECCIÓN 4: VISUALIZACIÓN, BÚSQUEDA Y EDICIÓN INTERACTIVA
    # -------------------------------------------------------------
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    if not personal_list:
        st.info("👷 Aún no has registrado trabajadores o cuadrillas. Da de alta al primero usando el formulario superior.")
        return

    # Barra de búsqueda y filtrado ágil
    col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
    with col_s1:
        filtro_txt = st.text_input(
            "🔍 Buscar trabajador por nombre o teléfono:",
            placeholder="Escribe para buscar...",
            key="filtro_personal_txt"
        )
    with col_s2:
        filtro_esp = st.selectbox(
            "Filtrar por especialidad:",
            options=["Todas"] + ESPECIALIDADES_LIST,
            key="filtro_personal_esp"
        )
    with col_s3:
        st.metric(
            label="👥 Total Trabajadores",
            value=len(personal_list)
        )

    # Filtrar registros localmente sin recargas anómalas
    filtrados = personal_list
    if filtro_txt and filtro_txt.strip():
        txt_lower = filtro_txt.strip().lower()
        filtrados = [
            p for p in filtrados
            if txt_lower in (p.get("nombre") or "").lower() or txt_lower in (p.get("telefono") or "").lower()
        ]

    if filtro_esp != "Todas":
        filtrados = [p for p in filtrados if p.get("especialidad") == filtro_esp]

    st.markdown("##### Directorio Activo de Cuadrillas y Destajistas")
    st.caption("💡 *Edita directamente las celdas de tarifa ($/jornal), especialidad o teléfono. Los cambios se guardan automáticamente.*")

    if not filtrados:
        st.info("No se encontraron trabajadores que coincidan con los criterios de búsqueda.")
        return

    df_pers = pd.DataFrame(filtrados)
    df_pers.insert(0, "#", range(1, len(df_pers) + 1))
    df_pers["costo_jornal_base"] = pd.to_numeric(df_pers["costo_jornal_base"], errors="coerce").fillna(0.0).round(2)
    df_pers["telefono"] = df_pers["telefono"].fillna("").astype(str)

    cols_ed = ["#", "nombre", "especialidad", "costo_jornal_base", "telefono"]
    ed_pers_key = f"editor_personal_{st.session_state['ed_personal_counter']}"

    edited_df = st.data_editor(
        df_pers[cols_ed],
        column_config={
            "#": st.column_config.NumberColumn("#", disabled=True),
            "nombre": st.column_config.TextColumn("Nombre Completo", required=True),
            "especialidad": st.column_config.SelectboxColumn("Especialidad / Oficio", options=ESPECIALIDADES_LIST, required=True),
            "costo_jornal_base": st.column_config.NumberColumn("Costo Jornal ($)", format="$%.2f", min_value=0.0, step=25.0, required=True),
            "telefono": st.column_config.TextColumn("Teléfono / WhatsApp")
        },
        use_container_width=True,
        hide_index=True,
        key=ed_pers_key
    )

    # Detección y guardado de cambios en celdas editadas
    if ed_pers_key in st.session_state and st.session_state[ed_pers_key].get("edited_rows", {}):
        cambios_guardados = 0
        error_guardado = None

        for row_str, col_vals in list(st.session_state[ed_pers_key]["edited_rows"].items()):
            try:
                r_idx = int(row_str)
            except ValueError:
                continue

            if r_idx >= len(filtrados):
                continue

            id_mod = filtrados[r_idx]["id"]
            up_payload = {}

            if "nombre" in col_vals:
                v_nom = col_vals["nombre"]
                if not v_nom or not str(v_nom).strip():
                    error_guardado = "El nombre del trabajador no puede quedar vacío."
                    break
                up_payload["nombre"] = str(v_nom).strip()

            if "especialidad" in col_vals:
                up_payload["especialidad"] = str(col_vals["especialidad"])

            if "costo_jornal_base" in col_vals:
                try:
                    up_payload["costo_jornal_base"] = round(max(0.0, float(col_vals["costo_jornal_base"])), 2)
                except (ValueError, TypeError):
                    up_payload["costo_jornal_base"] = 0.0

            if "telefono" in col_vals:
                up_payload["telefono"] = str(col_vals["telefono"] or "").strip()

            if up_payload:
                try:
                    supabase.table("personal_obra").update(up_payload).eq("id", id_mod).execute()
                    cambios_guardados += 1
                except Exception as ex_up:
                    error_guardado = f"Error al guardar cambios: {ex_up}"
                    break

        if error_guardado:
            st.toast(f"⚠️ {error_guardado}", icon="⚠️")
            st.session_state["ed_personal_counter"] += 1
            st.session_state.pop(ed_pers_key, None)
            st.rerun()
        elif cambios_guardados > 0:
            st.toast("✅ Datos de personal actualizados correctamente.", icon="✅")
            st.session_state["ed_personal_counter"] += 1
            st.session_state.pop(ed_pers_key, None)
            st.rerun()
