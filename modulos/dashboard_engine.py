import streamlit as st
import pandas as pd
import datetime
import altair as alt
from modulos.db_engine import normalizar_unidad, get_proveedores
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

    proveedores_dash = get_proveedores(user_id)
    dict_proveedores = {p["id"]: p for p in proveedores_dash}

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
    proy_mat_presupuestado = sum(
        float(c.get("cantidad_contratada") or 0.0) * float(c.get("costo_material") or 0.0)
        for c in conceptos_dash
    )
    proy_herr_presupuestada = sum(
        float(c.get("cantidad_contratada") or 0.0) * float(c.get("costo_herramienta") or 0.0)
        for c in conceptos_dash
    )

    dias_jornadas_vistos = set()
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

                # Computa la mano de obra erogada según modalidad del personal
                p_info = m.get("personal_obra")
                if m.get("id_personal") and p_info:
                    p_mod = p_info.get("modalidad_pago") or "Por Destajo"
                    if p_mod == "Por Jornada":
                        f_dia = str(m.get("fecha") or (m.get("created_at") or ""))[:10]
                        k_dia = (e["id"], f_dia, m.get("id_personal"))
                        if k_dia not in dias_jornadas_vistos:
                            dias_jornadas_vistos.add(k_dia)
                            tarifa_j = float(p_info.get("costo_jornal_base") or 0.0)
                            total_destajos_pagados += tarifa_j
                    else:
                        total_destajos_pagados += (cant * c_mo)
                else:
                    total_destajos_pagados += (cant * c_mo)

    saldo_por_ejercer = round(monto_contratado_total - monto_estimado_global, 2)
    pct_global = round((monto_estimado_global / monto_contratado_total * 100), 2) if monto_contratado_total > 0 else 0.0

    # Factores analíticos operacionales
    pct_ind_proy = float(proy_obj_actual.get("porcentaje_indirectos") or 15.0)
    pct_util_proy = float(proy_obj_actual.get("porcentaje_utilidad") or 15.0)
    pct_herr_proy = float(proy_obj_actual.get("porcentaje_herramienta") or 5.0)
    pct_iva_proy = float(proy_obj_actual.get("porcentaje_iva") or 0.0)
    monto_iva_global = round(monto_estimado_global * (pct_iva_proy / 100.0), 2) if pct_iva_proy > 0 else 0.0
    total_con_iva_global = round(monto_estimado_global + monto_iva_global, 2)

    suma_analitica_erogada = costo_materiales_erogado + total_destajos_pagados + costo_herramienta_erogado + costo_indirectos_erogado
    hay_desglose_analitico = (suma_analitica_erogada > 0)

    # Opción A (Estricta y Transparente): Si el catálogo no tiene desglose analítico (APUs en cero)
    # y no hay destajistas asignados en campo, NO se simulan montos. Todo se muestra en $0.00 reales.
    gasto_erogado_real = round(suma_analitica_erogada, 2)
    utilidad_bruta_real = round(monto_estimado_global - gasto_erogado_real, 2) if (hay_desglose_analitico and monto_estimado_global > 0) else 0.0
    pct_margen_real = round((utilidad_bruta_real / monto_estimado_global * 100), 2) if (hay_desglose_analitico and monto_estimado_global > 0) else 0.0

    # Pre-cálculo de costos analíticos por periodo de estimación
    costos_por_est = {}
    for e_item in estimaciones_dash:
        num_p = e_item["num_periodo"]
        meds_p = get_mediciones(e_item["id"])
        c_mat_p, c_mo_p, c_herr_p, c_ind_p, monto_est_p = 0.0, 0.0, 0.0, 0.0, 0.0
        dias_jornadas_est = set()
        for m in meds_p:
            c_id = m.get("id_concepto")
            cant = float(m.get("cantidad_total") or 0.0)
            if c_id in dict_conceptos_info:
                c_info = dict_conceptos_info[c_id]
                pu = float(c_info.get("precio_unitario") or 0.0)
                monto_est_p += (cant * pu)
                c_mat_p += (cant * float(c_info.get("costo_material") or 0.0))
                c_herr_p += (cant * float(c_info.get("costo_herramienta") or 0.0))
                c_ind_p += (cant * float(c_info.get("costo_indirecto") or 0.0))
                
                p_info = m.get("personal_obra")
                if m.get("id_personal") and p_info:
                    p_mod = p_info.get("modalidad_pago") or "Por Destajo"
                    if p_mod == "Por Jornada":
                        f_dia = str(m.get("fecha") or (m.get("created_at") or ""))[:10]
                        k_dia = (f_dia, m.get("id_personal"))
                        if k_dia not in dias_jornadas_est:
                            dias_jornadas_est.add(k_dia)
                            c_mo_p += float(p_info.get("costo_jornal_base") or 0.0)
                    else:
                        c_mo_p += (cant * float(c_info.get("costo_mano_obra") or 0.0))
                else:
                    c_mo_p += (cant * float(c_info.get("costo_mano_obra") or 0.0))

        gasto_erog_p = c_mat_p + c_mo_p + c_herr_p + c_ind_p
        c_util_p = round(max(0.0, monto_est_p - gasto_erog_p), 2) if gasto_erog_p > 0 else 0.0
        costos_por_est[num_p] = {
            "mat": c_mat_p,
            "mo": c_mo_p,
            "herr": c_herr_p,
            "ind": c_ind_p,
            "util": c_util_p,
            "monto": monto_est_p
        }

    # Helper para calcular la distribución de costos por periodo o acumulada con columna Estatus dinámica
    def _calcular_df_distribucion(sel_filtro):
        if sel_filtro == "Total Acumulado":
            c_mat = sum(v["mat"] for v in costos_por_est.values())
            c_mo = sum(v["mo"] for v in costos_por_est.values())
            c_herr = sum(v["herr"] for v in costos_por_est.values())
            c_ind = sum(v["ind"] for v in costos_por_est.values())
            c_util = sum(v["util"] for v in costos_por_est.values())
            c_mat_eval = c_mat
            c_mo_eval = c_mo
        else:
            num_p = int(sel_filtro.replace("Estimación #", "").strip())
            datos_p = costos_por_est.get(num_p, {"mat": 0.0, "mo": 0.0, "herr": 0.0, "ind": 0.0, "util": 0.0})
            c_mat = datos_p["mat"]
            c_mo = datos_p["mo"]
            c_herr = datos_p["herr"]
            c_ind = datos_p["ind"]
            c_util = datos_p["util"]
            c_mat_eval = sum(v["mat"] for k, v in costos_por_est.items() if k <= num_p)
            c_mo_eval = sum(v["mo"] for k, v in costos_por_est.items() if k <= num_p)

        df_res = pd.DataFrame({
            "Rubro": ["Materiales", "Mano de Obra / Destajos", "Herramienta y Equipo", "Gastos Indirectos", "Margen de Utilidad"],
            "Importe": [max(0.0, c_mat), max(0.0, c_mo), max(0.0, c_herr), max(0.0, c_ind), max(0.0, c_util)]
        })
        t_dist = df_res["Importe"].sum()
        df_res["Porcentaje"] = (df_res["Importe"] / t_dist * 100.0).round(1) if t_dist > 0 else 0.0
        df_res["Participacion"] = df_res["Porcentaje"].apply(lambda p: f"{p:.1f}%")

        if t_dist == 0:
            df_res["Estatus"] = ["⚪ Sin movimientos"] * 5
            return df_res

        # 1. Materiales (evaluado contra costo base presupuestado)
        if proy_mat_presupuestado > 0:
            if c_mat_eval > proy_mat_presupuestado:
                est_mat = f"🔴 Excedido (Presup: ${proy_mat_presupuestado:,.2f})"
            else:
                est_mat = f"🟢 En rango (Presup: ${proy_mat_presupuestado:,.2f})"
        else:
            est_mat = "⚪ Sin costo base"

        # 2. Mano de Obra (evaluado contra presupuesto pactado)
        if proy_mo_presupuestada > 0:
            if c_mo_eval > proy_mo_presupuestada:
                est_mo = f"🔴 Excedido (Presup: ${proy_mo_presupuestada:,.2f})"
            else:
                est_mo = f"🟢 En rango (Presup: ${proy_mo_presupuestada:,.2f})"
        else:
            est_mo = "⚪ Sin presupuesto pactado"

        # 3. Herramienta y Equipo (evaluado contra porcentaje objetivo del proyecto)
        pct_herr_act = float(df_res.loc[df_res["Rubro"] == "Herramienta y Equipo", "Porcentaje"].values[0])
        if pct_herr_act <= pct_herr_proy:
            est_herr = f"🟢 En rango (Meta: ≤ {pct_herr_proy:.1f}%)"
        else:
            est_herr = f"🔴 Excedido (Meta: {pct_herr_proy:.1f}%)"

        # 4. Gastos Indirectos (evaluado contra porcentaje objetivo del proyecto)
        pct_ind_act = float(df_res.loc[df_res["Rubro"] == "Gastos Indirectos", "Porcentaje"].values[0])
        if pct_ind_act <= pct_ind_proy:
            est_ind = f"🟢 En rango (Meta: ≤ {pct_ind_proy:.1f}%)"
        else:
            est_ind = f"🔴 Excedido (Meta: {pct_ind_proy:.1f}%)"

        # 5. Margen de Utilidad (3 colores: Rojo si < 0, Amarillo si 0 <= margen < meta, Verde si >= meta)
        pct_util_act = float(df_res.loc[df_res["Rubro"] == "Margen de Utilidad", "Porcentaje"].values[0])
        imp_util_act = float(df_res.loc[df_res["Rubro"] == "Margen de Utilidad", "Importe"].values[0])
        if imp_util_act <= 0 or pct_util_act <= 0:
            est_util = f"🔴 Pérdida ({pct_util_act:.1f}%)"
        elif pct_util_act < pct_util_proy:
            est_util = f"🟡 Bajo meta (Meta: {pct_util_proy:.1f}%)"
        else:
            est_util = f"🟢 En meta (Meta: ≥ {pct_util_proy:.1f}%)"

        df_res["Estatus"] = [est_mat, est_mo, est_herr, est_ind, est_util]
        return df_res

    # Helper para calcular la auditoría y distribución de mano de obra por trabajador/cuadrilla
    def _calcular_df_mano_obra(sel_filtro):
        if sel_filtro == "Total Acumulado":
            ests_a_procesar = estimaciones_dash
        else:
            try:
                num_p = int(str(sel_filtro).replace("Estimación #", "").strip())
                ests_a_procesar = [e for e in estimaciones_dash if e["num_periodo"] == num_p]
            except Exception:
                ests_a_procesar = estimaciones_dash

        all_meds = []
        for e in ests_a_procesar:
            meds_e = get_mediciones(e["id"])
            for m in meds_e:
                m_copy = dict(m)
                m_copy["_id_estimacion"] = e["id"]
                all_meds.append(m_copy)

        tot_destajos = 0.0
        tot_jornadas = 0.0
        tot_sin_asignar = 0.0
        workers = {}
        dias_jornada = set()

        for m in all_meds:
            p_info = m.get("personal_obra")
            c_info = m.get("catalogo_conceptos") or dict_conceptos_info.get(m.get("id_concepto"), {})
            vol = float(m.get("cantidad_total") or 0.0)
            pu_mo = float(c_info.get("costo_mano_obra") or 0.0)
            m_val = round(vol * pu_mo, 2)

            if not p_info and not m.get("id_personal"):
                tot_sin_asignar += m_val
                k = "sin_asignar"
                if k not in workers:
                    workers[k] = {
                        "Trabajador": "Mano de Obra sin Asignar",
                        "Modalidad": "Sin Asignar",
                        "Importe": 0.0,
                        "valor_generado": 0.0,
                        "salario_pagado": 0.0,
                        "Estatus": "⚠️ Pendiente asignar en Tab de Captura en Campo"
                    }
                workers[k]["Importe"] += m_val
                workers[k]["valor_generado"] += m_val
            else:
                pid = m.get("id_personal") or p_info.get("id")
                nombre = p_info.get("nombre") or f"Trabajador #{pid}"
                mod = p_info.get("modalidad_pago") or "Por Destajo"
                tarifa = float(p_info.get("costo_jornal_base") or 0.0)
                fecha = str(m.get("fecha") or (m.get("created_at") or ""))[:10]
                id_est = m.get("_id_estimacion")

                k = (pid, mod)
                if k not in workers:
                    workers[k] = {
                        "Trabajador": nombre,
                        "Modalidad": mod,
                        "Importe": 0.0,
                        "valor_generado": 0.0,
                        "salario_pagado": 0.0,
                        "tarifa": tarifa,
                        "dias": set()
                    }
                workers[k]["valor_generado"] += m_val

                if mod == "Por Destajo":
                    workers[k]["Importe"] += m_val
                    tot_destajos += m_val
                else:
                    k_dia = (id_est, fecha, pid)
                    if k_dia not in dias_jornada:
                        dias_jornada.add(k_dia)
                        workers[k]["dias"].add(k_dia)
                        workers[k]["salario_pagado"] += tarifa
                        workers[k]["Importe"] += tarifa
                        tot_jornadas += tarifa

        for k, w in workers.items():
            if w["Modalidad"] == "Por Destajo":
                w["Estatus"] = "🟢 Liquidado por volumen"
            elif w["Modalidad"] == "Por Jornada":
                gen = w["valor_generado"]
                pag = w["salario_pagado"]
                if gen >= pag:
                    pct = ((gen - pag) / pag * 100.0) if pag > 0 else 0.0
                    w["Estatus"] = f"🟢 Desquitado (+{pct:.0f}%)" if pct > 0 else "🟢 Desquitado (100%)"
                else:
                    pct = ((pag - gen) / pag * 100.0) if pag > 0 else 0.0
                    w["Estatus"] = f"🔴 En déficit (-{pct:.0f}%)"

        gran_total = round(tot_destajos + tot_jornadas + tot_sin_asignar, 2)
        tot_destajos = round(tot_destajos, 2)
        tot_jornadas = round(tot_jornadas, 2)
        tot_sin_asignar = round(tot_sin_asignar, 2)

        filas_mo = []
        for k, w in workers.items():
            imp = round(w["Importe"], 2)
            pct = round((imp / gran_total * 100.0), 1) if gran_total > 0 else 0.0
            filas_mo.append({
                "Trabajador": w["Trabajador"],
                "Modalidad": w["Modalidad"],
                "Importe": imp,
                "Porcentaje": pct,
                "Participacion": f"{pct:.1f}%",
                "Estatus": w["Estatus"]
            })

        filas_mo.sort(key=lambda x: x["Importe"], reverse=True)
        df_mo = pd.DataFrame(filas_mo)
        if df_mo.empty:
            df_mo = pd.DataFrame(columns=["Trabajador", "Modalidad", "Importe", "Porcentaje", "Participacion", "Estatus"])

        kpis_mo = {
            "total": gran_total,
            "destajos": tot_destajos,
            "jornadas": tot_jornadas,
            "sin_asignar": tot_sin_asignar
        }
        return df_mo, kpis_mo

    # Helper para calcular la auditoría y distribución de materiales por proveedor
    def _calcular_df_materiales(sel_filtro):
        if sel_filtro == "Total Acumulado":
            ests_a_procesar = estimaciones_dash
        else:
            try:
                num_p = int(str(sel_filtro).replace("Estimación #", "").strip())
                ests_a_procesar = [e for e in estimaciones_dash if e["num_periodo"] == num_p]
            except Exception:
                ests_a_procesar = estimaciones_dash

        all_meds = []
        for e in ests_a_procesar:
            meds_e = get_mediciones(e["id"])
            for m in meds_e:
                m_copy = dict(m)
                m_copy["_id_estimacion"] = e["id"]
                all_meds.append(m_copy)

        tot_asignado = 0.0
        tot_sin_asignar = 0.0
        provs_accum = {}

        for m in all_meds:
            c_id = m.get("id_concepto")
            c_info = dict_conceptos_info.get(c_id, {})
            vol = float(m.get("cantidad_total") or 0.0)
            pu_mat = float(c_info.get("costo_material") or 0.0)
            m_val = round(vol * pu_mat, 2)

            if m_val <= 0:
                continue

            id_prov = c_info.get("id_proveedor")
            if not id_prov or id_prov not in dict_proveedores:
                tot_sin_asignar += m_val
                k = "sin_asignar"
                if k not in provs_accum:
                    provs_accum[k] = {
                        "Proveedor": "Materiales sin Asignar",
                        "Giro": "Sin Asignar",
                        "Importe": 0.0,
                        "Estatus": "⚠️ Pendiente asignar en Catálogo",
                        "is_sin_asignar": True
                    }
                provs_accum[k]["Importe"] += m_val
            else:
                p_obj = dict_proveedores[id_prov]
                nom = p_obj["nombre_comercial"]
                giro = p_obj.get("giro") or "Materiales"
                k = id_prov
                if k not in provs_accum:
                    provs_accum[k] = {
                        "Proveedor": nom,
                        "Giro": giro,
                        "Importe": 0.0,
                        "Estatus": "🟢 Proveedor Asignado",
                        "is_sin_asignar": False
                    }
                provs_accum[k]["Importe"] += m_val
                tot_asignado += m_val

        gran_total = round(tot_asignado + tot_sin_asignar, 2)
        tot_asignado = round(tot_asignado, 2)
        tot_sin_asignar = round(tot_sin_asignar, 2)

        # 1. Tabla completa (100% de los proveedores ordenados por importe descendente)
        filas_tabla = []
        for k, p in provs_accum.items():
            imp = round(p["Importe"], 2)
            pct = round((imp / gran_total * 100.0), 1) if gran_total > 0 else 0.0
            filas_tabla.append({
                "Proveedor": p["Proveedor"],
                "Giro": p["Giro"],
                "Importe": imp,
                "Porcentaje": pct,
                "Participacion": f"{pct:.1f}%",
                "Estatus": p["Estatus"],
                "is_sin_asignar": p.get("is_sin_asignar", False)
            })

        filas_tabla.sort(key=lambda x: x["Importe"], reverse=True)
        df_mat_table = pd.DataFrame(filas_tabla)
        if df_mat_table.empty:
            df_mat_table = pd.DataFrame(columns=["Proveedor", "Giro", "Importe", "Porcentaje", "Participacion", "Estatus"])

        # 2. Dataset para la Dona: Top 7 + "Otros Proveedores (Consolidado)"
        provs_validos = [f for f in filas_tabla if not f.get("is_sin_asignar")]
        sin_asig = [f for f in filas_tabla if f.get("is_sin_asignar")]

        filas_chart = []
        if len(provs_validos) <= 8:
            filas_chart.extend(provs_validos)
        else:
            top7 = provs_validos[:7]
            resto = provs_validos[7:]
            imp_resto = round(sum(r["Importe"] for r in resto), 2)
            pct_resto = round((imp_resto / gran_total * 100.0), 1) if gran_total > 0 else 0.0
            filas_chart.extend(top7)
            filas_chart.append({
                "Proveedor": "📦 Otros Proveedores (Consolidado)",
                "Giro": "Consolidado",
                "Importe": imp_resto,
                "Porcentaje": pct_resto,
                "Participacion": f"{pct_resto:.1f}%",
                "Estatus": f"🟢 {len(resto)} proveedores menores",
                "is_sin_asignar": False
            })

        if sin_asig:
            filas_chart.extend(sin_asig)

        df_mat_chart = pd.DataFrame(filas_chart)
        if df_mat_chart.empty:
            df_mat_chart = pd.DataFrame(columns=["Proveedor", "Giro", "Importe", "Porcentaje", "Participacion", "Estatus"])

        num_comercios = len([k for k in provs_accum.keys() if k != "sin_asignar" and provs_accum[k]["Importe"] > 0])

        kpis_mat = {
            "total": gran_total,
            "asignado": tot_asignado,
            "sin_asignar": tot_sin_asignar,
            "num_comercios": num_comercios
        }

        return df_mat_table, df_mat_chart, kpis_mat

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
    df_mo_global, _ = _calcular_df_mano_obra("Total Acumulado")
    _, df_mat_chart_global, _ = _calcular_df_materiales("Total Acumulado")

    datos_operativos = {
        "gasto_erogado_real": gasto_erogado_real,
        "utilidad_bruta_real": utilidad_bruta_real,
        "pct_margen_real": pct_margen_real,
        "total_destajos_pagados": total_destajos_pagados,
        "costo_materiales_erogado": costo_materiales_erogado,
        "costo_herramienta_erogado": costo_herramienta_erogado,
        "costo_indirectos_erogado": costo_indirectos_erogado,
        "total_con_iva_global": total_con_iva_global,
        "monto_iva_global": monto_iva_global,
        "pct_iva_proy": pct_iva_proy,
        "df_mo": df_mo_global,
        "df_mat": df_mat_chart_global
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
        return alt.Chart(df_plot).mark_arc(x=175, y=120, innerRadius=65, outerRadius=105, stroke="#ffffff", strokeWidth=2).encode(
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
                    orient="none",
                    legendX=305,
                    legendY=8,
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
            height=240
        ).configure_view(
            strokeWidth=0
        )

    # Helper para gráfica de dona interactiva de Mano de Obra con Altair
    def _crear_grafica_dona_mo(df_mo_data):
        df_plot = df_mo_data[df_mo_data["Importe"] > 0]
        if df_plot.empty:
            return None
        palette = ["#0D9488", "#2563EB", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4", "#10B981", "#6366F1", "#D97706", "#4F46E5"]
        domain_trabs = [t for t in df_plot["Trabajador"].tolist() if t != "Mano de Obra sin Asignar"]
        range_trabs = palette[:len(domain_trabs)]
        if "Mano de Obra sin Asignar" in df_plot["Trabajador"].values:
            domain_trabs.append("Mano de Obra sin Asignar")
            range_trabs.append("#94A3B8")

        return alt.Chart(df_plot).mark_arc(x=175, y=120, innerRadius=65, outerRadius=105, stroke="#ffffff", strokeWidth=2).encode(
            theta=alt.Theta(field="Importe", type="quantitative"),
            color=alt.Color(
                field="Trabajador",
                type="nominal",
                scale=alt.Scale(
                    domain=domain_trabs,
                    range=range_trabs
                ),
                legend=alt.Legend(
                    title="Personal / Asignación",
                    orient="none",
                    legendX=305,
                    legendY=8,
                    labelFontSize=11,
                    titleFontSize=12,
                    symbolType="circle"
                )
            ),
            tooltip=[
                alt.Tooltip("Trabajador:N", title="Trabajador / Cuadrilla"),
                alt.Tooltip("Modalidad:N", title="Modalidad"),
                alt.Tooltip("Importe:Q", title="Importe ($)", format="$,.2f"),
                alt.Tooltip("Participacion:N", title="% Participación")
            ]
        ).properties(
            height=240
        ).configure_view(
            strokeWidth=0
        )

    # Helper para gráfica de dona interactiva de Materiales y Proveedores con Altair
    def _crear_grafica_dona_mat(df_mat_data):
        df_plot = df_mat_data[df_mat_data["Importe"] > 0]
        if df_plot.empty:
            return None
        palette_mat = [
            "#2563EB", "#0284C7", "#0D9488", "#10B981", "#8B5CF6", 
            "#EC4899", "#6366F1", "#14B8A6", "#3B82F6", "#4F46E5"
        ]
        
        domain_provs = []
        range_colors = []
        c_idx = 0

        for p in df_plot["Proveedor"].tolist():
            if p not in ("Materiales sin Asignar", "📦 Otros Proveedores (Consolidado)"):
                domain_provs.append(p)
                range_colors.append(palette_mat[c_idx % len(palette_mat)])
                c_idx += 1

        if "📦 Otros Proveedores (Consolidado)" in df_plot["Proveedor"].values:
            domain_provs.append("📦 Otros Proveedores (Consolidado)")
            range_colors.append("#64748B")

        if "Materiales sin Asignar" in df_plot["Proveedor"].values:
            domain_provs.append("Materiales sin Asignar")
            range_colors.append("#F59E0B")

        return alt.Chart(df_plot).mark_arc(
            x=175, y=120, innerRadius=65, outerRadius=105, stroke="#ffffff", strokeWidth=2
        ).encode(
            theta=alt.Theta(field="Importe", type="quantitative"),
            color=alt.Color(
                field="Proveedor",
                type="nominal",
                scale=alt.Scale(
                    domain=domain_provs,
                    range=range_colors
                ),
                legend=alt.Legend(
                    title="Proveedor / Comercio",
                    orient="none",
                    legendX=305,
                    legendY=8,
                    labelFontSize=11,
                    titleFontSize=12,
                    symbolType="circle"
                )
            ),
            tooltip=[
                alt.Tooltip("Proveedor:N", title="Proveedor / Comercio"),
                alt.Tooltip("Giro:N", title="Giro Comercial"),
                alt.Tooltip("Importe:Q", title="Gasto Estimado ($)", format="$,.2f"),
                alt.Tooltip("Participacion:N", title="% Participación")
            ]
        ).properties(
            height=240
        ).configure_view(
            strokeWidth=0
        )

    # Helper maestro para renderizar el contenedor unificado y dinámico de análisis y distribución
    def _render_contenedor_distribucion(key_suffix: str):
        with st.container(border=True):
            col_hdr_izq, col_hdr_der = st.columns([1.0, 1.4])
            with col_hdr_der:
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    sel_enfoque = st.selectbox(
                        "Enfoque de Análisis:",
                        options=[
                            "📊 General: Costos y Margen",
                            "👷 Mano de Obra: Trabajadores y Destajos",
                            "📦 Materiales: Desglose por Proveedor"
                        ],
                        key=f"dash_enfoque_{key_suffix}",
                        label_visibility="collapsed"
                    )
                with col_s2:
                    opciones_filtro_dona = ["Total Acumulado"] + [f"Estimación #{e['num_periodo']}" for e in estimaciones_dash]
                    sel_filtro_dona = st.selectbox(
                        "Filtrar periodo:",
                        options=opciones_filtro_dona,
                        key=f"dash_filtro_dona_{key_suffix}",
                        label_visibility="collapsed"
                    )
            with col_hdr_izq:
                if sel_enfoque == "👷 Mano de Obra: Trabajadores y Destajos":
                    st.markdown("##### 👷 Análisis de Mano de Obra y Nómina:")
                elif sel_enfoque.startswith("📦"):
                    st.markdown("##### 📦 Análisis de Materiales y Proveedores:")
                else:
                    st.markdown("##### 📊 Distribución de Costos y Margen del Despacho:")

            if sel_enfoque == "📊 General: Costos y Margen":
                df_dist_plot = _calcular_df_distribucion(sel_filtro_dona)
                col_chart, col_legend_table = st.columns([1.0, 1.4])
                with col_chart:
                    chart_obj = _crear_grafica_dona(df_dist_plot)
                    if chart_obj:
                        st.altair_chart(chart_obj, use_container_width=True)
                    else:
                        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                        st.info("💡 **Este periodo no cuenta con desglose analítico (APUs) en su catálogo ni destajistas asignados en campo.**\n\nRegistra estos costos para ver la distribución real.")
                with col_legend_table:
                    st.dataframe(
                        df_dist_plot[["Rubro", "Importe", "Porcentaje", "Estatus"]],
                        height=220,
                        column_config={
                            "Rubro": st.column_config.TextColumn("Rubro", width=145),
                            "Importe": st.column_config.NumberColumn("Importe", format="$%,.2f", width=105),
                            "Porcentaje": st.column_config.NumberColumn("% Total", format="%.1f%%", width=70),
                            "Estatus": st.column_config.TextColumn("Estatus", width=240)
                        },
                        hide_index=True,
                        use_container_width=True
                    )

                    # Barra de Liquidación Contable y Fiscal (Opción B)
                    sub_sel = float(df_dist_plot["Importe"].sum())
                    iva_sel = round(sub_sel * (pct_iva_proy / 100.0), 2) if pct_iva_proy > 0 else 0.0
                    tot_iva_sel = round(sub_sel + iva_sel, 2)
                    lbl_iva_sel = f"+${iva_sel:,.2f} ({pct_iva_proy:.1f}%)" if pct_iva_proy > 0 else "$0.00 (Exento)"

                    html_barra_fiscal = (
                        f"<div style='"
                        f"display: flex; justify-content: space-between; align-items: center; "
                        f"background: rgba(14, 165, 233, 0.06); "
                        f"border: 1px solid rgba(14, 165, 233, 0.22); "
                        f"border-radius: 8px; padding: 7px 12px; margin-top: 8px; margin-bottom: 8px; "
                        f"font-size: 0.86rem;'>"
                        f"<div>🏷️ <span style='color: #64748B;'>Subtotal:</span> <b>${sub_sel:,.2f}</b></div>"
                        f"<div>🏛️ <span style='color: #64748B;'>IVA:</span> <b>{lbl_iva_sel}</b></div>"
                        f"<div>💳 <span style='color: #0284C7;'>Total c/IVA:</span> <b style='color: #0369A1; font-size: 0.95rem;'>${tot_iva_sel:,.2f}</b></div>"
                        f"</div>\n"
                        f"<div style='height: 4px;'></div>"
                    )
                    st.markdown(html_barra_fiscal, unsafe_allow_html=True)

            elif sel_enfoque == "👷 Mano de Obra: Trabajadores y Destajos":
                df_mo_plot, kpis_mo_plot = _calcular_df_mano_obra(sel_filtro_dona)

                col_chart, col_legend_table = st.columns([1.0, 1.4])
                with col_chart:
                    chart_mo = _crear_grafica_dona_mo(df_mo_plot)
                    if chart_mo:
                        st.altair_chart(chart_mo, use_container_width=True)
                    else:
                        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                        st.info("💡 **Este periodo no cuenta con registros de mano de obra, destajos ni jornales.**\n\nRegistra mediciones con destajistas o personal en la Tab de Captura en Campo.")
                with col_legend_table:
                    st.dataframe(
                        df_mo_plot[["Trabajador", "Modalidad", "Importe", "Porcentaje", "Estatus"]],
                        height=220,
                        column_config={
                            "Trabajador": st.column_config.TextColumn("Trabajador / Cuadrilla", width=170),
                            "Modalidad": st.column_config.TextColumn("Modalidad", width=90),
                            "Importe": st.column_config.NumberColumn("Importe", format="$%,.2f", width=95),
                            "Porcentaje": st.column_config.NumberColumn("% Total", format="%.1f%%", width=65),
                            "Estatus": st.column_config.TextColumn("Estatus", width=340)
                        },
                        hide_index=True,
                        use_container_width=True
                    )

                    # Barra resumen de nómina con tooltips estilo nativo Streamlit BaseWeb
                    sub_mo = float(df_mo_plot["Importe"].sum()) if not df_mo_plot.empty else 0.0
                    tot_dest = kpis_mo_plot["destajos"]
                    tot_jor = kpis_mo_plot["jornadas"]
                    tot_sin = kpis_mo_plot["sin_asignar"]

                    svg_help = (
                        "<svg viewBox='0 0 16 16' width='14' height='14' fill='none' stroke='currentColor' stroke-width='1.5' "
                        "style='display: inline-block; vertical-align: middle;'>"
                        "<circle cx='8' cy='8' r='7'/>"
                        "<path d='M8 11.5v-1M8 8a1.5 1.5 0 1 0-1.5-1.5'/>"
                        "</svg>"
                    )

                    html_barra_mo = (
                        f"<style>\n"
                        f".st-tip-wrap {{ position: relative; display: inline-flex; align-items: center; cursor: help; margin-left: 5px; vertical-align: middle; white-space: nowrap; }}\n"
                        f".st-tip-icon {{ color: #64748B; opacity: 0.75; transition: opacity 0.15s ease, color 0.15s ease; display: inline-flex; align-items: center; }}\n"
                        f".st-tip-wrap:hover .st-tip-icon {{ opacity: 1; color: #0F172A; }}\n"
                        f".st-tip-box {{ visibility: hidden; opacity: 0; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: #1E293B; color: #F8FAFC; font-size: 0.76rem; font-weight: 400; line-height: 1.35; padding: 7px 11px; border-radius: 6px; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22); white-space: normal; width: max-content; max-width: 250px; z-index: 9999; pointer-events: none; transition: opacity 0.2s ease, transform 0.2s ease; }}\n"
                        f".st-tip-box::after {{ content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border-width: 5px; border-style: solid; border-color: #1E293B transparent transparent transparent; }}\n"
                        f".st-tip-box-left {{ left: 0; transform: none; }}\n"
                        f".st-tip-box-left::after {{ left: 10px; transform: none; }}\n"
                        f".st-tip-box-right {{ right: 0; left: auto; transform: none; }}\n"
                        f".st-tip-box-right::after {{ right: 10px; left: auto; transform: none; }}\n"
                        f".st-tip-wrap:hover .st-tip-box {{ visibility: visible; opacity: 1; transform: translateX(-50%) translateY(-2px); }}\n"
                        f".st-tip-wrap:hover .st-tip-box-left {{ visibility: visible; opacity: 1; transform: translateY(-2px); }}\n"
                        f".st-tip-wrap:hover .st-tip-box-right {{ visibility: visible; opacity: 1; transform: translateY(-2px); }}\n"
                        f"</style>\n"
                        f"<div style='"
                        f"display: flex; justify-content: space-between; align-items: center; "
                        f"background: rgba(13, 148, 136, 0.06); "
                        f"border: 1px solid rgba(13, 148, 136, 0.22); "
                        f"border-radius: 8px; padding: 7px 12px; margin-top: 8px; margin-bottom: 8px; "
                        f"font-size: 0.83rem; white-space: nowrap;'>"
                        f"<div style='display: inline-flex; align-items: center; white-space: nowrap;'>🔨&nbsp;<span style='color: #64748B;'>Destajos:</span>&nbsp;<b>${tot_dest:,.2f}</b>"
                        f"<span class='st-tip-wrap'><span class='st-tip-icon'>{svg_help}</span><span class='st-tip-box st-tip-box-left'>Mano de obra devengada por destajistas según volumen ejecutado y costo unitario de catálogo.</span></span></div>"
                        f"<div style='display: inline-flex; align-items: center; white-space: nowrap;'>⏱️&nbsp;<span style='color: #64748B;'>Jornadas:</span>&nbsp;<b>${tot_jor:,.2f}</b>"
                        f"<span class='st-tip-wrap'><span class='st-tip-icon'>{svg_help}</span><span class='st-tip-box'>Salarios devengados en campo pagados por jornal diario.</span></span></div>"
                        f"<div style='display: inline-flex; align-items: center; white-space: nowrap;'>⚠️&nbsp;<span style='color: #64748B;'>Sin Asignar:</span>&nbsp;<b>${tot_sin:,.2f}</b>"
                        f"<span class='st-tip-wrap'><span class='st-tip-icon'>{svg_help}</span><span class='st-tip-box'>💡 Costo de mano de obra contemplado en catálogo para mediciones cuantificadas que aún no tienen un trabajador o cuadrilla responsable asignado en la Tab de Captura en Campo.</span></span></div>"
                        f"<div style='display: inline-flex; align-items: center; white-space: nowrap;'>💳&nbsp;<span style='color: #0F766E;'>Nómina Total:</span>&nbsp;<b style='color: #0D9488; font-size: 0.93rem;'>${sub_mo:,.2f}</b>"
                        f"<span class='st-tip-wrap'><span class='st-tip-icon'>{svg_help}</span><span class='st-tip-box st-tip-box-right'>Suma total de destajos pagados, jornadas devengadas y mano de obra contemplada sin asignar en el periodo seleccionado.</span></span></div>"
                        f"</div>\n"
                        f"<div style='height: 4px;'></div>"
                    )
                    st.markdown(html_barra_mo, unsafe_allow_html=True)

            else:
                df_mat_table, df_mat_chart, kpis_mat_plot = _calcular_df_materiales(sel_filtro_dona)

                col_chart, col_legend_table = st.columns([1.0, 1.4])
                with col_chart:
                    chart_mat = _crear_grafica_dona_mat(df_mat_chart)
                    if chart_mat:
                        st.altair_chart(chart_mat, use_container_width=True)
                    else:
                        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                        st.info("💡 **Este periodo no cuenta con consumos de materiales cuantificados en obra.**\n\nRegistra mediciones de avance en conceptos con costo de materiales en la Tab de Captura en Campo.")
                with col_legend_table:
                    st.dataframe(
                        df_mat_table[["Proveedor", "Giro", "Importe", "Porcentaje", "Estatus"]],
                        height=220,
                        column_config={
                            "Proveedor": st.column_config.TextColumn("Proveedor / Comercio", width=170),
                            "Giro": st.column_config.TextColumn("Giro Comercial", width=120),
                            "Importe": st.column_config.NumberColumn("Importe", format="$%,.2f", width=95),
                            "Porcentaje": st.column_config.NumberColumn("% Total", format="%.1f%%", width=65),
                            "Estatus": st.column_config.TextColumn("Estatus", width=260)
                        },
                        hide_index=True,
                        use_container_width=True
                    )

                    # Barra resumen de suministros y proveedores con tooltips nativos BaseWeb
                    sub_mat = kpis_mat_plot["total"]
                    tot_asig = kpis_mat_plot["asignado"]
                    tot_sin_mat = kpis_mat_plot["sin_asignar"]
                    n_comercios = kpis_mat_plot["num_comercios"]
                    lbl_com = "proveedor" if n_comercios == 1 else "proveedores"

                    svg_help = (
                        "<svg viewBox='0 0 16 16' width='14' height='14' fill='none' stroke='currentColor' stroke-width='1.5' "
                        "style='display: inline-block; vertical-align: middle;'>"
                        "<circle cx='8' cy='8' r='7'/>"
                        "<path d='M8 11.5v-1M8 8a1.5 1.5 0 1 0-1.5-1.5'/>"
                        "</svg>"
                    )

                    html_barra_mat = (
                        f"<style>\n"
                        f".st-tip-wrap {{ position: relative; display: inline-flex; align-items: center; cursor: help; margin-left: 5px; vertical-align: middle; white-space: nowrap; }}\n"
                        f".st-tip-icon {{ color: #64748B; opacity: 0.75; transition: opacity 0.15s ease, color 0.15s ease; display: inline-flex; align-items: center; }}\n"
                        f".st-tip-wrap:hover .st-tip-icon {{ opacity: 1; color: #0F172A; }}\n"
                        f".st-tip-box {{ visibility: hidden; opacity: 0; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: #1E293B; color: #F8FAFC; font-size: 0.76rem; font-weight: 400; line-height: 1.35; padding: 7px 11px; border-radius: 6px; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22); white-space: normal; width: max-content; max-width: 250px; z-index: 9999; pointer-events: none; transition: opacity 0.2s ease, transform 0.2s ease; }}\n"
                        f".st-tip-box::after {{ content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border-width: 5px; border-style: solid; border-color: #1E293B transparent transparent transparent; }}\n"
                        f".st-tip-box-left {{ left: 0; transform: none; }}\n"
                        f".st-tip-box-left::after {{ left: 10px; transform: none; }}\n"
                        f".st-tip-box-right {{ right: 0; left: auto; transform: none; }}\n"
                        f".st-tip-box-right::after {{ right: 10px; left: auto; transform: none; }}\n"
                        f".st-tip-wrap:hover .st-tip-box {{ visibility: visible; opacity: 1; transform: translateX(-50%) translateY(-2px); }}\n"
                        f".st-tip-wrap:hover .st-tip-box-left {{ visibility: visible; opacity: 1; transform: translateY(-2px); }}\n"
                        f".st-tip-wrap:hover .st-tip-box-right {{ visibility: visible; opacity: 1; transform: translateY(-2px); }}\n"
                        f"</style>\n"
                        f"<div style='"
                        f"display: flex; justify-content: space-between; align-items: center; "
                        f"background: rgba(37, 99, 235, 0.06); "
                        f"border: 1px solid rgba(37, 99, 235, 0.22); "
                        f"border-radius: 8px; padding: 7px 12px; margin-top: 8px; margin-bottom: 8px; "
                        f"font-size: 0.83rem; white-space: nowrap;'>"
                        f"<div style='display: inline-flex; align-items: center; white-space: nowrap;'>🏢&nbsp;<span style='color: #64748B;'>Con Proveedor:</span>&nbsp;<b>${tot_asig:,.2f}</b>"
                        f"<span class='st-tip-wrap'><span class='st-tip-icon'>{svg_help}</span><span class='st-tip-box st-tip-box-left'>Importe de materiales devengado en conceptos respaldados con un comercio o proveedor asignado.</span></span></div>"
                        f"<div style='display: inline-flex; align-items: center; white-space: nowrap;'>⚠️&nbsp;<span style='color: #64748B;'>Sin Asignar:</span>&nbsp;<b>${tot_sin_mat:,.2f}</b>"
                        f"<span class='st-tip-wrap'><span class='st-tip-icon'>{svg_help}</span><span class='st-tip-box'>💡 Costo de materiales devengado en conceptos cuantificados que aún no tienen un proveedor vinculado en el catálogo.</span></span></div>"
                        f"<div style='display: inline-flex; align-items: center; white-space: nowrap;'>🏪&nbsp;<span style='color: #64748B;'>Comercios con Gasto:</span>&nbsp;<b>{n_comercios} {lbl_com}</b>"
                        f"<span class='st-tip-wrap'><span class='st-tip-icon'>{svg_help}</span><span class='st-tip-box'>Número de proveedores comerciales que registran consumo de insumos en el corte seleccionado.</span></span></div>"
                        f"<div style='display: inline-flex; align-items: center; white-space: nowrap;'>📦&nbsp;<span style='color: #1D4ED8;'>Total Materiales:</span>&nbsp;<b style='color: #2563EB; font-size: 0.93rem;'>${sub_mat:,.2f}</b>"
                        f"<span class='st-tip-wrap'><span class='st-tip-icon'>{svg_help}</span><span class='st-tip-box st-tip-box-right'>Costo directo total de materiales ejecutados según las mediciones y volúmenes de obra de este periodo.</span></span></div>"
                        f"</div>\n"
                        f"<div style='height: 4px;'></div>"
                    )
                    st.markdown(html_barra_mat, unsafe_allow_html=True)

    # Distribución global inicial
    df_dist = _calcular_df_distribucion("Total Acumulado")

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
            # Estilo dinámico tricolor para Margen Real (escopado al contenedor de Resumen Global)
            diff_meta = pct_margen_real - pct_util_proy
            if pct_margen_real < pct_util_proy:
                # Flecha hacia abajo obligatoria para estados Amarillo o Rojo
                delta_margen = f"-{abs(diff_meta):.1f}% vs meta ({pct_util_proy:.0f}%)"
            else:
                # Flecha hacia arriba para estado Verde
                delta_margen = f"+{abs(diff_meta):.1f}% vs meta ({pct_util_proy:.0f}%)"

            if pct_margen_real < 0.0:
                # 1) ROJO: Margen estrictamente negativo (< 0%)
                bg_m = "rgba(239, 68, 68, 0.15)"
                col_m = "#DC2626"
            elif pct_margen_real < pct_util_proy:
                # 2) AMARILLO: Idéntico al color de la leyenda de advertencia st.warning (fondo pastel y texto dorado/ámbar)
                bg_m = "rgba(255, 255, 18, 0.25)"
                col_m = "rgb(146, 108, 5)"
            else:
                # 3) VERDE: Margen igual o mayor que el margen meta del proyecto
                bg_m = "rgba(16, 185, 129, 0.15)"
                col_m = "#059669"

            css_margen = (
                f"##### 🏛️ Resumen Global del Proyecto <span id='resumen-global-proyecto'></span>\n"
                f"<style>\n"
                f"div:has(#resumen-global-proyecto) [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'],\n"
                f"[data-testid='stHorizontalBlock']:has([data-testid='stColumn']:nth-child(6)) > [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] {{\n"
                f"    background-color: {bg_m} !important;\n"
                f"    color: {col_m} !important;\n"
                f"}}\n"
                f"div:has(#resumen-global-proyecto) [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] svg,\n"
                f"[data-testid='stHorizontalBlock']:has([data-testid='stColumn']:nth-child(6)) > [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] svg {{\n"
                f"    color: {col_m} !important;\n"
                f"    fill: currentColor !important;\n"
                f"}}\n"
                f"div:has(#resumen-global-proyecto) [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] svg path:first-child,\n"
                f"[data-testid='stHorizontalBlock']:has([data-testid='stColumn']:nth-child(6)) > [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] svg path:first-child {{\n"
                f"    fill: none !important;\n"
                f"}}\n"
                f"div:has(#resumen-global-proyecto) [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] svg path:last-child,\n"
                f"[data-testid='stHorizontalBlock']:has([data-testid='stColumn']:nth-child(6)) > [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] svg path:last-child {{\n"
                f"    fill: currentColor !important;\n"
                f"}}\n"
                f"div:has(#resumen-global-proyecto) [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] p,\n"
                f"[data-testid='stHorizontalBlock']:has([data-testid='stColumn']:nth-child(6)) > [data-testid='stColumn']:nth-child(6) [data-testid='stMetricDelta'] p {{\n"
                f"    color: {col_m} !important;\n"
                f"}}\n"
                f"</style>"
            )
            st.markdown(css_margen, unsafe_allow_html=True)

            kpi1, kpi_iva, kpi_rep, kpi2, kpi3, kpi4 = st.columns(6)
            
            # 1. Presupuesto Pactado
            kpi1.metric("Presupuesto Pactado", f"${monto_contratado_total:,.2f}")

            # 2. Total con I.V.A. (Ubicado entre Presupuesto Pactado y Gasto Reportable)
            if pct_iva_proy > 0:
                delta_iva_kpi = f"+${monto_iva_global:,.2f} ({pct_iva_proy:.1f}% IVA)"
            else:
                delta_iva_kpi = "Sin IVA aplicable (0%)"
            kpi_iva.metric(
                "Total con I.V.A.",
                f"${total_con_iva_global:,.2f}",
                delta=delta_iva_kpi,
                delta_color="off",
                help="Monto total cobrable acumulado amparado en estimaciones incluyendo el Impuesto al Valor Agregado configurado en el proyecto."
            )
            
            # 3. Gasto Reportable (con delta vs Presupuesto Pactado en rojo si sobrepasa)
            diff_rep = monto_estimado_global - monto_contratado_total
            if monto_contratado_total > 0 and diff_rep > 0:
                delta_rep = f"+${diff_rep:,.2f} sobre pactado"
                delta_col_rep = "inverse"
            else:
                delta_rep = f"{(monto_estimado_global/monto_contratado_total*100):.1f}% estimado" if monto_contratado_total > 0 else None
                delta_col_rep = "off"
            kpi_rep.metric(
                "Gasto Reportable", 
                f"${monto_estimado_global:,.2f}", 
                delta=delta_rep, 
                delta_color=delta_col_rep, 
                help="Total acumulado cobrable al cliente amparado en las estimaciones abiertas a precios unitarios de catálogo (Subtotal sin IVA)."
            )
            
            # 4. Gasto Erogado Real (con delta en rojo si excede el pactado)
            diff_erogado = gasto_erogado_real - monto_contratado_total
            if monto_contratado_total > 0 and diff_erogado > 0:
                delta_erog = f"+${diff_erogado:,.2f} sobre pactado"
                delta_col_erog = "inverse"
            else:
                delta_erog = f"{(gasto_erogado_real/monto_contratado_total*100):.1f}% ejercido" if monto_contratado_total > 0 else None
                delta_col_erog = "off"
            kpi2.metric("Gasto Erogado Real", f"${gasto_erogado_real:,.2f}", delta=delta_erog, delta_color=delta_col_erog)

            # 5. Utilidad Bruta Real
            excedente_contrato = max(0.0, monto_estimado_global - monto_contratado_total)
            if excedente_contrato > 0:
                delta_util = f"Sujeta a adenda (${excedente_contrato:,.2f} excedente)"
                delta_col_util = "off"
            else:
                delta_util = f"{pct_margen_real:.1f}% margen"
                delta_col_util = "normal"
            kpi3.metric(
                "Utilidad Bruta Real", 
                f"${utilidad_bruta_real:,.2f}", 
                delta=delta_util, 
                delta_color=delta_col_util, 
                help="Utilidad operativa calculada sobre el total cuantificado en campo vs el costo directo erogado."
            )

            # 6. Margen Real (llamado directamente en kpi4 para alineación milimétrica exacta con los otros 5 KPIs)
            kpi4.metric("Margen Real", f"{pct_margen_real:.1f}%", delta=delta_margen, delta_color="normal")

            # Banner al fondo del contenedor: Conceptos Sobregirados
            conceptos_sobre = [c for c in conceptos_dash if acumulados_cronologicos.get(c["id"], 0.0) > float(c.get("cantidad_contratada") or 0.0)]
            if conceptos_sobre:
                n_sobre = len(conceptos_sobre)
                plural = "s" if n_sobre > 1 else ""
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                st.warning(f"⚠️ **{n_sobre} Concepto{plural} Sobregirado{plural}**, revisa la sección de *Desglose por Estimación y Concepto* para obtener más detalles.")

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        _render_contenedor_distribucion("priv")

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
        _render_contenedor_distribucion("mixta")

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
