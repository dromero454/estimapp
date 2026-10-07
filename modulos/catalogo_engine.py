import streamlit as st
from supabase import Client
import pandas as pd
import datetime
from modulos.db_engine import (
    normalizar_unidad,
    unidades_list,
    admite_decimales,
    get_biblioteca_instituciones,
    get_biblioteca_conceptos,
    get_mediciones,
    extraer_nombre_archivo,
    generar_plantilla_excel,
    procesar_excel_importacion
)

def render_catalogo_tab(supabase: Client, user_id: str, lista_proyectos: list, get_conceptos_cache):
    st.subheader("Catálogo del Proyecto (Contrato de Obra)")
    if not lista_proyectos:
        st.warning("Primero debes registrar un proyecto en la pestaña 'Gestión de Proyectos'.")
        return

    proyectos_dict = {p["nombre_obra"]: p["id"] for p in lista_proyectos}
    proy_sel = st.selectbox("Seleccionar Proyecto Destino", list(proyectos_dict.keys()), key="cat_proy_2")
    proy_id = proyectos_dict[proy_sel]

    # Datos del proyecto activo (herencia de factores globales como % Utilidad)
    proy_obj = next((p for p in lista_proyectos if p["id"] == proy_id), {})
    pct_util_proy_def = float(proy_obj.get("porcentaje_utilidad") or 15.0)

    categorias_disp = get_biblioteca_instituciones(user_id)
    if categorias_disp:
        cat_sel = st.selectbox("Institución/catálogo maestro (Para importar):", categorias_disp, key="sel_cat_bib_2")
        conceptos_bib = get_biblioteca_conceptos(cat_sel, user_id) if cat_sel else []
    else:
        cat_sel = None
        conceptos_bib = []
        st.info("ℹ️ No tienes instituciones registradas en tu Biblioteca Maestra. Puedes crearlas en la pestaña 'Biblioteca Maestra de Conceptos'.")

    col_import1, col_import2 = st.columns(2)

    with col_import1:
        # Importación Lote desde Biblioteca
        with st.expander("📦 Importación Lote desde Biblioteca"):
            if not conceptos_bib:
                st.info(f"No hay conceptos disponibles en '{cat_sel or 'Biblioteca'}'.")
            else:
                opciones_lote = {f"{c['clave']} — {c['descripcion'][:60]}...": c for c in conceptos_bib}
                ms_k = st.session_state.get("ms_lote_key", 0)
                seleccionados_lote = st.multiselect("Seleccionar conceptos:", list(opciones_lote.keys()), key=f"ms_lote_{ms_k}")
                if st.button("📥 Importar Seleccionados", type="primary") and seleccionados_lote:
                    registros_a_insertar = []
                    for sel in seleccionados_lote:
                        c_ref = opciones_lote[sel]
                        c_mat = float(c_ref.get("costo_material") or 0.0)
                        c_mo = float(c_ref.get("costo_mano_obra") or 0.0)
                        c_herr = float(c_ref.get("costo_herramienta") or 0.0)
                        c_ind = float(c_ref.get("costo_indirecto") or 0.0)
                        suma_costos = round(c_mat + c_mo + c_herr + c_ind, 2)

                        # Si el concepto maestro tiene desglose, calcula PU aplicando la utilidad del proyecto
                        if suma_costos > 0:
                            pu_calc = round(suma_costos * (1.0 + pct_util_proy_def / 100.0), 2)
                        else:
                            pu_calc = float(c_ref.get("precio_referencial") or 0.0)

                        registros_a_insertar.append({
                            "id_proyecto": proy_id,
                            "especialidad": c_ref.get("especialidad", ""),
                            "categoria": c_ref.get("categoria", ""),
                            "clave": c_ref["clave"],
                            "descripcion": c_ref["descripcion"],
                            "unidad": normalizar_unidad(c_ref["unidad"]),
                            "cantidad_contratada": 0.0,
                            "costo_material": c_mat,
                            "costo_mano_obra": c_mo,
                            "costo_herramienta": c_herr,
                            "costo_indirecto": c_ind,
                            "porcentaje_utilidad": pct_util_proy_def,
                            "precio_unitario": pu_calc
                        })

                    if registros_a_insertar:
                        for chunk in [registros_a_insertar[i:i+50] for i in range(0, len(registros_a_insertar), 50)]:
                            supabase.table("catalogo_conceptos").insert(chunk).execute()
                        get_conceptos_cache.clear()
                        st.session_state["ms_lote_key"] = ms_k + 1
                        st.success(f"✅ {len(registros_a_insertar)} conceptos importados.")
                        st.rerun()

        # Importar Concepto Único desde Biblioteca
        with st.expander("📄 Importar Concepto Único desde Biblioteca"):
            if conceptos_bib:
                opciones_unico = {f"{c['clave']} — {c['descripcion'][:55]}...": c for c in conceptos_bib}
                obj_u = opciones_unico[st.selectbox("Concepto maestro:", list(opciones_unico.keys()), key="sel_unico")]
                
                c_mat_u = float(obj_u.get("costo_material") or 0.0)
                c_mo_u = float(obj_u.get("costo_mano_obra") or 0.0)
                c_herr_u = float(obj_u.get("costo_herramienta") or 0.0)
                c_ind_u = float(obj_u.get("costo_indirecto") or 0.0)
                suma_costos_u = round(c_mat_u + c_mo_u + c_herr_u + c_ind_u, 2)
                pu_default_u = round(suma_costos_u * (1.0 + pct_util_proy_def / 100.0), 2) if suma_costos_u > 0 else float(obj_u.get("precio_referencial") or 0.0)

                with st.form("form_importar_bib", clear_on_submit=True):
                    c_cu1, c_cu2 = st.columns(2)
                    cant_u = c_cu1.number_input("Cantidad Contratada", min_value=0.01, value=1.0, step=0.5, format="%.2f")
                    pu_u = c_cu2.number_input("Precio Unitario ($)", min_value=0.0, value=pu_default_u, step=0.5, format="%.2f")
                    if st.form_submit_button("➕ Agregar al Contrato"):
                        u_u_norm = normalizar_unidad(obj_u["unidad"])
                        if not admite_decimales(u_u_norm) and not float(cant_u).is_integer():
                            st.error(f"⚠️ Para la unidad '{u_u_norm}', la cantidad contratada debe ser un número entero.")
                        else:
                            cant_u_final = round(float(cant_u)) if not admite_decimales(u_u_norm) else round(float(cant_u), 2)
                            pu_u_final = round(float(pu_u), 2)
                            supabase.table("catalogo_conceptos").insert({
                                "id_proyecto": proy_id,
                                "especialidad": obj_u.get("especialidad"),
                                "categoria": obj_u.get("categoria"),
                                "clave": obj_u["clave"],
                                "descripcion": obj_u["descripcion"],
                                "unidad": u_u_norm,
                                "cantidad_contratada": cant_u_final,
                                "costo_material": c_mat_u,
                                "costo_mano_obra": c_mo_u,
                                "costo_herramienta": c_herr_u,
                                "costo_indirecto": c_ind_u,
                                "porcentaje_utilidad": pct_util_proy_def,
                                "precio_unitario": pu_u_final
                            }).execute()
                            get_conceptos_cache.clear()
                            st.success("✅ Concepto agregado.")
                            st.rerun()

    with col_import2:
        # Carga Masiva Excel
        ts_descarga = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with st.expander("📂 Subir desde Excel (Carga Masiva al Contrato)"):
            st.download_button(
                "📥 Descargar Plantilla Oficial Excel",
                data=generar_plantilla_excel("proyecto"),
                file_name=f"Plantilla_Cat_Proyecto_{ts_descarga}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            up_proy_k = st.session_state.get("up_proy_key", 0)
            excel_proy = st.file_uploader("Sube plantilla llena:", type=["xlsx"], key=f"up_proy_{up_proy_k}")
            if excel_proy and st.button("Subir e Insertar al Proyecto", type="primary"):
                try:
                    df_up = pd.read_excel(excel_proy)
                    ok, error_msg, records = procesar_excel_importacion(
                        df_up, tipo="proyecto", pct_utilidad_default=pct_util_proy_def
                    )
                    if not ok:
                        st.error(f"⚠️ {error_msg}")
                    elif not records:
                        st.warning("⚠️ No se encontraron filas con datos válidos (clave y descripción requeridas).")
                    else:
                        for r in records:
                            r["id_proyecto"] = proy_id
                        for chunk in [records[i:i+50] for i in range(0, len(records), 50)]:
                            supabase.table("catalogo_conceptos").insert(chunk).execute()
                        get_conceptos_cache.clear()
                        st.session_state["up_proy_key"] = up_proy_k + 1
                        st.success(f"✅ {len(records)} conceptos cargados exitosamente.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error procesando el archivo: {e}")

        # Alta manual con Dual Path (Camino 1: Cerrado vs Camino 2: Analítico + Margen de Utilidad)
        with st.expander("➕ Alta manual (Concepto Extraordinario)"):
            cat_c = st.session_state.get("cat_alta_key", 0)

            # Callback reactivo para calcular Precio Unitario = (Costos Directos) * (1 + % Utilidad / 100)
            def _on_costos_cat_change():
                mat = st.session_state.get(f"cat_mat_{cat_c}", 0.0) or 0.0
                mo = st.session_state.get(f"cat_mo_{cat_c}", 0.0) or 0.0
                herr = st.session_state.get(f"cat_herr_{cat_c}", 0.0) or 0.0
                ind = st.session_state.get(f"cat_ind_{cat_c}", 0.0) or 0.0
                util = st.session_state.get(f"cat_util_{cat_c}", pct_util_proy_def)
                if util is None:
                    util = pct_util_proy_def
                costo_sub = round(float(mat) + float(mo) + float(herr) + float(ind), 2)
                if costo_sub > 0:
                    pu_calc = round(costo_sub * (1.0 + float(util) / 100.0), 2)
                    st.session_state[f"cat_pu_{cat_c}"] = pu_calc

            st.session_state.setdefault(f"cat_pu_{cat_c}", 0.0)
            st.session_state.setdefault(f"cat_util_{cat_c}", pct_util_proy_def)

            esp_m = st.text_input("Especialidad (Opcional)", placeholder="Ej: 01 PRELIMINARES", key=f"cat_esp_{cat_c}")
            cat_m = st.text_input("Categoría / Partida (Opcional)", placeholder="Ej: 1.1", key=f"cat_cat_{cat_c}")
            clave_m = st.text_input("Clave de Concepto *", placeholder="Ej: OC01-015-126", key=f"cat_clave_{cat_c}")
            unidad_m = st.selectbox("Unidad", unidades_list, key=f"cat_unidad_{cat_c}")
            desc_m = st.text_area("Descripción detallada *", placeholder="Ingrese la descripción completa...", key=f"cat_desc_{cat_c}")

            c_cant_col, c_util_col = st.columns(2)
            cant_m = c_cant_col.number_input("Cantidad Contratada", min_value=0.01, value=1.0, step=0.5, format="%.2f", key=f"cat_cant_{cat_c}")
            pct_util_input = c_util_col.number_input(
                "% Utilidad (Margen)", min_value=0.0, max_value=100.0,
                value=st.session_state.get(f"cat_util_{cat_c}", pct_util_proy_def),
                step=0.5, format="%.2f",
                key=f"cat_util_{cat_c}", on_change=_on_costos_cat_change
            )

            # Camino 2: Expander opcional de desglose analítico APU
            with st.expander("📊 Desglose Analítico de Costo Directo", expanded=False):
                st.caption("Captura opcional de costos directos e indirectos. Al llenarlos, se calculará el Precio Unitario aplicando el % de Utilidad.")
                c_dcol1, c_dcol2 = st.columns(2)
                c_mat = c_dcol1.number_input(
                    "Costo Material ($)", min_value=0.0, step=0.5, format="%.2f",
                    key=f"cat_mat_{cat_c}", on_change=_on_costos_cat_change
                )
                c_mo = c_dcol2.number_input(
                    "Costo Mano de Obra ($)", min_value=0.0, step=0.5, format="%.2f",
                    key=f"cat_mo_{cat_c}", on_change=_on_costos_cat_change
                )
                c_herr = c_dcol1.number_input(
                    "Costo Herramienta ($)", min_value=0.0, step=0.5, format="%.2f",
                    key=f"cat_herr_{cat_c}", on_change=_on_costos_cat_change
                )
                c_ind = c_dcol2.number_input(
                    "Costo Indirecto ($)", min_value=0.0, step=0.5, format="%.2f",
                    key=f"cat_ind_{cat_c}", on_change=_on_costos_cat_change
                )

            # Camino 1: Precio unitario tradicional (directo o calculado automáticamente)
            pu_m = st.number_input(
                "Precio Unitario ($)", min_value=0.0, step=0.5, format="%.2f",
                key=f"cat_pu_{cat_c}"
            )

            if st.button("Guardar en Catálogo", type="primary", key=f"btn_save_cat_{cat_c}"):
                if not clave_m.strip() or not desc_m.strip():
                    st.error("⚠️ Clave y descripción son obligatorias.")
                else:
                    u_m_norm = normalizar_unidad(unidad_m)
                    if not admite_decimales(u_m_norm) and not float(cant_m).is_integer():
                        st.error(f"⚠️ Para la unidad '{u_m_norm}', la cantidad contratada debe ser un número entero.")
                    else:
                        cant_m_final = round(float(cant_m)) if not admite_decimales(u_m_norm) else round(float(cant_m), 2)
                        mat_val = round(float(c_mat), 2)
                        mo_val = round(float(c_mo), 2)
                        herr_val = round(float(c_herr), 2)
                        ind_val = round(float(c_ind), 2)
                        suma_analitica = round(mat_val + mo_val + herr_val + ind_val, 2)
                        util_final = round(float(pct_util_input), 2)

                        pu_final = round(float(pu_m), 2)
                        if pu_final == 0.0 and suma_analitica > 0:
                            pu_final = round(suma_analitica * (1.0 + util_final / 100.0), 2)

                        payload_conc = {
                            "id_proyecto": proy_id,
                            "especialidad": esp_m.strip(),
                            "categoria": cat_m.strip(),
                            "clave": clave_m.strip(),
                            "descripcion": desc_m.strip(),
                            "unidad": u_m_norm,
                            "cantidad_contratada": cant_m_final,
                            "costo_material": mat_val,
                            "costo_mano_obra": mo_val,
                            "costo_herramienta": herr_val,
                            "costo_indirecto": ind_val,
                            "porcentaje_utilidad": util_final,
                            "precio_unitario": pu_final
                        }

                        try:
                            supabase.table("catalogo_conceptos").insert(payload_conc).execute()
                            get_conceptos_cache.clear()
                            st.session_state["cat_alta_key"] = cat_c + 1
                            st.session_state.pop(f"cat_pu_{cat_c}", None)
                            st.session_state.pop(f"cat_util_{cat_c}", None)
                            st.success("✅ Concepto guardado exitosamente.")
                            st.rerun()
                        except Exception as ex_cat_ins:
                            st.error(f"Error al guardar el concepto: {ex_cat_ins}")

    # Borrado de Conceptos (Cascada Segura)
    conceptos_proyecto = get_conceptos_cache(proy_id)
    dict_conc_borrar = {f"#{idx} — {c['clave']} ({c['descripcion'][:45]}...)": c for idx, c in enumerate(conceptos_proyecto, start=1)} if conceptos_proyecto else {}

    with st.expander("🗑️ Eliminar Conceptos del Contrato (Borrado en Cascada)"):
        st.warning("Nota: Eliminar conceptos del catálogo borrará irreversiblemente las mediciones y avances asociados a ellos para proteger la integridad del balance.")
        del_conc_k = st.session_state.get("del_conc_counter", 0)
        conc_a_borrar_labels = st.multiselect("Seleccionar conceptos:", list(dict_conc_borrar.keys()), key=f"del_conc_sel_{del_conc_k}")
        borrar_todos_conc = st.checkbox("⚠️ Selecciona para eliminar todos los conceptos mostrados en la tabla.", key=f"chk_todos_conc_{del_conc_k}")
        if borrar_todos_conc:
            conc_a_borrar_labels = list(dict_conc_borrar.keys())

        if st.button("Eliminar Seleccionados", type="primary", disabled=len(conc_a_borrar_labels)==0, key=f"btn_del_cat_bulk_{del_conc_k}"):
            ids_to_delete = [dict_conc_borrar[label]["id"] for label in conc_a_borrar_labels]
            if ids_to_delete:
                try:
                    archivos_ev_conc = []
                    for chunk in [ids_to_delete[i:i+50] for i in range(0, len(ids_to_delete), 50)]:
                        try:
                            res_m_c = supabase.table("mediciones_campo").select("url_foto, url_croquis").in_("id_concepto", chunk).execute()
                            for m_row in (res_m_c.data or []):
                                if m_row.get("url_foto"):
                                    nf = extraer_nombre_archivo(m_row["url_foto"])
                                    if nf: archivos_ev_conc.append(nf)
                                if m_row.get("url_croquis"):
                                    nc = extraer_nombre_archivo(m_row["url_croquis"])
                                    if nc: archivos_ev_conc.append(nc)
                        except Exception:
                            pass

                    for chunk in [ids_to_delete[i:i+50] for i in range(0, len(ids_to_delete), 50)]:
                        supabase.table("mediciones_campo").delete().in_("id_concepto", chunk).execute()
                        supabase.table("catalogo_conceptos").delete().in_("id", chunk).execute()

                    if archivos_ev_conc:
                        for chunk_ev in [archivos_ev_conc[i:i+50] for i in range(0, len(archivos_ev_conc), 50)]:
                            try: supabase.storage.from_("evidencias").remove(chunk_ev)
                            except: pass

                    get_conceptos_cache.clear()
                    get_mediciones.clear()
                    st.session_state["del_conc_counter"] = del_conc_k + 1
                    st.success(f"✅ {len(ids_to_delete)} conceptos y sus mediciones eliminados.")
                    st.rerun()
                except Exception as ex_del_c:
                    st.error(f"Error al eliminar conceptos: {ex_del_c}")

    # Presupuesto Oficial del Proyecto (Editor Directo con Dual Path + Utilidad)
    if conceptos_proyecto:
        st.markdown("##### Presupuesto Oficial del Proyecto (Editor Directo):")
        st.caption("💡 *Haz doble clic sobre cualquier celda para modificarla. Al editar costos o margen (% Utilidad), el P.U. se recalcula automáticamente.*")
        df_c = pd.DataFrame(conceptos_proyecto)
        df_c.insert(0, "#", range(1, len(df_c) + 1))

        df_c["clave"] = df_c["clave"].fillna("").astype(str)
        df_c["categoria"] = df_c["categoria"].fillna("").astype(str)
        df_c["especialidad"] = df_c["especialidad"].fillna("").astype(str)
        df_c["descripcion"] = df_c["descripcion"].fillna("").astype(str)
        df_c["cantidad_contratada"] = pd.to_numeric(df_c["cantidad_contratada"], errors="coerce").fillna(0.0).astype(float).round(2)
        df_c["costo_material"] = pd.to_numeric(df_c.get("costo_material"), errors="coerce").fillna(0.0).astype(float).round(2)
        df_c["costo_mano_obra"] = pd.to_numeric(df_c.get("costo_mano_obra"), errors="coerce").fillna(0.0).astype(float).round(2)
        df_c["costo_herramienta"] = pd.to_numeric(df_c.get("costo_herramienta"), errors="coerce").fillna(0.0).astype(float).round(2)
        df_c["costo_indirecto"] = pd.to_numeric(df_c.get("costo_indirecto"), errors="coerce").fillna(0.0).astype(float).round(2)
        df_c["porcentaje_utilidad"] = pd.to_numeric(df_c.get("porcentaje_utilidad"), errors="coerce").fillna(pct_util_proy_def).astype(float).round(2)
        df_c["precio_unitario"] = pd.to_numeric(df_c["precio_unitario"], errors="coerce").fillna(0.0).astype(float).round(2)

        ed_cat_key = f"editor_catalogo_{proy_id}_{st.session_state.get('ed_cat_counter', 0)}"

        edited_catalogo = st.data_editor(
            df_c[[
                "#", "clave", "especialidad", "categoria", "unidad", "cantidad_contratada",
                "costo_material", "costo_mano_obra", "costo_herramienta", "costo_indirecto",
                "porcentaje_utilidad", "precio_unitario", "descripcion"
            ]],
            column_config={
                "#": st.column_config.NumberColumn("#", disabled=True),
                "clave": st.column_config.TextColumn("Clave", required=True),
                "especialidad": st.column_config.TextColumn("Especialidad"),
                "categoria": st.column_config.TextColumn("Categoría"),
                "unidad": st.column_config.SelectboxColumn("Unidad", options=unidades_list, required=True),
                "cantidad_contratada": st.column_config.NumberColumn("Cant. Contratada", format="%.2f", min_value=0.0, step=0.01, required=True),
                "costo_material": st.column_config.NumberColumn("Costo Mat. ($)", format="$%.2f", min_value=0.0, step=0.01),
                "costo_mano_obra": st.column_config.NumberColumn("Costo M.O. ($)", format="$%.2f", min_value=0.0, step=0.01),
                "costo_herramienta": st.column_config.NumberColumn("Costo Herr. ($)", format="$%.2f", min_value=0.0, step=0.01),
                "costo_indirecto": st.column_config.NumberColumn("Costo Ind. ($)", format="$%.2f", min_value=0.0, step=0.01),
                "porcentaje_utilidad": st.column_config.NumberColumn("% Utilidad", format="%.2f%%", min_value=0.0, max_value=100.0, step=0.5),
                "precio_unitario": st.column_config.NumberColumn("P.U. ($)", format="$%.2f", min_value=0.0, step=0.01, required=True),
                "descripcion": st.column_config.TextColumn("Descripción")
            },
            use_container_width=True,
            hide_index=True,
            key=ed_cat_key
        )

        if ed_cat_key in st.session_state and st.session_state[ed_cat_key].get("edited_rows", {}):
            error_cat_msg = None
            cambios_cat_guardados = 0

            for row_str, col_vals in list(st.session_state[ed_cat_key]["edited_rows"].items()):
                try:
                    r_idx = int(row_str)
                except ValueError:
                    continue
                if r_idx >= len(conceptos_proyecto):
                    continue

                conc_actual = conceptos_proyecto[r_idx]
                id_conc_mod = conc_actual["id"]
                up_payload = {}

                if "clave" in col_vals:
                    val_clave = col_vals["clave"]
                    if val_clave is None or not str(val_clave).strip():
                        error_cat_msg = "⚠️ La clave del concepto es obligatoria y no puede quedar vacía."
                        break
                    up_payload["clave"] = str(val_clave).strip()

                for campo in ["especialidad", "categoria", "descripcion"]:
                    if campo in col_vals:
                        up_payload[campo] = str(col_vals[campo] or "").strip()

                if "unidad" in col_vals:
                    val_u = col_vals["unidad"]
                    if val_u:
                        up_payload["unidad"] = normalizar_unidad(val_u)
                    else:
                        error_cat_msg = "⚠️ La unidad del concepto es obligatoria."
                        break

                if "cantidad_contratada" in col_vals:
                    val_c = col_vals["cantidad_contratada"]
                    if val_c is None or str(val_c).strip() in ("", "None", "nan"):
                        up_payload["cantidad_contratada"] = float(conc_actual.get("cantidad_contratada") or 0.0)
                    else:
                        try:
                            val_c_num = float(val_c)
                            u_eval = up_payload.get("unidad") or conc_actual.get("unidad") or ""
                            if not admite_decimales(u_eval):
                                val_c_num = round(val_c_num)
                            else:
                                val_c_num = round(val_c_num, 2)
                            up_payload["cantidad_contratada"] = max(0.0, val_c_num)
                        except (ValueError, TypeError):
                            up_payload["cantidad_contratada"] = float(conc_actual.get("cantidad_contratada") or 0.0)

                # Costos analíticos y % Utilidad
                hubo_cambio_analitico = False
                for c_cost in ["costo_material", "costo_mano_obra", "costo_herramienta", "costo_indirecto"]:
                    if c_cost in col_vals:
                        hubo_cambio_analitico = True
                        val_num = pd.to_numeric(col_vals[c_cost], errors="coerce")
                        up_payload[c_cost] = round(max(0.0, float(val_num)), 2) if not pd.isna(val_num) else 0.0

                if "porcentaje_utilidad" in col_vals:
                    hubo_cambio_analitico = True
                    val_util = pd.to_numeric(col_vals["porcentaje_utilidad"], errors="coerce")
                    up_payload["porcentaje_utilidad"] = round(max(0.0, float(val_util)), 2) if not pd.isna(val_util) else pct_util_proy_def

                # Recalcular Precio Unitario
                if "precio_unitario" in col_vals:
                    val_p = col_vals["precio_unitario"]
                    if val_p is None or str(val_p).strip() in ("", "None", "nan"):
                        up_payload["precio_unitario"] = float(conc_actual.get("precio_unitario") or 0.0)
                    else:
                        try:
                            up_payload["precio_unitario"] = round(max(0.0, float(val_p)), 2)
                        except (ValueError, TypeError):
                            up_payload["precio_unitario"] = float(conc_actual.get("precio_unitario") or 0.0)
                elif hubo_cambio_analitico:
                    c_mat_n = up_payload.get("costo_material", conc_actual.get("costo_material") or 0.0)
                    c_mo_n = up_payload.get("costo_mano_obra", conc_actual.get("costo_mano_obra") or 0.0)
                    c_herr_n = up_payload.get("costo_herramienta", conc_actual.get("costo_herramienta") or 0.0)
                    c_ind_n = up_payload.get("costo_indirecto", conc_actual.get("costo_indirecto") or 0.0)
                    u_pct_n = up_payload.get("porcentaje_utilidad", conc_actual.get("porcentaje_utilidad") or pct_util_proy_def)
                    costo_sub_n = round(float(c_mat_n) + float(c_mo_n) + float(c_herr_n) + float(c_ind_n), 2)
                    if costo_sub_n > 0:
                        up_payload["precio_unitario"] = round(costo_sub_n * (1.0 + float(u_pct_n) / 100.0), 2)

                if up_payload:
                    try:
                        supabase.table("catalogo_conceptos").update(up_payload).eq("id", id_conc_mod).execute()
                        cambios_cat_guardados += 1
                    except Exception as e:
                        error_cat_msg = f"⚠️ Error al actualizar el concepto: {e}"
                        break

            if error_cat_msg:
                st.toast(error_cat_msg, icon="⚠️")
                st.session_state["ed_cat_counter"] = st.session_state.get("ed_cat_counter", 0) + 1
                st.session_state.pop(ed_cat_key, None)
                st.rerun()
            elif cambios_cat_guardados > 0:
                get_conceptos_cache.clear()
                st.toast("✅ Catálogo actualizado.")
                st.session_state["ed_cat_counter"] = st.session_state.get("ed_cat_counter", 0) + 1
                st.session_state.pop(ed_cat_key, None)
                st.rerun()
    else:
        st.info("ℹ️ No hay conceptos en el presupuesto de este proyecto. Utiliza las opciones superiores para importar desde la Biblioteca, subir un archivo Excel o capturar conceptos manualmente.")
