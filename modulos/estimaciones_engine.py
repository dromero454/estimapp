import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
from modulos.db_engine import extraer_nombre_archivo
from modulos.excel_engine import (
    inyectar_datos_excel_imss, inyectar_datos_excel_pjf,
    generar_excel_estimapp, descargar_plantilla_supabase
)

def registrar_telemetria_clima_silenciosa(supabase, id_estimacion: int, proy_obj: dict, f_inicio: str, f_fin: str):
    """
    Realiza una llamada HTTP GET en segundo plano a la API de Open-Meteo Historical Archive
    para almacenar métricas climáticas oficiales del periodo de corte.
    Salvaguarda Inviolable: Envuelto en try/except silencioso para jamás interrumpir
    ni bloquear la experiencia del usuario si falla la red, la API o no hay coordenadas.
    """
    try:
        if not proy_obj:
            return
        lat = proy_obj.get("latitud")
        lon = proy_obj.get("longitud")
        if lat is None or lon is None:
            return
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (ValueError, TypeError):
            return

        if lat_f == 0.0 and lon_f == 0.0:
            return

        # Evitar registros duplicados si ya existe telemetría previa
        res_ex = supabase.table("telemetria_clima").select("id").eq("id_estimacion", id_estimacion).limit(1).execute()
        if res_ex.data:
            return

        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat_f}&longitude={lon_f}&start_date={f_inicio}&end_date={f_fin}&daily=temperature_2m_mean,temperature_2m_max,precipitation_sum,relative_humidity_2m_mean&timezone=auto"
        req = urllib.request.Request(url, headers={"User-Agent": "Estimapp/2.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())

        daily = data.get("daily", {})
        temp_means = [float(v) for v in daily.get("temperature_2m_mean", []) if v is not None]
        temp_maxs = [float(v) for v in daily.get("temperature_2m_max", []) if v is not None]
        precip_sums = [float(v) for v in daily.get("precipitation_sum", []) if v is not None]
        hum_means = [float(v) for v in daily.get("relative_humidity_2m_mean", []) if v is not None]

        if not temp_means and not precip_sums:
            return

        t_media = round(sum(temp_means) / len(temp_means), 2) if temp_means else None
        t_max = round(sum(temp_maxs) / len(temp_maxs), 2) if temp_maxs else None
        p_total = round(sum(precip_sums), 2) if precip_sums else 0.0
        d_lluvia = sum(1 for p in precip_sums if p > 0.5)
        h_media = round(sum(hum_means) / len(hum_means), 2) if hum_means else None

        supabase.table("telemetria_clima").insert({
            "id_estimacion": id_estimacion,
            "temp_media_c": t_media,
            "temp_max_c": t_max,
            "precipitacion_mm": p_total,
            "dias_lluvia": d_lluvia,
            "humedad_relativa_pct": h_media
        }).execute()
    except Exception:
        # Falla silenciosa total para garantizar continuidad operativa
        pass


def generar_texto_recibo_raya(proy_obj: dict, est_obj: dict, filas_raya: list, total_raya: float) -> str:
    """Genera el contenido estructurado de texto para el Recibo de Liquidación de Raya."""
    obra_nom = proy_obj.get("nombre_obra", "Obra")
    contrato = proy_obj.get("contrato_no", "S/N")
    periodo_str = f"Del {est_obj.get('periodo_inicio')} al {est_obj.get('periodo_fin')}"
    fecha_emision = datetime.date.today().strftime("%d/%m/%Y")

    lineas = [
        "================================================================================",
        "                       RECIBO DE LIQUIDACIÓN DE RAYA Y DESTAJOS                 ",
        "================================================================================",
        f"Proyecto / Obra: {obra_nom}",
        f"Contrato:        {contrato}",
        f"Estimación N°:   {est_obj.get('num_periodo')}",
        f"Periodo de Corte:{periodo_str}",
        f"Fecha Emisión:   {fecha_emision}",
        "--------------------------------------------------------------------------------",
        f"{'TRABAJADOR':<28} | {'ESPECIALIDAD':<15} | {'JORNALES':<9} | {'TARIFA':<10} | {'TOTAL RAYA'}",
        "--------------------------------------------------------------------------------"
    ]

    for r in filas_raya:
        nom = r["Trabajador"][:27]
        esp = r["Especialidad"][:14]
        jorn = f"{r['Jornales']:.2f}"
        tar = f"${r['Tarifa Base ($)']:,.2f}"
        tot = f"${r['Total a Pagar ($)']:,.2f}"
        lineas.append(f"{nom:<28} | {esp:<15} | {jorn:<9} | {tar:<10} | {tot}")

    lineas.extend([
        "--------------------------------------------------------------------------------",
        f"MONTO TOTAL DE RAYA DEL PERIODO: ${total_raya:,.2f} MXN",
        "================================================================================",
        "",
        "Firmas de Conformidad:",
        ""
    ])

    for r in filas_raya:
        lineas.extend([
            f"Trabajador: {r['Trabajador']} ({r['Especialidad']})",
            f"Importe Recibido: ${r['Total a Pagar ($)']:,.2f} MXN",
            "Firma del Trabajador: ___________________________________",
            ""
        ])

    lineas.append("================================================================================")
    return "\n".join(lineas)


def render_estimaciones_tab(supabase, user_id: str, lista_proyectos: list, get_estimaciones, get_conceptos, get_mediciones):
    """
    Renderiza la Pestaña 3: Estimaciones y Raya (modulos/estimaciones_engine.py).
    Permite cortes libres (N días), liquidación de raya y destajos por cuadrilla,
    telemetría meteorológica histórica con Open-Meteo y exportaciones oficiales.
    """
    st.subheader("Periodos de Estimación")

    proyectos_dict = {p["nombre_obra"]: p["id"] for p in lista_proyectos} if lista_proyectos else {}
    if not proyectos_dict:
        st.warning("Registra un proyecto primero.")
        return

    proy_sel_est = st.selectbox("Seleccionar Proyecto", list(proyectos_dict.keys()), key="est_proy")
    id_proy_est = proyectos_dict[proy_sel_est]
    proy_obj_actual = next((p for p in lista_proyectos if p["id"] == id_proy_est), {})
    modalidad_proy = proy_obj_actual.get("modalidad", "publica")

    estimaciones_proyecto = get_estimaciones(id_proy_est)
    periodos_existentes = {int(e["num_periodo"]) for e in estimaciones_proyecto if e.get("num_periodo") is not None} if estimaciones_proyecto else set()
    siguiente_num_periodo = (max(periodos_existentes) + 1) if periodos_existentes else 1

    col_est_nueva, col_est_baja = st.columns(2)

    # -------------------------------------------------------------
    # APERTURA DE NUEVA ESTIMACIÓN (FECHAS LIBRES - N DÍAS)
    # -------------------------------------------------------------
    with col_est_nueva:
        with st.expander("➕ Aperturar nueva estimación"):
            with st.form("form_nueva_estimacion", clear_on_submit=True):
                col_e1, col_e2, col_e3 = st.columns(3)
                num_periodo = col_e1.number_input(
                    "N° Estimación", min_value=1, step=1, value=siguiente_num_periodo,
                    key=f"num_est_input_{id_proy_est}_{st.session_state.get('ed_est_counter', 0)}"
                )
                # Selectores con fechas completamente libres (sin forzar 7 ni 15 días)
                f_ini = col_e2.date_input("Fecha Inicio")
                f_fin = col_e3.date_input("Fecha Fin")

                if st.form_submit_button("Abrir Periodo"):
                    if int(num_periodo) in periodos_existentes:
                        st.error(f"⚠️ La estimación #{int(num_periodo)} ya existe en este proyecto.")
                    elif f_fin < f_ini:
                        st.error("⚠️ La fecha de fin no puede ser anterior a la fecha de inicio.")
                    else:
                        try:
                            res_ins = supabase.table("estimaciones").insert({
                                "id_proyecto": id_proy_est,
                                "num_periodo": int(num_periodo),
                                "periodo_inicio": str(f_ini),
                                "periodo_fin": str(f_fin),
                                "estado": "borrador"
                            }).execute()

                            new_id = res_ins.data[0]["id"] if res_ins.data else None
                            if new_id:
                                # Telemetría Climática Silenciosa en segundo plano
                                registrar_telemetria_clima_silenciosa(
                                    supabase, new_id, proy_obj_actual, str(f_ini), str(f_fin)
                                )

                            get_estimaciones.clear()
                            st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                            st.success(f"Estimación #{num_periodo} aperturada exitosamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al aperturar: {e}")

    dict_est_borrar = {f"#{idx} — Estimación #{e['num_periodo']} ({e['periodo_inicio']} al {e['periodo_fin']})": e["id"] for idx, e in enumerate(estimaciones_proyecto, start=1)} if estimaciones_proyecto else {}

    # -------------------------------------------------------------
    # ELIMINACIÓN DE ESTIMACIÓN (DEFENSIVA Y EN CASCADA)
    # -------------------------------------------------------------
    with col_est_baja:
        with st.expander("🗑️ Eliminar Estimación"):
            if not dict_est_borrar:
                st.info("No hay estimaciones registradas.")
            else:
                del_counter = st.session_state.get("del_est_counter", 0)
                est_del_sel = st.selectbox("Seleccionar estimación:", list(dict_est_borrar.keys()), key=f"del_est_sel_{del_counter}")
                st.warning("⚠️ Al eliminar la estimación también se borrarán todas sus mediciones y registros climáticos asociados.")
                
                if st.button("Eliminar Estimación", type="primary", disabled=not st.checkbox("Confirmo eliminar esta estimación", key=f"chk_del_est_{del_counter}")):
                    id_est_del = dict_est_borrar[est_del_sel]
                    try:
                        # 1. Recolectar evidencias de mediciones asociadas
                        archivos_ev_est = []
                        try:
                            res_meds_est = supabase.table("mediciones_campo").select("url_foto, url_croquis").eq("id_estimacion", id_est_del).execute()
                            for m_row in (res_meds_est.data or []):
                                if m_row.get("url_foto"):
                                    nf = extraer_nombre_archivo(m_row["url_foto"])
                                    if nf: archivos_ev_est.append(nf)
                                if m_row.get("url_croquis"):
                                    nc = extraer_nombre_archivo(m_row["url_croquis"])
                                    if nc: archivos_ev_est.append(nc)
                        except Exception:
                            pass

                        # 2. Borrar primero en BD (PostgreSQL ejecuta CASCADE en mediciones y telemetría)
                        supabase.table("estimaciones").delete().eq("id", id_est_del).execute()

                        # 3. Tras confirmarse en BD, purgar evidencias en Storage
                        if archivos_ev_est:
                            for chunk_ev in [archivos_ev_est[i:i+50] for i in range(0, len(archivos_ev_est), 50)]:
                                try: supabase.storage.from_("evidencias").remove(chunk_ev)
                                except Exception: pass

                        get_estimaciones.clear()
                        get_mediciones.clear()
                        st.session_state["del_est_counter"] = del_counter + 1
                        st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                        st.success("Estimación y mediciones asociadas eliminadas correctamente.")
                        st.rerun()
                    except Exception as ex_del_est:
                        st.error(f"Error al eliminar estimación: {ex_del_est}")

    # =============================================================
    # LISTADO Y EDICIÓN DE ESTIMACIONES
    # =============================================================
    if estimaciones_proyecto:
        st.markdown("##### Listado de Estimaciones:")
        st.caption("💡 *Haz doble clic en cualquier celda para cambiar de estado o corregir las fechas de corte.*")

        if "est_error_banner" in st.session_state and st.session_state["est_error_banner"]:
            st.error(st.session_state.pop("est_error_banner"))

        df_e = pd.DataFrame(estimaciones_proyecto)
        df_e.insert(0, "#", range(1, len(df_e) + 1))
        df_editor_data = df_e[["#", "num_periodo", "periodo_inicio", "periodo_fin", "estado"]].copy()
        df_editor_data["periodo_inicio"] = pd.to_datetime(df_editor_data["periodo_inicio"], errors="coerce").dt.date
        df_editor_data["periodo_fin"] = pd.to_datetime(df_editor_data["periodo_fin"], errors="coerce").dt.date

        ed_est_key = f"editor_estimaciones_{id_proy_est}_{st.session_state.get('ed_est_counter', 0)}"

        edited_table = st.data_editor(
            df_editor_data,
            column_config={
                "#": st.column_config.NumberColumn("#", disabled=True, width=50),
                "num_periodo": st.column_config.NumberColumn("N° Periodo", disabled=True, width=100),
                "periodo_inicio": st.column_config.DateColumn("Fecha Inicio", format="YYYY-MM-DD", required=True),
                "periodo_fin": st.column_config.DateColumn("Fecha Fin", format="YYYY-MM-DD", required=True),
                "estado": st.column_config.SelectboxColumn("Estado de la Estimación", width="medium", options=["borrador", "en_revision", "aprobada"], required=True),
            },
            hide_index=True,
            use_container_width=True,
            key=ed_est_key
        )

        if ed_est_key in st.session_state and st.session_state[ed_est_key].get("edited_rows", {}):
            error_msg = None
            cambios_guardados = 0

            for row_idx_str, col_mod in list(st.session_state[ed_est_key]["edited_rows"].items()):
                try:
                    r_idx = int(row_idx_str)
                except ValueError:
                    continue
                if r_idx >= len(estimaciones_proyecto):
                    continue

                est_actual = estimaciones_proyecto[r_idx]
                id_est_mod = est_actual["id"]
                up_est = {}

                if "estado" in col_mod:
                    val_est = str(col_mod["estado"]).strip() if col_mod["estado"] else ""
                    if val_est in ["borrador", "en_revision", "aprobada"]:
                        up_est["estado"] = val_est
                    else:
                        error_msg = "⚠️ El estado seleccionado no es válido."

                for col_f in ["periodo_inicio", "periodo_fin"]:
                    if col_f in col_mod:
                        val_raw = col_mod[col_f]
                        if val_raw is None or pd.isna(val_raw) or str(val_raw).strip() in ("", "None", "nan", "NaT"):
                            error_msg = "⚠️ La fecha de inicio y la fecha de fin son obligatorias."
                        else:
                            try:
                                d_parsed = pd.to_datetime(str(val_raw).strip()).date()
                                up_est[col_f] = d_parsed.strftime("%Y-%m-%d")
                            except Exception:
                                error_msg = "⚠️ El formato de fecha no es válido."

                if not error_msg:
                    f_ini_check = up_est.get("periodo_inicio", est_actual.get("periodo_inicio"))
                    f_fin_check = up_est.get("periodo_fin", est_actual.get("periodo_fin"))
                    if f_ini_check and f_fin_check and str(f_fin_check) < str(f_ini_check):
                        error_msg = "⚠️ La fecha de fin no puede ser anterior a la fecha de inicio."

                if error_msg:
                    break

                if up_est:
                    try:
                        supabase.table("estimaciones").update(up_est).eq("id", id_est_mod).execute()
                        # Si se actualizan fechas o estado, asegurar telemetría climática
                        f_i_up = up_est.get("periodo_inicio", est_actual.get("periodo_inicio"))
                        f_f_up = up_est.get("periodo_fin", est_actual.get("periodo_fin"))
                        registrar_telemetria_clima_silenciosa(
                            supabase, id_est_mod, proy_obj_actual, str(f_i_up), str(f_f_up)
                        )
                        cambios_guardados += 1
                    except Exception as e:
                        error_msg = f"⚠️ Error al actualizar la estimación: {e}"
                        break

            if error_msg:
                st.session_state["est_error_banner"] = error_msg
                st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                st.session_state.pop(ed_est_key, None)
                st.rerun()
            elif cambios_guardados > 0:
                get_estimaciones.clear()
                st.toast("✅ Estimación actualizada.")
                st.session_state["ed_est_counter"] = st.session_state.get("ed_est_counter", 0) + 1
                st.session_state.pop(ed_est_key, None)
                st.rerun()

        # =============================================================
        # TELEMETRÍA METEOROLÓGICA DEL PERIODO (OPEN-METEO)
        # =============================================================
        ids_estimaciones = [e["id"] for e in estimaciones_proyecto]
        try:
            res_clima = supabase.table("telemetria_clima").select("*").in_("id_estimacion", ids_estimaciones).execute()
            clima_dict = {c["id_estimacion"]: c for c in (res_clima.data or [])}
        except Exception:
            clima_dict = {}

        # =============================================================
        # SUBPANEL: LIQUIDACIÓN DE RAYA Y DESTAJOS (ETAPA 4)
        # =============================================================
        est_labels = [f"Estimación #{e['num_periodo']} (Del {e['periodo_inicio']} al {e['periodo_fin']})" for e in estimaciones_proyecto]
        
        st.markdown("---")
        st.markdown("##### 👷 Liquidación de Raya y Control de Destajos:")
        
        col_sel_est_raya, _ = st.columns([2, 1])
        est_raya_sel_label = col_sel_est_raya.selectbox(
            "Seleccionar Estimación para Auditoría de Raya:",
            est_labels,
            key="sel_est_raya_periodo"
        )

        idx_est_raya = est_labels.index(est_raya_sel_label)
        est_obj_raya = estimaciones_proyecto[idx_est_raya]
        meds_raya = get_mediciones(est_obj_raya["id"])

        # Identificar mediciones con destajistas asignados
        meds_con_trabajador = [m for m in meds_raya if m.get("id_personal") is not None or m.get("personal_obra")]

        # Muestra el subpanel si es modalidad privada/mixta o si hay destajistas asignados
        debe_mostrar_raya = (modalidad_proy in ["privada", "mixta"]) or (len(meds_con_trabajador) > 0)

        if not debe_mostrar_raya:
            st.info("💡 En proyectos de obra pública tradicional, la liquidación de raya es opcional. Asigna destajistas a tus mediciones de campo en la Tab 2 para habilitar este control.")
        else:
            if not meds_con_trabajador:
                st.warning("⚠️ No se registraron mediciones con destajista asignado en este periodo de corte.")
            else:
                # Agrupación por trabajador
                agrupado_trabajadores = {}
                for m in meds_con_trabajador:
                    p_info = m.get("personal_obra") or {}
                    pid = m.get("id_personal") or p_info.get("id") or "desc"
                    nombre_trab = p_info.get("nombre") or f"Trabajador #{pid}"
                    especialidad = p_info.get("especialidad") or "General"
                    costo_jornal = float(p_info.get("costo_jornal_base") or 0.0)
                    
                    jornales = float(m.get("horas_o_jornales") or 1.0)
                    c_info = m.get("catalogo_conceptos") or {}
                    c_clave = c_info.get("clave", "—")

                    if pid not in agrupado_trabajadores:
                        agrupado_trabajadores[pid] = {
                            "Trabajador": nombre_trab,
                            "Especialidad": especialidad,
                            "Jornales": 0.0,
                            "Tarifa Base ($)": costo_jornal,
                            "Conceptos": set(),
                            "Total a Pagar ($)": 0.0
                        }

                    agrupado_trabajadores[pid]["Jornales"] += jornales
                    agrupado_trabajadores[pid]["Conceptos"].add(c_clave)

                filas_raya = []
                total_raya_periodo = 0.0
                total_jornales_periodo = 0.0

                for pid, t_data in agrupado_trabajadores.items():
                    monto_trab = round(t_data["Jornales"] * t_data["Tarifa Base ($)"], 2)
                    t_data["Total a Pagar ($)"] = monto_trab
                    total_raya_periodo += monto_trab
                    total_jornales_periodo += t_data["Jornales"]

                    filas_raya.append({
                        "Trabajador": t_data["Trabajador"],
                        "Especialidad": t_data["Especialidad"],
                        "Conceptos Ejecutados": len(t_data["Conceptos"]),
                        "Jornales": round(t_data["Jornales"], 2),
                        "Tarifa Base ($)": t_data["Tarifa Base ($)"],
                        "Total a Pagar ($)": monto_trab
                    })

                col_r1, col_r2, col_r3 = st.columns(3)
                col_r1.metric("Monto Total de Raya", f"${total_raya_periodo:,.2f} MXN")
                col_r2.metric("Trabajadores en Campo", f"{len(filas_raya)}")
                col_r3.metric("Jornales Acumulados", f"{total_jornales_periodo:.2f}")

                df_raya = pd.DataFrame(filas_raya)
                st.dataframe(
                    df_raya,
                    column_config={
                        "Trabajador": st.column_config.TextColumn("Trabajador", width=180),
                        "Especialidad": st.column_config.TextColumn("Especialidad", width=130),
                        "Conceptos Ejecutados": st.column_config.NumberColumn("Conceptos", width=100),
                        "Jornales": st.column_config.NumberColumn("Jornales", format="%.2f", width=100),
                        "Tarifa Base ($)": st.column_config.NumberColumn("Tarifa Base ($)", format="$%.2f", width=120),
                        "Total a Pagar ($)": st.column_config.NumberColumn("Total Raya ($)", format="$%.2f", width=130),
                    },
                    use_container_width=True,
                    hide_index=True
                )

                # Previsualización y Descarga del Recibo de Raya
                texto_recibo = generar_texto_recibo_raya(proy_obj_actual, est_obj_raya, filas_raya, total_raya_periodo)
                
                col_rec_btn, col_rec_exp = st.columns([1, 2])
                with col_rec_btn:
                    st.download_button(
                        label="📄 Descargar Recibo de Liquidación (TXT)",
                        data=texto_recibo,
                        file_name=f"Recibo_Raya_{proy_obj_actual.get('nombre_obra', 'Obra')}_Est_{est_obj_raya['num_periodo']}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key="btn_descarga_recibo_raya"
                    )

                with st.expander("👁️ Vista Previa del Recibo de Liquidación"):
                    st.text(texto_recibo)

        # Muestra métricas de telemetría si están registradas para la estimación activa
        clima_est = clima_dict.get(est_obj_raya["id"])
        if clima_est:
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            st.info(
                f"🌤️ **Telemetría Meteorológica del Periodo ({est_obj_raya['periodo_inicio']} al {est_obj_raya['periodo_fin']}):** "
                f"Temperatura Media: **{clima_est.get('temp_media_c')} °C** | "
                f"Máxima: **{clima_est.get('temp_max_c')} °C** | "
                f"Precipitación: **{clima_est.get('precipitacion_mm')} mm** | "
                f"Días de Lluvia: **{clima_est.get('dias_lluvia', 0)}**"
            )

        # =============================================================
        # EXPORTACIÓN OFICIAL (IMSS, PJF, ESTIMAPP)
        # =============================================================
        st.markdown("---")
        st.markdown("##### 📥 Exportación Oficial (Formatos Institucionales y Libre)")
        col_exp_1, col_exp_2, col_exp_3 = st.columns([2, 1, 1])

        est_a_descargar = col_exp_1.selectbox("Estimación a Exportar:", est_labels, key="sel_est_export_box")

        # Restricción de plantillas oficiales para Ingrid Gutiérrez
        user_ses = st.session_state.get("user")
        email_sesion_norm = ((getattr(user_ses, "email", "") or "").lower().strip())
        if email_sesion_norm == "ingrid.gutierrez2904@gmail.com":
            opciones_formato_excel = ["IMSS", "Poder Judicial de la Federación", "Formato Estimapp"]
        else:
            opciones_formato_excel = ["Formato Estimapp"]

        formato_institucion = col_exp_2.selectbox("Formato de Salida:", opciones_formato_excel, key="sel_formato_salida_box")

        with col_exp_3:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            btn_generar_excel = st.button("Preparar estimación en formato Excel", type="primary", use_container_width=True, key="btn_prep_excel_box")

        if btn_generar_excel:
            idx_est_sel = est_labels.index(est_a_descargar)
            est_obj_actual = estimaciones_proyecto[idx_est_sel]
            conceptos_cat = get_conceptos(id_proy_est)

            with st.spinner("Generando archivo..."):
                try:
                    if formato_institucion == "IMSS":
                        plantilla_bytes = descargar_plantilla_supabase("plantillas", "plantilla_maestra_estimacion_imss.xlsx")
                        xlsx_generado = inyectar_datos_excel_imss(plantilla_bytes, proy_obj_actual, est_obj_actual, conceptos_cat, estimaciones_proyecto)
                        st.session_state["xls_name"] = f"Estimacion_{est_obj_actual['num_periodo']}_IMSS.xlsx"
                    elif formato_institucion == "Poder Judicial de la Federación":
                        plantilla_bytes = descargar_plantilla_supabase("plantillas", "plantilla_maestra_estimacion_pjf.xlsx")
                        xlsx_generado = inyectar_datos_excel_pjf(plantilla_bytes, proy_obj_actual, est_obj_actual, conceptos_cat, estimaciones_proyecto)
                        st.session_state["xls_name"] = f"Estimacion_{est_obj_actual['num_periodo']}_PJF.xlsx"
                    else:
                        xlsx_generado = generar_excel_estimapp(proy_obj_actual, est_obj_actual, conceptos_cat, estimaciones_proyecto)
                        st.session_state["xls_name"] = f"Estimacion_{est_obj_actual['num_periodo']}_Estimapp.xlsx"

                    st.session_state["xls_buffer"] = xlsx_generado
                except Exception as e:
                    st.error(f"Error: {e}")

        def _on_descarga_excel_completada():
            st.session_state.pop("xls_buffer", None)
            st.session_state.pop("xls_name", None)

        if st.session_state.get("xls_buffer"):
            st.success("✅ Archivo listo para descarga.")
            btn_descarga = st.download_button(
                "⬇️ Descargar Archivo",
                data=st.session_state["xls_buffer"],
                file_name=st.session_state.get("xls_name", "Estimacion.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                on_click=_on_descarga_excel_completada,
                key="btn_descarga_excel_estimacion"
            )
            if btn_descarga:
                _on_descarga_excel_completada()
                st.rerun()
        else:
            st.markdown("<div style='height: 120px; margin-top: 14px;'></div>", unsafe_allow_html=True)
