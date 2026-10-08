import streamlit as st
import pandas as pd
import datetime
import altair as alt
from modulos.db_engine import normalizar_unidad
from modulos.pdf_engine import generar_pdf_resumen_ejecutivo


def render_dashboard_tab(supabase, user_id: str, lista_proyectos: list, get_conceptos, get_estimaciones, get_mediciones):
    """
    Renderiza la Pestaña 1: Resumen Financiero Adaptativo (modulos/dashboard_engine.py).
    Adapta métricas, gráficos interactivos de dona y controles según la modalidad del proyecto activo:
    - 'publica': Tarjetas contractuales tradicionales y avance físico oficial.
    - 'privada': KPIs de rentabilidad real (erogado vs utilidad), gráfica de dona y semáforo de mano de obra.
    - 'mixta': Despliegue en dos columnas paralelas (Control Contractual + Control Operativo Interno) y dona interactiva.
    """
    col_hdr_title, col_hdr_btn = st.columns([2.8, 1.2])
    with col_hdr_title:
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
                    total_destajos_pagados += (cant * c_mo)

    saldo_por_ejercer = round(monto_contratado_total - monto_estimado_global, 2)
    pct_global = round((monto_estimado_global / monto_contratado_total * 100), 2) if monto_contratado_total > 0 else 0.0

    # Factores analíticos operacionales
    pct_ind_proy = float(proy_obj_actual.get("porcentaje_indirectos") or 15.0)
    pct_util_proy = float(proy_obj_actual.get("porcentaje_utilidad") or 15.0)
    pct_herr_proy = float(proy_obj_actual.get("porcentaje_herramienta") or 5.0)

    suma_analitica_erogada = costo_materiales_erogado + total_destajos_pagados + costo_herramienta_erogado + costo_indirectos_erogado
    hay_desglose_analitico = (suma_analitica_erogada > 0)

    # Opción A (Estricta y Transparente): Si el catálogo no tiene desglose analítico (APUs en cero)
    # y no hay destajistas asignados en campo, NO se simulan montos. Todo se muestra en $0.00 reales.
    gasto_erogado_real = round(suma_analitica_erogada, 2)
    utilidad_bruta_real = round(monto_estimado_global - gasto_erogado_real, 2) if (hay_desglose_analitico and monto_estimado_global > 0) else 0.0
    pct_margen_real = round((utilidad_bruta_real / monto_estimado_global * 100), 2) if (hay_desglose_analitico and monto_estimado_global > 0) else 0.0

    # Preparar tabla para el PDF y desglose integral
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

    df_dash = pd.DataFrame(filas_dash)
    if not df_dash.empty:
        df_dash = df_dash.sort_values(by=["_sort_est", "_sort_avance"], ascending=[True, False]).reset_index(drop=True)
        df_dash.insert(3, "#", range(1, len(df_dash) + 1))
        df_dash = df_dash.drop(columns=["_sort_est", "_sort_avance"])

    # Generación y Botón de Descarga alineado a la derecha en la cabecera
    datos_operativos = {
        "gasto_erogado_real": gasto_erogado_real,
        "utilidad_bruta_real": utilidad_bruta_real,
        "pct_margen_real": pct_margen_real,
        "total_destajos_pagados": total_destajos_pagados,
        "costo_materiales_erogado": costo_materiales_erogado,
        "costo_herramienta_erogado": costo_herramienta_erogado,
        "costo_indirectos_erogado": costo_indirectos_erogado
    }
    pdf_bytes = generar_pdf_resumen_ejecutivo(
        proy_info=proy_obj_actual,
        monto_cont=monto_contratado_total,
        monto_est=monto_estimado_global,
        saldo_ejercer=saldo_por_ejercer,
        pct_global=pct_global,
        df_conceptos=df_dash,
        datos_operativos=datos_operativos
    )
    fecha_gen = datetime.date.today().strftime("%d/%m/%Y")
    contrato_nom = proy_obj_actual.get('contrato_no') or 'Obra'

    with col_hdr_btn:
        st.download_button(
            label="📄 Exportar Resumen Ejecutivo (PDF)",
            data=pdf_bytes,
            file_name=f"Resumen_Ejecutivo_{contrato_nom}_{fecha_gen}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="btn_pdf_resumen_ejecutivo_top"
        )

    # Helper para gráfica de dona interactiva con Altair
    def _crear_grafica_dona(df_dist_data):
        df_plot = df_dist_data[df_dist_data["Importe"] > 0]
        if df_plot.empty:
            return None
        return alt.Chart(df_plot).mark_arc(innerRadius=65, outerRadius=110, stroke="#ffffff", strokeWidth=2).encode(
            theta=alt.Theta(field="Importe", type="quantitative"),
            color=alt.Color(
                field="Rubro",
                type="nominal",
                scale=alt.Scale(
                    domain=["Materiales", "Mano de Obra / Destajos", "Herramienta y Equipo", "Gastos Indirectos", "Margen de Utilidad"],
                    range=["#2563EB", "#0D9488", "#F59E0B", "#64748B", "#10B981"]
                ),
                legend=alt.Legend(
                    title="Rubro Financiero",
                    orient="right",
                    labelFontSize=11,
                    titleFontSize=12,
                    symbolType="circle"
                )
            ),
            tooltip=[
                alt.Tooltip("Rubro:N", title="Rubro"),
                alt.Tooltip("Importe:Q", title="Monto ($)", format="$,.2f"),
                alt.Tooltip("Participacion:N", title="Participación")
            ]
        ).properties(
            height=250
        ).configure_view(
            strokeWidth=0
        )

    # DataFrame de distribución de costos
    df_dist = pd.DataFrame({
        "Rubro": ["Materiales", "Mano de Obra / Destajos", "Herramienta y Equipo", "Gastos Indirectos", "Margen de Utilidad"],
        "Importe": [
            max(0.0, costo_materiales_erogado),
            max(0.0, total_destajos_pagados),
            max(0.0, costo_herramienta_erogado),
            max(0.0, costo_indirectos_erogado),
            max(0.0, utilidad_bruta_real)
        ]
    })
    total_dist = df_dist["Importe"].sum()
    df_dist["Porcentaje"] = (df_dist["Importe"] / total_dist * 100.0).round(1) if total_dist > 0 else 0.0
    df_dist["Participacion"] = df_dist["Porcentaje"].apply(lambda p: f"{p:.1f}%")

    # =============================================================
    # RENDERIZADO ADAPTATIVO SEGÚN MODALIDAD
    # =============================================================
    if modalidad_proy == "publica":
        # ---------------- MODO OBRA PÚBLICA (TRADICIONAL) ----------------
        with st.container(border=True):
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Monto Contratado Total", f"${monto_contratado_total:,.2f}")
            kpi2.metric("Monto Estimado Acumulado", f"${monto_estimado_global:,.2f}")
            kpi3.metric("Saldo por Ejercer (Meta = $0)", f"${saldo_por_ejercer:,.2f}", delta=f"{saldo_por_ejercer:,.2f}", delta_color="inverse")
            kpi4.metric("Avance Financiero Global", f"{pct_global:.2f}%")
            st.progress(min(pct_global / 100.0, 1.0))

    elif modalidad_proy == "privada":
        # ---------------- MODO OBRA PRIVADA (RENTABILIDAD INTERNA) ----------------
        with st.container(border=True):
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Presupuesto Pactado Cliente", f"${monto_contratado_total:,.2f}")
            kpi2.metric("Gasto Erogado Real (Obras/Compras)", f"${gasto_erogado_real:,.2f}", delta=f"-${gasto_erogado_real:,.2f}", delta_color="inverse")
            kpi3.metric("Utilidad Bruta Real Erogada", f"${utilidad_bruta_real:,.2f}", delta=f"${utilidad_bruta_real:,.2f}")
            kpi4.metric("Margen Real del Despacho", f"{pct_margen_real:.1f}%")

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

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("##### 📊 Distribución de Costos y Margen del Despacho:")
            col_chart, col_legend_table = st.columns([1.3, 1])
            with col_chart:
                chart_obj = _crear_grafica_dona(df_dist)
                if chart_obj:
                    st.altair_chart(chart_obj, use_container_width=True)
                else:
                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                    st.info("💡 **Este proyecto no cuenta con desglose analítico (APUs) en su catálogo ni destajistas asignados en campo.**\n\nRegistra estos costos para ver la distribución real.")
            with col_legend_table:
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                st.dataframe(
                    df_dist[["Rubro", "Importe", "Porcentaje"]],
                    column_config={
                        "Rubro": st.column_config.TextColumn("Rubro", width=160),
                        "Importe": st.column_config.NumberColumn("Importe", format="$%,.2f", width=120),
                        "Porcentaje": st.column_config.NumberColumn("% Total", format="%.1f%%", width=80)
                    },
                    hide_index=True,
                    use_container_width=True
                )

    else:
        # ---------------- MODO MIXTA / INTEGRAL (COLUMNAS PARALELAS) ----------------
        st.markdown("""
        <style>
        /* Paridad estricta y nivelación de altura entre contenedores paralelos del dashboard */
        [data-testid="column"]:has([data-testid="stVerticalBlockBorderWrapper"]) {
            display: flex !important;
            flex-direction: column !important;
        }
        [data-testid="column"]:has([data-testid="stVerticalBlockBorderWrapper"]) > [data-testid="stVerticalBlock"],
        [data-testid="column"]:has([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]) {
            display: flex !important;
            flex-direction: column !important;
            flex: 1 1 auto !important;
            height: 100% !important;
        }
        [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] {
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
            height: 100% !important;
        }
        [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] {
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
            height: 100% !important;
        }
        </style>
        """, unsafe_allow_html=True)

        col_pub, col_priv = st.columns(2)
        with col_pub:
            with st.container(border=True):
                st.markdown("##### 🏛️ Control Contractual Oficial")
                c_p1, c_p2 = st.columns(2)
                c_p1.metric("Presupuesto Contratado", f"${monto_contratado_total:,.2f}")
                c_p2.metric("Estimado Acumulado", f"${monto_estimado_global:,.2f}")
                c_p3, c_p4 = st.columns(2)
                c_p3.metric("Saldo por Ejercer", f"${saldo_por_ejercer:,.2f}", delta=f"{saldo_por_ejercer:,.2f}", delta_color="inverse")
                c_p4.metric("% Avance Oficial", f"{pct_global:.2f}%")
                st.progress(min(pct_global / 100.0, 1.0))

                # Semáforo de Estado Contractual para paridad visual y de altura
                if saldo_por_ejercer < 0:
                    st.error("🚨 Sobregiro financiero acumulado en estimaciones.")
                elif pct_global >= 100.0:
                    st.success("🟢 Avance contractual al 100% (Meta alcanzada).")
                elif pct_global > 0.0:
                    st.info(f"🔵 Avance contractual en curso ({pct_global:.1f}% ejercido).")
                else:
                    st.info("⚪ Sin estimaciones oficiales aplicadas.")

        with col_priv:
            with st.container(border=True):
                st.markdown("##### 📈 Control Operativo y Rentabilidad")
                c_i1, c_i2 = st.columns(2)
                c_i1.metric("Gasto Erogado Real", f"${gasto_erogado_real:,.2f}", delta=f"-${gasto_erogado_real:,.2f}" if gasto_erogado_real > 0 else None, delta_color="inverse")
                c_i2.metric("Utilidad Bruta Real", f"${utilidad_bruta_real:,.2f}", delta=f"${utilidad_bruta_real:,.2f}" if utilidad_bruta_real > 0 else None)
                c_i3, c_i4 = st.columns(2)
                c_i3.metric("Margen Real del Despacho", f"{pct_margen_real:.1f}%")
                c_i4.metric("Destajos Pagados", f"${total_destajos_pagados:,.2f}")

                # Espaciador para nivelar exactamente la barra de progreso y márgenes de la columna izquierda
                # Sin deltas de gasto/utilidad requiere 59px para paridad milimétrica; con deltas requiere 39px
                espacio_comp = 39 if (gasto_erogado_real > 0 or utilidad_bruta_real > 0) else 59
                st.markdown(f"<div style='height: {espacio_comp}px;'></div>", unsafe_allow_html=True)
                if proy_mo_presupuestada > 0 and total_destajos_pagados > proy_mo_presupuestada:
                    st.error("🚨 Sobregiro en destajos vs. Mano de Obra presupuestada.")
                else:
                    st.success("🟢 Rentabilidad y nómina bajo control.")

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("##### 📊 Distribución de Costos Erogados y Margen de Utilidad:")
            col_chart, col_legend_table = st.columns([1.3, 1])
            with col_chart:
                chart_obj = _crear_grafica_dona(df_dist)
                if chart_obj:
                    st.altair_chart(chart_obj, use_container_width=True)
                else:
                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                    st.info("💡 **Este proyecto no cuenta con desglose analítico (APUs) en su catálogo ni destajistas asignados en campo.**\n\nRegistra estos costos para ver la distribución real.")
            with col_legend_table:
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                st.dataframe(
                    df_dist[["Rubro", "Importe", "Porcentaje"]],
                    column_config={
                        "Rubro": st.column_config.TextColumn("Rubro", width=160),
                        "Importe": st.column_config.NumberColumn("Importe", format="$%,.2f", width=120),
                        "Porcentaje": st.column_config.NumberColumn("% Total", format="%.1f%%", width=80)
                    },
                    hide_index=True,
                    use_container_width=True
                )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # =============================================================
    # AUDITORÍA INTEGRAL DE AVANCE (TABLA DESGLOSE)
    # =============================================================
    st.markdown("##### Desglose por Estimación y Concepto (Auditoría Integral de Avance):")

    if not df_dash.empty:
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
