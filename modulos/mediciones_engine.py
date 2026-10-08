import streamlit as st
import pandas as pd
import uuid
from modulos.db_engine import normalizar_unidad, extraer_nombre_archivo, extraer_nombres_archivos, optimizar_imagen

def get_personal_obra_disponible(supabase, user_id: str):
    """Consulta la lista de trabajadores activos para el usuario."""
    try:
        res = supabase.table("personal_obra").select("id, nombre, especialidad, costo_jornal_base")\
            .eq("user_id", user_id)\
            .order("nombre")\
            .execute()
        return res.data or []
    except Exception:
        return []

def render_mediciones_tab(supabase, user_id: str, lista_proyectos: list, get_estimaciones, get_conceptos, get_mediciones):
    """
    Renderiza la Pestaña 2: Captura en Campo (modulos/mediciones_engine.py).
    Soporta generación geométrica integral, evidencias multimedia, vinculación de destajistas
    y registro de horas/jornales invertidos.
    """
    st.subheader("Captura de Mediciones y Evidencia")
    
    proyectos_dict = {p["nombre_obra"]: p["id"] for p in lista_proyectos} if lista_proyectos else {}
    if not proyectos_dict:
        st.warning("Configura tu proyecto primero.")
        return

    proy_sel_cap = st.selectbox("Proyecto", list(proyectos_dict.keys()), key="cap_proy")
    id_proy_cap = proyectos_dict[proy_sel_cap]
    
    lista_est_cap = get_estimaciones(id_proy_cap)
    estimaciones_dict = {f"Estimación #{e['num_periodo']} ({e['estado']})": e["id"] for e in lista_est_cap} if lista_est_cap else {}
    
    lista_conc_cap = get_conceptos(id_proy_cap)
    conceptos_dict = {}
    if lista_conc_cap:
        for c in lista_conc_cap:
            clave_c, desc_c, u_norm = c["clave"], c["descripcion"], normalizar_unidad(c["unidad"])
            desc_limpia = desc_c[len(clave_c):].lstrip(" .:-") if desc_c.lower().startswith(clave_c.lower()) else desc_c
            conceptos_dict[f"{clave_c} — {desc_limpia[:55]}... ({u_norm})"] = c

    if not estimaciones_dict:
        st.error("No hay periodos de estimación abiertos para este proyecto.")
        return
    if not conceptos_dict:
        st.error("No hay conceptos en el catálogo de este proyecto.")
        return

    # Consulta de personal/destajistas disponibles
    personal_lista = get_personal_obra_disponible(supabase, user_id)
    opcion_sin_asignar = "Sin asignar (Cuadrilla general)"
    opciones_personal = [opcion_sin_asignar]
    personal_dict_map = {opcion_sin_asignar: None}
    
    for p in personal_lista:
        p_label = f"{p['nombre']} ({p.get('especialidad') or 'General'})"
        opciones_personal.append(p_label)
        personal_dict_map[p_label] = p["id"]

    # Fila 1: Selección de Estimación y Concepto
    c_est, c_con = st.columns([1, 2])
    est_sel = c_est.selectbox("Periodo Activo", list(estimaciones_dict.keys()))
    conc_sel = c_con.selectbox("Concepto a Cuantificar", list(conceptos_dict.keys()))
    
    id_est = estimaciones_dict[est_sel]
    obj_conc = conceptos_dict[conc_sel]
    id_conc = obj_conc["id"]
    u_base = normalizar_unidad(obj_conc["unidad"])
    pu_conc = float(obj_conc.get("precio_unitario") or 0.0)

    # Detección de cambio de unidad geométrica para sincronizar inputs
    if "last_unidad_cap" not in st.session_state:
        st.session_state.last_unidad_cap = u_base
    if st.session_state.last_unidad_cap != u_base:
        st.session_state.last_unidad_cap = u_base
        st.session_state.dim_counter += 1
        st.rerun()

    st.markdown("---")
    
    # Fila 2: Cabecera con datos del concepto y Selector de Destajista / Jornales (Etapa 4)
    st.markdown(f"**Concepto:** `{obj_conc['clave']}` | **Unidad:** `{u_base}` | **P.U. Contratado:** `${pu_conc:,.2f}`")
    
    c_ver = st.session_state.get("cap_counter", 0)
    d_ver = f"{st.session_state.get('cap_counter', 0)}_{st.session_state.get('dim_counter', 0)}"

    col_dest1, col_dest2 = st.columns([2, 1])
    dest_sel = col_dest1.selectbox(
        "👷 Destajista / Cuadrilla responsable",
        opciones_personal,
        index=0,
        key=f"dest_sel_{c_ver}"
    )
    horas_jornales = col_dest2.number_input(
        "Horas o Jornales invertidos",
        min_value=0.0,
        value=1.0,
        step=0.5,
        key=f"jornales_{c_ver}"
    )

    # Localización y Ejes
    col_loc1, col_loc2, col_loc3 = st.columns(3)
    localizacion = col_loc1.text_input("Localización / Elemento *", placeholder="Ej: VESTIDORES - MURO FONDO...", key=f"input_loc_{c_ver}")
    eje = col_loc2.text_input("Eje", placeholder="Ej: 2, A-B...", key=f"input_eje_{c_ver}")
    tramo = col_loc3.text_input("Tramo", placeholder="Ej: 1-2, EJE C...", key=f"input_tramo_{c_ver}")

    # Definición de banderas de dimensión
    es_m3, es_m2, es_kg, es_lt = (u_base=="m³"), (u_base=="m²"), (u_base=="kg"), (u_base=="litros")
    es_h, es_m3km, es_lin = (u_base=="mano de obra (h)"), (u_base=="m³/km"), (u_base in ["m", "tramo"])
    
    tipo_geom = "Rectangular / Cuadrada"
    if es_m2:
        tipo_geom = st.selectbox("Tipo de Geometría:", ["Rectangular / Cuadrada", "Triangular", "Trapecio Regular"], key=f"geom_sel_{d_ver}")

    if es_m2:
        if tipo_geom == "Triangular":
            label_largo, label_ancho, label_alto = "Base (m)", "Altura (m)", "Alto (m)"
            des_largo, des_ancho, des_alto = False, False, True
        elif tipo_geom == "Trapecio Regular":
            label_largo, label_ancho, label_alto = "Base Mayor - B (m)", "Base Menor - b (m)", "Altura - h (m)"
            des_largo, des_ancho, des_alto = False, False, False
        else:
            label_largo, label_ancho, label_alto = "Largo (m)", "Ancho / Altura (m)", "Alto (m)"
            des_largo, des_ancho, des_alto = False, False, True
        des_kg, des_litros, des_horas = True, True, True
    elif es_m3km:
        label_largo, label_ancho, label_alto = "Distancia (km)", "Volumen (m³)", "Alto (m)"
        des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = False, False, True, True, True, True
    elif es_m3:
        label_largo, label_ancho, label_alto = "Largo (m)", "Ancho (m)", "Alto (m)"
        des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = False, False, False, True, True, True
    elif es_kg:
        label_largo, label_ancho, label_alto = "Largo (m)", "Ancho (m)", "Alto (m)"
        des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = False, True, True, False, True, True
    elif es_lt:
        label_largo, label_ancho, label_alto = "Largo (m)", "Ancho (m)", "Alto (m)"
        des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = True, True, True, True, False, True
    elif es_h:
        label_largo, label_ancho, label_alto = "Largo (m)", "Ancho (m)", "Alto (m)"
        des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = True, True, True, True, True, False
    elif es_lin:
        label_largo, label_ancho, label_alto = "Largo (m)", "Ancho (m)", "Alto (m)"
        des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = False, True, True, True, True, True
    else:
        label_largo, label_ancho, label_alto = "Largo (m)", "Ancho (m)", "Alto (m)"
        des_largo, des_ancho, des_alto, des_kg, des_litros, des_horas = True, True, True, True, True, True

    col_d1, col_d2, col_d3, col_d4, col_d5, col_d6, col_d7 = st.columns(7)
    largo = col_d1.number_input(label_largo, min_value=0.0, value=0.0, step=0.5, key=f"nl_{d_ver}", disabled=des_largo)
    ancho = col_d2.number_input(label_ancho, min_value=0.0, value=0.0, step=0.5, key=f"nan_{d_ver}", disabled=des_ancho)
    alto = col_d3.number_input(label_alto, min_value=0.0, value=0.0, step=0.5, key=f"nal_{d_ver}", disabled=des_alto)
    kilos = col_d4.number_input("Kilos (kg)", min_value=0.0, value=0.0, step=0.5, key=f"nkg_{d_ver}", disabled=des_kg)
    litros = col_d5.number_input("Litros", min_value=0.0, value=0.0, step=0.5, key=f"nlt_{d_ver}", disabled=des_litros)
    horas = col_d6.number_input("Horas (h)", min_value=0.0, value=0.0, step=0.5, key=f"nhr_{d_ver}", disabled=des_horas)
    piezas = col_d7.number_input("Piezas", min_value=1.0, value=1.0, step=1.0, key=f"npz_{d_ver}")

    v_l = 0.0 if des_largo else float(largo)
    v_an = 0.0 if des_ancho else float(ancho)
    v_al = 0.0 if des_alto else float(alto)
    v_kg = 0.0 if des_kg else float(kilos)
    v_lt = 0.0 if des_litros else float(litros)
    v_h = 0.0 if des_horas else float(horas)

    if es_m2:
        if tipo_geom == "Triangular": calc_preview = (v_l * v_an / 2.0) * piezas
        elif tipo_geom == "Trapecio Regular": calc_preview = ((v_l + v_an) / 2.0) * v_al * piezas
        else: calc_preview = (v_l * v_an * piezas) if (v_l > 0 and v_an > 0) else 0.0
    elif es_m3km: calc_preview = v_l * v_an * piezas
    elif es_m3: calc_preview = v_l * v_an * v_al * piezas
    elif es_kg: calc_preview = (v_l * v_kg * piezas) if v_l > 0 else (v_kg * piezas)
    elif es_lt: calc_preview = v_lt * piezas
    elif es_h: calc_preview = v_h * piezas
    elif es_lin: calc_preview = v_l * piezas
    else: calc_preview = piezas

    calc_preview = round(float(calc_preview), 3)
    importe_preview = round(calc_preview * pu_conc, 2)
    st.info(f"📐 Cantidad Calculada: **{calc_preview:.3f} {u_base}** | Importe Estimado: **${importe_preview:,.2f} MXN**")

    col_f1, col_f2 = st.columns(2)
    fotos = col_f1.file_uploader("Fotografías de Evidencia", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"file_foto_{c_ver}")
    croquis_list = col_f2.file_uploader("Croquis / Planos", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"file_croquis_{c_ver}")

    if st.button("💾 Guardar Medición en Generador", type="primary"):
        if calc_preview <= 0:
            st.warning("La cantidad debe ser mayor a 0.")
        elif not localizacion.strip():
            st.warning("Debes indicar la Localización / Elemento.")
        else:
            archivos_subidos_tmp = []
            urls_fotos = []
            urls_croquis = []
            try:
                if fotos:
                    f_items = fotos if isinstance(fotos, list) else [fotos]
                    for f in f_items:
                        contenido_f, mime_f = optimizar_imagen(f)
                        fname_f = f"{uuid.uuid4()}.jpg"
                        supabase.storage.from_("evidencias").upload(fname_f, contenido_f, {"content-type": mime_f})
                        u_f = supabase.storage.from_("evidencias").get_public_url(fname_f)
                        urls_fotos.append(u_f)
                        archivos_subidos_tmp.append(fname_f)
                if croquis_list:
                    c_items = croquis_list if isinstance(croquis_list, list) else [croquis_list]
                    for c in c_items:
                        contenido_c, mime_c = optimizar_imagen(c)
                        fname_c = f"{uuid.uuid4()}.jpg"
                        supabase.storage.from_("evidencias").upload(fname_c, contenido_c, {"content-type": mime_c})
                        u_c = supabase.storage.from_("evidencias").get_public_url(fname_c)
                        urls_croquis.append(u_c)
                        archivos_subidos_tmp.append(fname_c)

                url_foto = ",".join(urls_fotos) if urls_fotos else None
                url_croquis = ",".join(urls_croquis) if urls_croquis else None

                if es_kg: v_an = v_kg
                elif es_lt: v_l = v_lt
                elif es_h: v_l = v_h

                id_destajista = personal_dict_map.get(dest_sel)
                jornales_val = float(horas_jornales) if horas_jornales is not None else 1.0

                supabase.table("mediciones_campo").insert({
                    "id_estimacion": id_est,
                    "id_concepto": id_conc,
                    "localizacion": localizacion.strip(),
                    "eje": eje.strip(),
                    "tramo": tramo.strip(),
                    "largo": v_l,
                    "ancho": v_an,
                    "alto": v_al,
                    "piezas": float(piezas),
                    "cantidad_total": calc_preview,
                    "url_foto": url_foto,
                    "url_croquis": url_croquis,
                    "id_personal": id_destajista,
                    "horas_o_jornales": jornales_val
                }).execute()

                get_mediciones.clear()
                st.session_state.cap_counter = st.session_state.get("cap_counter", 0) + 1
                st.session_state.dim_counter = st.session_state.get("dim_counter", 0) + 1
                st.success("✅ Medición guardada exitosamente.")
                st.rerun()
            except Exception as ex_ins_med:
                if archivos_subidos_tmp:
                    try: supabase.storage.from_("evidencias").remove(archivos_subidos_tmp)
                    except Exception: pass
                st.error(f"Error al guardar medición: {ex_ins_med}")

    # =============================================================
    # TABLA DE MEDICIONES REGISTRADAS EN EL PERIODO
    # =============================================================
    st.markdown("### Mediciones registradas en este periodo:")
    st.caption("💡 *Haz doble clic sobre cualquier celda permitida para editar directamente su valor.*")
    mediciones_periodo = get_mediciones(id_est)

    if mediciones_periodo:
        rows = []
        meds_borrar_dict = {}
        total_periodo_acum = 0.0

        for idx, m in enumerate(mediciones_periodo, start=1):
            c_info = m.get("catalogo_conceptos") or {}
            p_info = m.get("personal_obra") or {}
            
            clave_c = c_info.get("clave", "—")
            u_c = normalizar_unidad(c_info.get("unidad", "pza"))
            pu_c = float(c_info.get("precio_unitario") or 0.0)
            cant_m = float(m.get("cantidad_total") or 0.0)
            imp_m = round(cant_m * pu_c, 2)
            total_periodo_acum += imp_m

            destajista_nom = p_info.get("nombre") if p_info else "Sin asignar"
            jornales_m = float(m.get("horas_o_jornales") or 1.0)

            rows.append({
                "#": idx,
                "id": m["id"],
                "Clave": clave_c,
                "Destajista": destajista_nom,
                "Jornales": jornales_m,
                "Localización": m.get("localizacion") or "",
                "Eje": m.get("eje") or "",
                "Tramo": m.get("tramo") or "",
                "Largo / Factor": float(m.get("largo") or 0.0),
                "Ancho / Kilos": float(m.get("ancho") or 0.0),
                "Alto": float(m.get("alto") or 0.0),
                "Pzas": float(m.get("piezas") or 1.0),
                "Cantidad": cant_m,
                "Unidad": u_c,
                "P.U. ($)": pu_c,
                "Importe ($)": imp_m,
                "Tiene Foto": f"Sí ({len([u for u in str(m.get('url_foto') or '').split(',') if u.strip()])})" if m.get("url_foto") else "No",
                "Tiene Croquis": f"Sí ({len([u for u in str(m.get('url_croquis') or '').split(',') if u.strip()])})" if m.get("url_croquis") else "No"
            })
            meds_borrar_dict[f"#{idx} — {clave_c} ({m.get('localizacion', '')} — {cant_m} {u_c})"] = m

        df_meds = pd.DataFrame(rows)
        ed_med_key = f"editor_mediciones_{id_est}_{st.session_state.get('ed_med_counter', 0)}"
        
        edited_meds = st.data_editor(
            df_meds.drop(columns=["id"]),
            column_config={
                "#": st.column_config.NumberColumn("#", disabled=True, width=50),
                "Clave": st.column_config.TextColumn("Clave", disabled=True, width=110),
                "Destajista": st.column_config.TextColumn("Destajista", disabled=True, width=150),
                "Jornales": st.column_config.NumberColumn("Jornales", format="%.1f", disabled=True, width=80),
                "Localización": st.column_config.TextColumn("Localización", width=160),
                "Eje": st.column_config.TextColumn("Eje", width=90),
                "Tramo": st.column_config.TextColumn("Tramo", width=90),
                "Largo / Factor": st.column_config.NumberColumn("Largo / Factor", format="%.2f", width=100),
                "Ancho / Kilos": st.column_config.NumberColumn("Ancho / Kilos", format="%.2f", width=100),
                "Alto": st.column_config.NumberColumn("Alto", format="%.2f", width=80),
                "Pzas": st.column_config.NumberColumn("Pzas", format="%.1f", width=70),
                "Cantidad": st.column_config.NumberColumn("Cantidad", disabled=True, format="%.3f", width=95),
                "Unidad": st.column_config.TextColumn("Unidad", disabled=True, width=70),
                "P.U. ($)": st.column_config.NumberColumn("P.U. ($)", format="$%.2f", disabled=True, width=90),
                "Importe ($)": st.column_config.NumberColumn("Importe ($)", format="$%.2f", disabled=True, width=115),
                "Tiene Foto": st.column_config.TextColumn("Foto", disabled=True, width=60),
                "Tiene Croquis": st.column_config.TextColumn("Croquis", disabled=True, width=65),
            },
            use_container_width=True,
            hide_index=True,
            key=ed_med_key
        )

        if ed_med_key in st.session_state and st.session_state[ed_med_key].get("edited_rows", {}):
            error_med_msg = None
            cambios_med_guardados = 0

            for row_str, col_vals in list(st.session_state[ed_med_key]["edited_rows"].items()):
                try:
                    r_idx = int(row_str)
                except ValueError:
                    continue
                if r_idx >= len(rows):
                    continue

                up_payload = {}
                id_med_up = rows[r_idx]["id"]

                for k in ["Localización", "Eje", "Tramo"]:
                    if k in col_vals:
                        up_payload[k.lower()] = str(col_vals[k] or "").strip()

                for k in ["Largo / Factor", "Ancho / Kilos", "Alto", "Pzas"]:
                    if k in col_vals:
                        val_k = col_vals[k]
                        try:
                            val_fl = float(val_k) if val_k is not None and str(val_k).strip() not in ("", "None", "nan") else float(rows[r_idx][k])
                        except (ValueError, TypeError):
                            val_fl = float(rows[r_idx][k])

                        if k == "Largo / Factor": up_payload["largo"] = val_fl
                        elif k == "Ancho / Kilos": up_payload["ancho"] = val_fl
                        elif k == "Pzas": up_payload["piezas"] = val_fl
                        else: up_payload["alto"] = val_fl

                if any(k in col_vals for k in ["Largo / Factor", "Ancho / Kilos", "Alto", "Pzas"]):
                    def _safe_float(k_name):
                        v = col_vals.get(k_name)
                        if v is None or str(v).strip() in ("", "None", "nan"):
                            return float(rows[r_idx][k_name])
                        try:
                            return float(v)
                        except (ValueError, TypeError):
                            return float(rows[r_idx][k_name])

                    l_val = _safe_float("Largo / Factor")
                    an_val = _safe_float("Ancho / Kilos")
                    al_val = _safe_float("Alto")
                    pz_val = _safe_float("Pzas")
                    u_item = rows[r_idx]["Unidad"]
                    
                    if u_item == "m³": c_calc = l_val * an_val * al_val * pz_val
                    elif u_item == "m²": c_calc = (l_val * an_val * pz_val) if (l_val > 0 and an_val > 0) else 0.0
                    elif u_item == "m³/km": c_calc = l_val * an_val * pz_val
                    elif u_item == "kg": c_calc = (l_val * an_val * pz_val) if l_val > 0 else (an_val * pz_val)
                    elif u_item in ["m", "tramo", "litros", "mano de obra (h)"]: c_calc = l_val * pz_val
                    else: c_calc = pz_val
                    up_payload["cantidad_total"] = round(c_calc, 3)

                if up_payload:
                    try:
                        supabase.table("mediciones_campo").update(up_payload).eq("id", id_med_up).execute()
                        cambios_med_guardados += 1
                    except Exception as e:
                        error_med_msg = f"⚠️ Error al actualizar medición: {e}"
                        break

            if error_med_msg:
                st.toast(error_med_msg, icon="⚠️")
                st.session_state["ed_med_counter"] = st.session_state.get("ed_med_counter", 0) + 1
                st.session_state.pop(ed_med_key, None)
                st.rerun()
            elif cambios_med_guardados > 0:
                get_mediciones.clear()
                st.toast("✅ Medición actualizada.")
                st.session_state["ed_med_counter"] = st.session_state.get("ed_med_counter", 0) + 1
                st.session_state.pop(ed_med_key, None)
                st.rerun()

        st.metric("Total Estimado en el Periodo (Sin I.V.A.)", f"${total_periodo_acum:,.2f} MXN")

        with st.expander("🗑 Eliminar Mediciones (Borrado Masivo)"):
            del_counter = st.session_state.get("del_med_counter", 0)
            meds_a_borrar_labels = st.multiselect("Seleccionar mediciones a remover:", list(meds_borrar_dict.keys()), key=f"sel_med_del_{del_counter}")
            borrar_todas_meds = st.checkbox("⚠️ Selecciona para eliminar todas las mediciones mostradas en la tabla.", key=f"chk_todas_meds_{del_counter}")
            if borrar_todas_meds:
                meds_a_borrar_labels = list(meds_borrar_dict.keys())

            if st.button("Eliminar Seleccionadas", type="primary", disabled=len(meds_a_borrar_labels)==0, key=f"btn_del_meds_bulk_{del_counter}"):
                ids_to_delete = []
                archivos_a_borrar = []
                for label in meds_a_borrar_labels:
                    obj_med_borrar = meds_borrar_dict[label]
                    ids_to_delete.append(obj_med_borrar["id"])
                    if obj_med_borrar.get("url_foto"):
                        archivos_a_borrar.extend(extraer_nombres_archivos(obj_med_borrar["url_foto"]))
                    if obj_med_borrar.get("url_croquis"):
                        archivos_a_borrar.extend(extraer_nombres_archivos(obj_med_borrar["url_croquis"]))

                try:
                    # 1. Eliminar primero de la base de datos para garantizar integridad
                    if ids_to_delete:
                        for chunk in [ids_to_delete[i:i+50] for i in range(0, len(ids_to_delete), 50)]:
                            supabase.table("mediciones_campo").delete().in_("id", chunk).execute()

                    # 2. Solo tras confirmarse la eliminación en BD, purgar fotos de Storage
                    if archivos_a_borrar:
                        for chunk in [archivos_a_borrar[i:i+50] for i in range(0, len(archivos_a_borrar), 50)]:
                            try: supabase.storage.from_("evidencias").remove(chunk)
                            except Exception: pass

                    get_mediciones.clear()
                    st.session_state["del_med_counter"] = del_counter + 1
                    st.success(f"{len(ids_to_delete)} mediciones eliminadas.")
                    st.rerun()
                except Exception as ex_del_m:
                    st.error(f"Error al eliminar mediciones: {ex_del_m}")
