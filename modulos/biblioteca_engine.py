import streamlit as st
from supabase import Client
import pandas as pd
import datetime
from modulos.db_engine import (
    normalizar_unidad,
    unidades_list,
    get_biblioteca_instituciones,
    get_biblioteca_conceptos,
    generar_plantilla_excel,
    procesar_excel_importacion
)

def render_biblioteca_tab(supabase: Client, user_id: str):
    st.markdown("### 📖 Biblioteca Maestra de Conceptos (Global)")
    st.caption("Administra el tabulador institucional de precios de referencia y matrices de costo directo para usar en múltiples contratos.")

    # 1. Gestión de Instituciones
    cats_bib = get_biblioteca_instituciones(user_id)
    if "pending_cat_activa" in st.session_state:
        st.session_state["cat_activa"] = st.session_state.pop("pending_cat_activa")
    elif "cat_activa" not in st.session_state or (cats_bib and st.session_state["cat_activa"] not in cats_bib):
        st.session_state["cat_activa"] = cats_bib[0] if cats_bib else None

    cat_bib_sel = None
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        with st.container(border=True):
            st.markdown("**1. Selecciona o elimina una institución/catálogo maestro:**")
            c_bc1, c_bc2 = st.columns([3, 1])
            if cats_bib:
                idx_sel = cats_bib.index(st.session_state["cat_activa"]) if st.session_state.get("cat_activa") in cats_bib else 0
                cat_bib_sel = c_bc1.selectbox("Institución:", cats_bib, index=idx_sel, key="cat_activa", label_visibility="collapsed")
            else:
                c_bc1.selectbox("Institución:", ["(Sin instituciones)"], disabled=True, label_visibility="collapsed")

            if c_bc2.button("Eliminar", type="primary", use_container_width=True, disabled=(not cat_bib_sel)):
                if cat_bib_sel:
                    supabase.table("instituciones").delete().eq("nombre", cat_bib_sel).eq("user_id", user_id).execute()
                    supabase.table("biblioteca_conceptos").delete().eq("institucion", cat_bib_sel).eq("user_id", user_id).execute()
                    get_biblioteca_instituciones.clear()
                    get_biblioteca_conceptos.clear()
                    st.session_state["pending_cat_activa"] = cats_bib[0] if (len(cats_bib) > 1 and cats_bib[0] != cat_bib_sel) else ""
                    st.rerun()

    with col_b2:
        with st.container(border=True):
            st.markdown("**2. Crea una institución/catálogo maestro:**")
            new_cat_k = st.session_state.get("new_cat_key", 0)
            with st.form("form_crear_institucion", border=False):
                c_nc1, c_nc2 = st.columns([3, 1])
                nueva_inst = c_nc1.text_input("Nombre de institución:", label_visibility="collapsed", key=f"input_nueva_cat_{new_cat_k}", placeholder="Ej: ISSSTE, SEDENA...")
                btn_crear = c_nc2.form_submit_button("Crear", use_container_width=True)
                if btn_crear and nueva_inst.strip():
                    inst_limpia = nueva_inst.strip()
                    res_chk = supabase.table("instituciones").select("id").eq("nombre", inst_limpia).eq("user_id", user_id).execute()
                    if not res_chk.data:
                        supabase.table("instituciones").insert({
                            "nombre": inst_limpia,
                            "user_id": user_id
                        }).execute()
                    get_biblioteca_instituciones.clear()
                    st.session_state["pending_cat_activa"] = inst_limpia
                    st.session_state["msg_exito_cat"] = True
                    st.session_state["new_cat_key"] = new_cat_k + 1
                    st.rerun()
            
            if st.session_state.get("msg_exito_cat"):
                st.success("✅ Institución creada exitosamente")
                st.session_state["msg_exito_cat"] = False

    if not cat_bib_sel:
        st.info("ℹ️ Para registrar conceptos en la biblioteca, primero selecciona o crea una institución arriba.")
        return

    ts_descarga = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    col_bib_alta, col_bib_del = st.columns(2)

    with col_bib_alta:
        # Carga Masiva Excel
        with st.expander("📂 Subir Biblioteca desde Excel (Carga Masiva)"):
            st.download_button(
                "📥 Descargar Plantilla Excel de Biblioteca",
                data=generar_plantilla_excel("biblioteca"),
                file_name=f"Plantilla_Bib_Global_{ts_descarga}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            up_bib_k = st.session_state.get("up_bib_key", 0)
            excel_bib = st.file_uploader("Sube plantilla llena:", type=["xlsx"], key=f"up_bib_{up_bib_k}")
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
                        st.session_state["up_bib_key"] = up_bib_k + 1
                        st.success(f"✅ {len(records_b)} conceptos guardados en {cat_bib_sel}.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error procesando el archivo: {e}")

        # Alta manual con Dual Path (Camino 1: Cerrado vs Camino 2: Analítico APU)
        with st.expander("➕ Alta manual (Concepto Maestro)"):
            bib_c = st.session_state.get("bib_alta_key", 0)

            # Callback reactivo para sumar costos directos y pre-rellenar el PU Referencial
            def _on_costos_directos_bib_change():
                mat = st.session_state.get(f"bib_mat_{bib_c}", 0.0) or 0.0
                mo = st.session_state.get(f"bib_mo_{bib_c}", 0.0) or 0.0
                herr = st.session_state.get(f"bib_herr_{bib_c}", 0.0) or 0.0
                ind = st.session_state.get(f"bib_ind_{bib_c}", 0.0) or 0.0
                suma = round(float(mat) + float(mo) + float(herr) + float(ind), 2)
                if suma > 0:
                    st.session_state[f"bib_pu_ref_{bib_c}"] = suma

            st.session_state.setdefault(f"bib_pu_ref_{bib_c}", 0.0)

            esp_m = st.text_input("Especialidad (Opcional)", placeholder="Ej: 01 PRELIMINARES", key=f"bib_esp_{bib_c}")
            cat_m = st.text_input("Categoría / Partida (Opcional)", placeholder="Ej: 1.1", key=f"bib_cat_{bib_c}")
            clave_m = st.text_input("Clave de Concepto *", placeholder="Ej: OC01-015-126", key=f"bib_clave_{bib_c}")
            unidad_m = st.selectbox("Unidad", unidades_list, key=f"bib_unidad_{bib_c}")
            desc_m = st.text_area("Descripción detallada *", placeholder="Ingrese la descripción completa...", key=f"bib_desc_{bib_c}")

            # Camino 2: Expander opcional de desglose analítico
            with st.expander("📊 Desglose Analítico de Costo Directo", expanded=False):
                st.caption("Captura opcional de insumos directos. Al llenarlos, se calculará automáticamente el Costo Directo Total.")
                c_col1, c_col2 = st.columns(2)
                c_mat = c_col1.number_input(
                    "Costo Material ($)", min_value=0.0, step=0.5, format="%.2f",
                    key=f"bib_mat_{bib_c}", on_change=_on_costos_directos_bib_change
                )
                c_mo = c_col2.number_input(
                    "Costo Mano de Obra ($)", min_value=0.0, step=0.5, format="%.2f",
                    key=f"bib_mo_{bib_c}", on_change=_on_costos_directos_bib_change
                )
                c_herr = c_col1.number_input(
                    "Costo Herramienta ($)", min_value=0.0, step=0.5, format="%.2f",
                    key=f"bib_herr_{bib_c}", on_change=_on_costos_directos_bib_change
                )
                c_ind = c_col2.number_input(
                    "Costo Indirecto ($)", min_value=0.0, step=0.5, format="%.2f",
                    key=f"bib_ind_{bib_c}", on_change=_on_costos_directos_bib_change
                )

            # Camino 1: Precio unitario referencial (directo o pre-rellenado por la suma analítica)
            pu_m = st.number_input(
                "Precio Unitario Referencial ($)",
                min_value=0.0, step=0.5, format="%.2f",
                key=f"bib_pu_ref_{bib_c}"
            )

            if st.button("Guardar en Biblioteca", type="primary", key=f"btn_save_bib_{bib_c}"):
                if not clave_m.strip() or not desc_m.strip():
                    st.error("⚠️ Clave y descripción son obligatorias.")
                else:
                    mat_val = round(float(c_mat), 2)
                    mo_val = round(float(c_mo), 2)
                    herr_val = round(float(c_herr), 2)
                    ind_val = round(float(c_ind), 2)
                    suma_analitica = round(mat_val + mo_val + herr_val + ind_val, 2)

                    # Si se capturó desglose y el PU es 0, usamos la suma analítica
                    pu_final = round(float(pu_m), 2)
                    if pu_final == 0.0 and suma_analitica > 0:
                        pu_final = suma_analitica

                    # Regla de Negocio: En Biblioteca Maestra NUNCA se almacena porcentaje ni monto de utilidad
                    payload = {
                        "user_id": user_id,
                        "institucion": cat_bib_sel,
                        "especialidad": esp_m.strip(),
                        "categoria": cat_m.strip(),
                        "clave": clave_m.strip(),
                        "descripcion": desc_m.strip(),
                        "unidad": normalizar_unidad(unidad_m),
                        "costo_material": mat_val,
                        "costo_mano_obra": mo_val,
                        "costo_herramienta": herr_val,
                        "costo_indirecto": ind_val,
                        "precio_referencial": pu_final
                    }

                    try:
                        supabase.table("biblioteca_conceptos").insert(payload).execute()
                        get_biblioteca_conceptos.clear()
                        get_biblioteca_instituciones.clear()
                        st.session_state["bib_alta_key"] = bib_c + 1
                        # Limpiar valor de PU para el siguiente registro
                        st.session_state.pop(f"bib_pu_ref_{bib_c}", None)
                        st.success("✅ Concepto maestro guardado exitosamente.")
                        st.rerun()
                    except Exception as ex_ins:
                        st.error(f"Error al guardar concepto: {ex_ins}")

    lista_admin_bib = get_biblioteca_conceptos(cat_bib_sel, user_id)
    dict_del_bib = {f"#{idx} — {c['clave']} ({c['descripcion'][:50]}...)": c["id"] for idx, c in enumerate(lista_admin_bib, start=1)} if lista_admin_bib else {}

    with col_bib_del:
        with st.expander("🗑️ Eliminar Conceptos Maestros (Borrado Masivo)"):
            bib_del_k = st.session_state.get("bib_del_counter", 0)
            sel_del_bib_labels = st.multiselect("Seleccionar conceptos maestros:", list(dict_del_bib.keys()), key=f"del_bib_{bib_del_k}")
            borrar_toda_cat = st.checkbox("⚠️ Selecciona para eliminar todos los conceptos mostrados en la tabla.", key=f"chk_toda_cat_{bib_del_k}")
            if borrar_toda_cat:
                sel_del_bib_labels = list(dict_del_bib.keys())

            if st.button("Eliminar Seleccionados", type="primary", disabled=len(sel_del_bib_labels)==0, key=f"btn_del_bib_bulk_{bib_del_k}"):
                ids_to_delete = [dict_del_bib[label] for label in sel_del_bib_labels]
                if ids_to_delete:
                    for chunk in [ids_to_delete[i:i+50] for i in range(0, len(ids_to_delete), 50)]:
                        supabase.table("biblioteca_conceptos").delete().in_("id", chunk).execute()
                get_biblioteca_conceptos.clear()
                st.session_state["bib_del_counter"] = bib_del_k + 1
                st.success(f"{len(ids_to_delete)} conceptos eliminados.")
                st.rerun()

    # Tabla Interactiva (st.data_editor) con soporte Dual Path
    if lista_admin_bib:
        st.markdown(f"##### Conceptos en Institución: {cat_bib_sel} (Editor Directo):")
        st.caption("💡 *Haz doble clic sobre cualquier celda para modificar la base maestra. Modificar costos directos actualizará el tabulador.*")
        df_admin = pd.DataFrame(lista_admin_bib)
        df_admin.insert(0, "#", range(1, len(df_admin) + 1))

        df_admin["clave"] = df_admin["clave"].fillna("").astype(str)
        df_admin["categoria"] = df_admin["categoria"].fillna("").astype(str)
        df_admin["especialidad"] = df_admin["especialidad"].fillna("").astype(str)
        df_admin["descripcion"] = df_admin["descripcion"].fillna("").astype(str)
        df_admin["costo_material"] = pd.to_numeric(df_admin.get("costo_material"), errors="coerce").fillna(0.0).astype(float).round(2)
        df_admin["costo_mano_obra"] = pd.to_numeric(df_admin.get("costo_mano_obra"), errors="coerce").fillna(0.0).astype(float).round(2)
        df_admin["costo_herramienta"] = pd.to_numeric(df_admin.get("costo_herramienta"), errors="coerce").fillna(0.0).astype(float).round(2)
        df_admin["costo_indirecto"] = pd.to_numeric(df_admin.get("costo_indirecto"), errors="coerce").fillna(0.0).astype(float).round(2)
        df_admin["precio_referencial"] = pd.to_numeric(df_admin.get("precio_referencial"), errors="coerce").fillna(0.0).astype(float).round(2)

        ed_bib_key = f"editor_biblioteca_{cat_bib_sel}_{st.session_state.get('ed_bib_counter', 0)}"

        edited_bib = st.data_editor(
            df_admin[[
                "#", "clave", "especialidad", "categoria", "unidad",
                "costo_material", "costo_mano_obra", "costo_herramienta", "costo_indirecto",
                "precio_referencial", "descripcion"
            ]],
            column_config={
                "#": st.column_config.NumberColumn("#", disabled=True),
                "clave": st.column_config.TextColumn("Clave", required=True),
                "especialidad": st.column_config.TextColumn("Especialidad"),
                "categoria": st.column_config.TextColumn("Categoría"),
                "unidad": st.column_config.SelectboxColumn("Unidad", options=unidades_list, required=True),
                "costo_material": st.column_config.NumberColumn("Costo Mat. ($)", format="$%.2f", min_value=0.0, step=0.01),
                "costo_mano_obra": st.column_config.NumberColumn("Costo M.O. ($)", format="$%.2f", min_value=0.0, step=0.01),
                "costo_herramienta": st.column_config.NumberColumn("Costo Herr. ($)", format="$%.2f", min_value=0.0, step=0.01),
                "costo_indirecto": st.column_config.NumberColumn("Costo Ind. ($)", format="$%.2f", min_value=0.0, step=0.01),
                "precio_referencial": st.column_config.NumberColumn("P.U. Referencial ($)", format="$%.2f", min_value=0.0, step=0.01, required=True),
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

                # Costos analíticos
                hubo_cambio_costo = False
                for c_cost in ["costo_material", "costo_mano_obra", "costo_herramienta", "costo_indirecto"]:
                    if c_cost in col_vals:
                        hubo_cambio_costo = True
                        val_num = pd.to_numeric(col_vals[c_cost], errors="coerce")
                        up_b[c_cost] = round(max(0.0, float(val_num)), 2) if not pd.isna(val_num) else 0.0

                if "precio_referencial" in col_vals:
                    val_pr = col_vals["precio_referencial"]
                    if val_pr is None or str(val_pr).strip() in ("", "None", "nan"):
                        up_b["precio_referencial"] = float(bib_actual.get("precio_referencial") or 0.0)
                    else:
                        try:
                            up_b["precio_referencial"] = round(max(0.0, float(val_pr)), 2)
                        except (ValueError, TypeError):
                            up_b["precio_referencial"] = float(bib_actual.get("precio_referencial") or 0.0)
                elif hubo_cambio_costo:
                    # Si se modificaron costos y no el PU directamente, recalcular la suma
                    c_mat_n = up_b.get("costo_material", bib_actual.get("costo_material") or 0.0)
                    c_mo_n = up_b.get("costo_mano_obra", bib_actual.get("costo_mano_obra") or 0.0)
                    c_herr_n = up_b.get("costo_herramienta", bib_actual.get("costo_herramienta") or 0.0)
                    c_ind_n = up_b.get("costo_indirecto", bib_actual.get("costo_indirecto") or 0.0)
                    suma_n = round(float(c_mat_n) + float(c_mo_n) + float(c_herr_n) + float(c_ind_n), 2)
                    if suma_n > 0:
                        up_b["precio_referencial"] = suma_n

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
