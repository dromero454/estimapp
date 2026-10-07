import streamlit as st
import pandas as pd
import datetime
from modulos.db_engine import normalizar_unidad
from modulos.pdf_engine import generar_pdf_resumen_ejecutivo

def render_dashboard_tab(supabase, user_id: str, lista_proyectos: list, get_conceptos, get_estimaciones, get_mediciones):
    """
    Renderiza la Pestaña 1: Resumen Financiero Adaptativo (modulos/dashboard_engine.py).
    Adapta métricas, gráficos y controles según la modalidad del proyecto activo:
    - 'publica': Tarjetas contractuales tradicionales y avance físico oficial.
    - 'privada': KPIs de rentabilidad real (erogado vs utilidad), distribución de costos y semáforo de mano de obra.
    - 'mixta': Despliegue en dos columnas paralelas (Control Contractual + Control Operativo Interno).
    """
    st.markdown("### Control Presupuestal y Balance Financiero Adaptativo 🔗")
    
    proyectos_dict = {p["nombre_obra"]: p["id"] for p in lista_proyectos} if lista_proyectos else {}
    if not proyectos_dict:
        st.info("Registra un proyecto para visualizar el análisis financiero.")
        return

    proy_sel_dash = st.selectbox("Proyecto a Auditar", list(proyectos_dict.keys()), key="dash_proy")
    id_proy_dash = proyectos_dict[proy_sel_dash]
    proy_obj_actual = next((p for p in lista_proyectos if p["id"] == id_proy_dash), {})
    modalidad_proy = proy_obj_actual.get("modalidad", "publica")

    conceptos_dash = get_conceptos(id_proy_dash)
    estimaciones_dash = get_estimaciones(id_proy_dash)

    if not conceptos_dash:
        st.warning("Este proyecto no tiene conceptos en su catálogo.")
        return

    dict_conceptos_info = {c["id"]: c for c in conceptos_dash}
    monto_contratado_total = sum(
        float(c.get("cantidad_contratada") or 0.0) * float(c.get("precio_unitario") or 0.0)
        for c in conceptos_dash
    )

    meds_por_est_conc = {}
    monto_estimado_global = 0.0
    conceptos_con_estimacion = set()

    # Desglose de costos erogados reales
    costo_materiales_erogado = 0.0
    total_destajos_pagados = 0.0
    costo_herramienta_erogado = 0.0
    costo_indirectos_erogado = 0.0

    # Desglose de presupuesto contratado analítico
    proy_mo_presupuestada = sum(
        float(c.get("cantidad_contratada") or 0.0) * float(c.get("costo_mano_obra") or 0.0)
        for c in conceptos_dash
    )

    for e in estimaciones_dash:
        meds = get_mediciones(e["id"])
        for m in meds:
            c_id = m.get("id_concepto")
            if c_id in dict_conceptos_info:
                cant = float(m.get("cantidad_total") or 0.0)
                pu = float(dict_conceptos_info[c_id].get("precio_unitario") or 0.0)
                meds_por_est_conc[(e["id"], c_id)] = meds_por_est_conc.get((e["id"], c_id), 0.0) + cant
                monto_estimado_global += (cant * pu)
                conceptos_con_estimacion.add(c_id)

                c_info = dict_conceptos_info[c_id]
                c_mat = float(c_info.get("costo_material") or 0.0)
                c_mo = float(c_info.get("costo_mano_obra") or 0.0)
                c_herr = float(c_info.get("costo_herramienta") or 0.0)
                c_ind = float(c_info.get("costo_indirecto") or 0.0)

                costo_materiales_erogado += (cant * c_mat)
                costo_herramienta_erogado += (cant * c_herr)
                costo_indirectos_erogado += (cant * c_ind)

                # Si la medición tiene destajista asignado, computa su tarifa base real
                p_info = m.get("personal_obra")
                if m.get("id_personal") and p_info:
                    jornales_m = float(m.get("horas_o_jornales") or 1.0)
                    tarifa_j = float(p_info.get("costo_jornal_base") or 0.0)
                    total_destajos_pagados += (jornales_m * tarifa_j)
                else:
                    # En ausencia de destajista específico, toma la mano de obra presupuestada
                    total_destajos_pagados += (cant * c_mo)

    saldo_por_ejercer = round(monto_contratado_total - monto_estimado_global, 2)
    pct_global = round((monto_estimado_global / monto_contratado_total * 100), 2) if monto_contratado_total > 0 else 0.0

    # Factores analíticos operacionales
    # Si no se desglosaron costos en APU, aplicar distribución por factores del proyecto
    pct_ind_proy = float(proy_obj_actual.get("porcentaje_indirectos") or 15.0)
    pct_util_proy = float(proy_obj_actual.get("porcentaje_utilidad") or 15.0)
    pct_herr_proy = float(proy_obj_actual.get("porcentaje_herramienta") or 5.0)

    suma_analitica_erogada = costo_materiales_erogado + total_destajos_pagados + costo_herramienta_erogado + costo_indirectos_erogado
    
    if suma_analitica_erogada <= 0 and monto_estimado_global > 0:
        # Fallback proporcional elegante si el catálogo no cargó APU desglosado
        factor_cd = 1.0 / (1.0 + (pct_util_proy + pct_ind_proy + pct_herr_proy) / 100.0)
        costo_directo_estimado = monto_estimado_global * factor_cd
        costo_materiales_erogado = round(costo_directo_estimado * 0.55, 2)
        total_destajos_pagados = round(costo_directo_estimado * 0.45, 2)
        costo_herramienta_erogado = round(monto_estimado_global * (pct_herr_proy / 100.0), 2)
        costo_indirectos_erogado = round(monto_estimado_global * (pct_ind_proy / 100.0), 2)

    gasto_erogado_real = round(
        costo_materiales_erogado + total_destajos_pagados + costo_herramienta_erogado + costo_indirectos_erogado, 2
    )
    
    utilidad_bruta_real = round(monto_estimado_global - gasto_erogado_real, 2) if monto_estimado_global > 0 else 0.0
    pct_margen_real = round((utilidad_bruta_real / monto_estimado_global * 100), 2) if monto_estimado_global > 0 else pct_util_proy

    # Si aún no hay estimaciones ejecutadas, mostrar costos proyectados
    if monto_estimado_global == 0.0 and monto_contratado_total > 0:
        gasto_proyectado = round(monto_contratado_total * (1.0 - (pct_util_proy / 100.0)), 2)
        utilidad_proyectada = round(monto_contratado_total * (pct_util_proy / 100.0), 2)
    else:
        gasto_proyectado = gasto_erogado_real
        utilidad_proyectada = utilidad_bruta_real

    # =============================================================
    # RENDERIZADO ADAPTATIVO SEGÚN MODALIDAD
    # =============================================================
    if modalidad_proy == "publica":
        # ---------------- MODO OBRA PÚBLICA (TRADICIONAL) ----------------
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Monto Contratado Total", f"${monto_contratado_total:,.2f}")
        kpi2.metric("Monto Estimado Acumulado", f"${monto_estimado_global:,.2f}")
        kpi3.metric("Saldo por Ejercer (Meta = $0)", f"${saldo_por_ejercer:,.2f}", delta=f"{saldo_por_ejercer:,.2f}", delta_color="inverse")
        kpi4.metric("Avance Financiero Global", f"{pct_global:.2f}%")
        st.progress(min(pct_global / 100.0, 1.0))

    elif modalidad_proy == "privada":
        # ---------------- MODO OBRA PRIVADA (RENTABILIDAD INTERNA) ----------------
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Presupuesto Pactado Cliente", f"${monto_contratado_total:,.2f}")
        kpi2.metric("Gasto Erogado Real (Obras/Compras)", f"${gasto_erogado_real:,.2f}", delta=f"-${gasto_erogado_real:,.2f}", delta_color="inverse")
        kpi3.metric("Utilidad Bruta Real Erogada", f"${utilidad_bruta_real:,.2f}", delta=f"${utilidad_bruta_real:,.2f}")
        kpi4.metric("Margen Real del Despacho", f"{pct_margen_real:.1f}%")

        # Semáforo de Desviación Presupuestal
        if proy_mo_presupuestada > 0:
            ratio_mo = total_destajos_pagados / proy_mo_presupuestada
            if total_destajos_pagados > proy_mo_presupuestada:
                exceso_pct = (ratio_mo - 1.0) * 100
                st.error(f"🚨 **Semáforo Rojo - Sobregiro en Mano de Obra:** El importe erogado en destajos (${total_destajos_pagados:,.2f}) sobrepasa el presupuesto de mano de obra pactado (${proy_mo_presupuestada:,.2f}) en un **{exceso_pct:.1f}%**.")
            elif ratio_mo > 0.85:
                st.warning(f"⚠️ **Semáforo Amarillo - Advertencia de Desviación:** Los destajos erogados alcanzan el **{(ratio_mo*100):.1f}%** de la mano de obra presupuestada (${total_destajos_pagados:,.2f} de ${proy_mo_presupuestada:,.2f}).")
            else:
                st.success("🟢 **Semáforo Verde - Control Óptimo:** La mano de obra y destajos se mantienen dentro de los parámetros presupuestados.")
        else:
            st.info("💡 **Semáforo Financiero:** Registra costos desglosados en el catálogo para activar el semáforo de control de destajos.")

        # Gráfica interactiva de distribución de costos
        st.markdown("##### 📊 Distribución de Costos y Margen del Despacho:")
        df_dist = pd.DataFrame({
            "Rubro": ["Materiales", "Mano de Obra / Destajos", "Herramienta y Equipo", "Gastos Indirectos", "Margen de Utilidad"],
            "Importe ($ MXN)": [
                max(0.0, costo_materiales_erogado),
                max(0.0, total_destajos_pagados),
                max(0.0, costo_herramienta_erogado),
                max(0.0, costo_indirectos_erogado),
                max(0.0, utilidad_bruta_real)
            ]
        })
        st.bar_chart(df_dist.set_index("Rubro"), use_container_width=True)

    else:
        # ---------------- MODO MIXTA / INTEGRAL (COLUMNAS PARALELAS) ----------------
        col_pub, col_priv = st.columns(2)
        with col_pub:
            st.markdown("##### 🏛️ Control Contractual Oficial")
            c_p1, c_p2 = st.columns(2)
            c_p1.metric("Presupuesto Contratado", f"${monto_contratado_total:,.2f}")
            c_p2.metric("Estimado Acumulado", f"${monto_estimado_global:,.2f}")
            c_p3, c_p4 = st.columns(2)
            c_p3.metric("Saldo por Ejercer", f"${saldo_por_ejercer:,.2f}", delta=f"{saldo_por_ejercer:,.2f}", delta_color="inverse")
            c_p4.metric("% Avance Oficial", f"{pct_global:.2f}%")
            st.progress(min(pct_global / 100.0, 1.0))

        with col_priv:
            st.markdown("##### 📈 Control Operativo y Rentabilidad")
            c_i1, c_i2 = st.columns(2)
            c_i1.metric("Gasto Erogado Real", f"${gasto_erogado_real:,.2f}", delta=f"-${gasto_erogado_real:,.2f}", delta_color="inverse")
            c_i2.metric("Utilidad Bruta Real", f"${utilidad_bruta_real:,.2f}", delta=f"${utilidad_bruta_real:,.2f}")
            c_i3, c_i4 = st.columns(2)
            c_i3.metric("Margen Real del Despacho", f"{pct_margen_real:.1f}%")
            c_i4.metric("Destajos Pagados", f"${total_destajos_pagados:,.2f}")

            if proy_mo_presupuestada > 0 and total_destajos_pagados > proy_mo_presupuestada:
                st.error("🚨 Sobregiro en destajos vs. Mano de Obra presupuestada.")
            else:
                st.success("🟢 Rentabilidad y nómina bajo control.")

        st.markdown("##### 📊 Distribución de Costos:")
        df_dist = pd.DataFrame({
            "Rubro": ["Materiales", "Mano de Obra / Destajos", "Herramienta y Equipo", "Gastos Indirectos", "Margen de Utilidad"],
            "Importe ($ MXN)": [
                max(0.0, costo_materiales_erogado),
                max(0.0, total_destajos_pagados),
                max(0.0, costo_herramienta_erogado),
                max(0.0, costo_indirectos_erogado),
                max(0.0, utilidad_bruta_real)
            ]
        })
        st.bar_chart(df_dist.set_index("Rubro"), use_container_width=True)

    st.markdown("---")

    # =============================================================
    # AUDITORÍA INTEGRAL DE AVANCE (TABLA DESGLOSE Y PDF)
    # =============================================================
    filas_dash = []
    acumulados_cronologicos = {c["id"]: 0.0 for c in conceptos_dash}

    for e in estimaciones_dash:
        num_p = e["num_periodo"]
        label_est = f"Estimación #{num_p}"
        for c in conceptos_dash:
            c_id = c["id"]
            if (e["id"], c_id) in meds_por_est_conc:
                cant_periodo = round(meds_por_est_conc[(e["id"], c_id)], 3)
                acumulados_cronologicos[c_id] += cant_periodo
                cant_acum = round(acumulados_cronologicos[c_id], 3)
                cant_cont = float(c.get("cantidad_contratada") or 0.0)
                pu = float(c.get("precio_unitario") or 0.0)
                imp_periodo = round(cant_periodo * pu, 2)
                imp_acum = round(cant_acum * pu, 2)
                saldo_vol = round(cant_cont - cant_acum, 3)
                saldo_fin = round((cant_cont * pu) - imp_acum, 2)
                avance = round((cant_acum / cant_cont * 100), 1) if cant_cont > 0 else 0.0

                if avance > 100.0:
                    estatus_badge = f"🚨 Sobregirado (+{round(avance - 100.0, 1)}%)"
                elif avance == 100.0:
                    estatus_badge = "✅ Concluido (100%)"
                else:
                    estatus_badge = "🟢 En proceso"

                filas_dash.append({
                    "Estimación": label_est,
                    "Periodo": f"{e['periodo_inicio']} al {e['periodo_fin']}",
                    "Estado": e.get("estado", "borrador"),
                    "Clave": c["clave"],
                    "Unidad": normalizar_unidad(c["unidad"]),
                    "Cant. Contratada": cant_cont,
                    "Cant. en Periodo": cant_periodo,
                    "Cant. Acumulada": cant_acum,
                    "Saldo Físico": saldo_vol,
                    "P.U. ($)": pu,
                    "Importe Periodo ($)": imp_periodo,
                    "Importe Acumulado ($)": imp_acum,
                    "Saldo Financiero ($)": saldo_fin,
                    "% Avance": avance,
                    "Estatus": estatus_badge,
                    "_sort_est": num_p,
                    "_sort_avance": avance
                })

    for c in conceptos_dash:
        if c["id"] not in conceptos_con_estimacion:
            cant_cont = float(c.get("cantidad_contratada") or 0.0)
            pu = float(c.get("precio_unitario") or 0.0)
            filas_dash.append({
                "Estimación": "Sin estimar",
                "Periodo": "—",
                "Estado": "pendiente",
                "Clave": c["clave"],
                "Unidad": normalizar_unidad(c["unidad"]),
                "Cant. Contratada": cant_cont,
                "Cant. en Periodo": 0.0,
                "Cant. Acumulada": 0.0,
                "Saldo Físico": cant_cont,
                "P.U. ($)": pu,
                "Importe Periodo ($)": 0.0,
                "Importe Acumulado ($)": 0.0,
                "Saldo Financiero ($)": round(cant_cont * pu, 2),
                "% Avance": 0.0,
                "Estatus": "⚪ Sin iniciar",
                "_sort_est": 9999,
                "_sort_avance": 0.0
            })

    if filas_dash:
        df_dash = pd.DataFrame(filas_dash)
        df_dash = df_dash.sort_values(by=["_sort_est", "_sort_avance"], ascending=[True, False]).reset_index(drop=True)
        df_dash.insert(3, "#", range(1, len(df_dash) + 1))
        df_dash = df_dash.drop(columns=["_sort_est", "_sort_avance"])

        col_titulo_rep, col_btn_pdf = st.columns([3, 1])
        with col_titulo_rep:
            st.markdown("##### Desglose por Estimación y Concepto (Auditoría Integral de Avance):")
        with col_btn_pdf:
            pdf_bytes = generar_pdf_resumen_ejecutivo(
                proy_info=proy_obj_actual,
                monto_cont=monto_contratado_total,
                monto_est=monto_estimado_global,
                saldo_ejercer=saldo_por_ejercer,
                pct_global=pct_global,
                df_conceptos=df_dash
            )
            fecha_gen = datetime.date.today().strftime("%d/%m/%Y")
            contrato_nom = proy_obj_actual.get('contrato_no') or 'Obra'
            st.download_button(
                label="📄 Exportar Resumen Ejecutivo (PDF)",
                data=pdf_bytes,
                file_name=f"Resumen_Ejecutivo_{contrato_nom}_{fecha_gen}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        w_avance_dyn = 125
        max_len_c = df_dash["Clave"].astype(str).map(len).max() if not df_dash.empty else 5
        w_clave_dyn = max(130, min(int(max_len_c * 8.5) + 25, 220))
        max_len_p = df_dash["Periodo"].astype(str).map(len).max() if not df_dash.empty else 15
        w_periodo_dyn = max(170, min(int(max_len_p * 7.8) + 20, 205))

        st.dataframe(
            df_dash,
            column_config={
                "Estimación": st.column_config.TextColumn("Estimación", width=115),
                "Periodo": st.column_config.TextColumn("Fechas de Corte", width=w_periodo_dyn),
                "Estado": st.column_config.TextColumn("Estado", width=95),
                "#": st.column_config.NumberColumn("#", width=50),
                "Clave": st.column_config.TextColumn("Clave", width=w_clave_dyn),
                "Unidad": st.column_config.TextColumn("Unidad", width=65),
                "Cant. Contratada": st.column_config.NumberColumn("Cant. Contratada", format="%.2f", width=105),
                "Cant. en Periodo": st.column_config.NumberColumn("Cant. en Periodo", format="%.2f", width=105),
                "Cant. Acumulada": st.column_config.NumberColumn("Cant. Acumulada", format="%.2f", width=105),
                "Saldo Físico": st.column_config.NumberColumn("Saldo Físico", format="%.2f", width=95),
                "P.U. ($)": st.column_config.NumberColumn("P.U. ($)", format="$%.2f", width=90),
                "Importe Periodo ($)": st.column_config.NumberColumn("Importe Periodo ($)", format="$%.2f", width=125),
                "Importe Acumulado ($)": st.column_config.NumberColumn("Importe Acumulado ($)", format="$%.2f", width=125),
                "Saldo Financiero ($)": st.column_config.NumberColumn("Saldo Financiero ($)", format="$%.2f", width=125),
                "% Avance": st.column_config.ProgressColumn("% Avance", min_value=0, max_value=100, format="%.1f%%", width=w_avance_dyn),
                "Estatus": st.column_config.TextColumn("Estatus"),
            },
            use_container_width=True,
            hide_index=True
        )
