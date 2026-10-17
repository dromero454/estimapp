import streamlit as st
import io
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generar_pdf_recibo_pagos(
    proy_info: dict,
    est_info: dict,
    filas_destajos: list,
    filas_jornadas: list,
    total_general: float
) -> bytes:
    """
    Genera un recibo oficial de liquidación de pagos y destajos en PDF (ReportLab),
    con diseño corporativo, desglose por destajo (volumen * MO) y por jornada,
    totales consolidados y firmas de conformidad.
    """
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'PagosTitle',
        parent=styles['Heading1'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1A2530"),
        spaceAfter=2,
        fontName="Helvetica-Bold"
    )
    subtitle_style = ParagraphStyle(
        'PagosSubtitle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=10
    )
    section_h_style = ParagraphStyle(
        'PagosSecH',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0D9488"),
        fontName="Helvetica-Bold",
        spaceBefore=6,
        spaceAfter=4
    )
    table_text = ParagraphStyle(
        'PagosTableText',
        parent=styles['Normal'],
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor("#222222")
    )
    table_head = ParagraphStyle(
        'PagosTableHead',
        parent=styles['Normal'],
        fontSize=7.2,
        leading=9.5,
        textColor=colors.white,
        fontName="Helvetica-Bold"
    )

    story.append(Paragraph("ESTIMAPP | RECIBO OFICIAL DE LIQUIDACIÓN DE PAGOS Y DESTAJOS", title_style))
    fecha_emision = datetime.date.today().strftime('%d/%m/%Y')
    p_ini = est_info.get('periodo_inicio', '—')
    p_fin = est_info.get('periodo_fin', '—')
    story.append(Paragraph(f"Fecha de Emisión: {fecha_emision} | Periodo de Corte: Del {p_ini} al {p_fin} | Control de Mano de Obra y Destajos", subtitle_style))

    # Metadatos del Proyecto
    modalidad_lbl = str(proy_info.get('modalidad', 'publica')).capitalize()
    info_data = [
        [
            Paragraph("<b>Proyecto / Obra:</b>", table_text),
            Paragraph(f"{proy_info.get('nombre_obra') or 'N/D'}", table_text),
            Paragraph("<b>Contrato N°:</b>", table_text),
            Paragraph(f"{proy_info.get('contrato_no') or 'S/N'}", table_text)
        ],
        [
            Paragraph("<b>Estimación N°:</b>", table_text),
            Paragraph(f"Estimación #{est_info.get('num_periodo', 1)}", table_text),
            Paragraph("<b>Modalidad:</b>", table_text),
            Paragraph(f"Obra {modalidad_lbl}", table_text)
        ],
        [
            Paragraph("<b>Residente / Sup:</b>", table_text),
            Paragraph(f"{proy_info.get('residente_obra') or 'Supervisión de Obra'}", table_text),
            Paragraph("<b>Contratista:</b>", table_text),
            Paragraph(f"{proy_info.get('contratista') or 'Contratista'}", table_text)
        ]
    ]
    t_info = Table(info_data, colWidths=[80, 215, 80, 165])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 8))

    # KPIs de Liquidación
    total_destajos = sum(float(r.get("Total Destajo ($)", 0.0)) for r in filas_destajos)
    has_salario_diario = any("Salario Diario ($)" in r for r in filas_jornadas)
    if has_salario_diario:
        total_jornadas = sum(float(r.get("Salario Diario ($)") or 0.0) for r in filas_jornadas if r.get("Salario Diario ($)") is not None)
        total_dias = sum(1.0 for r in filas_jornadas if r.get("Salario Diario ($)") is not None)
    else:
        total_jornadas = sum(float(r.get("Total a Pagar ($)", 0.0)) for r in filas_jornadas)
        total_dias = sum(float(r.get("Jornadas", 0.0)) for r in filas_jornadas)

    kpi_data = [
        [
            Paragraph(f"<para align=center><b>Total Pagos por Destajos</b><br/><font size=10 color='#0288D1'><b>${total_destajos:,.2f} MXN</b></font></para>", table_text),
            Paragraph(f"<para align=center><b>Total Pagos por Jornadas</b><br/><font size=10 color='#D97706'><b>${total_jornadas:,.2f} MXN</b> <font size=7>({total_dias:.1f} jor)</font></font></para>", table_text),
            Paragraph(f"<para align=center><b>Gran Total Liquidado</b><br/><font size=10 color='#00875A'><b>${total_general:,.2f} MXN</b></font></para>", table_text)
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[180, 180, 180])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#0D9488")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 8))

    # =============================================================
    # TABLA 1: ACTIVIDADES POR DESTAJO (SUPERIOR)
    # =============================================================
    story.append(Paragraph("<b>1. RELACIÓN DE ACTIVIDADES LIQUIDADAS POR DESTAJO</b>", section_h_style))
    if filas_destajos:
        dest_rows = [
            [
                Paragraph("<para align=center>#</para>", table_head),
                Paragraph("<para align=center>Fecha</para>", table_head),
                Paragraph("Trabajador", table_head),
                Paragraph("Clave", table_head),
                Paragraph("Concepto", table_head),
                Paragraph("<para align=center>Unidad</para>", table_head),
                Paragraph("<para align=right>Volumen</para>", table_head),
                Paragraph("<para align=right>P.U. M.O. ($)</para>", table_head),
                Paragraph("<para align=right>Total Destajo ($)</para>", table_head)
            ]
        ]

        # Agrupación por (Fecha, Trabajador) para combinación visual SPAN (BUG-024)
        groups_dest = []
        curr_key = None
        start_row = 1
        num_grupo = 1

        for i, r in enumerate(filas_destajos):
            key = (str(r.get("Fecha", "")), str(r.get("Trabajador", "")))
            row_idx = i + 1
            if curr_key is None:
                curr_key = key
                start_row = row_idx
            elif key != curr_key:
                groups_dest.append((start_row, row_idx - 1, num_grupo))
                num_grupo += 1
                curr_key = key
                start_row = row_idx
        if curr_key is not None:
            groups_dest.append((start_row, len(filas_destajos), num_grupo))

        row_to_group = {}
        for s_r, e_r, n_g in groups_dest:
            for r_i in range(s_r, e_r + 1):
                row_to_group[r_i] = (s_r, e_r, n_g, r_i == s_r)

        for idx, r in enumerate(filas_destajos, start=1):
            c_desc = str(r.get("Concepto", ""))
            if len(c_desc) > 32:
                c_desc = c_desc[:30] + "..."
            fecha_str = str(r.get("Fecha", ""))
            s_r, e_r, n_g, is_first = row_to_group.get(idx, (idx, idx, idx, True))

            p_num = Paragraph(f"<para align=center>{n_g}</para>", table_text) if is_first else Paragraph("", table_text)
            p_fecha = Paragraph(f"<para align=center>{fecha_str}</para>", table_text) if is_first else Paragraph("", table_text)
            p_trab = Paragraph(f"{r.get('Trabajador', '')}", table_text) if is_first else Paragraph("", table_text)

            dest_rows.append([
                p_num,
                p_fecha,
                p_trab,
                Paragraph(f"{r.get('Clave', '')}", table_text),
                Paragraph(c_desc, table_text),
                Paragraph(f"<para align=center>{r.get('Unidad', '')}</para>", table_text),
                Paragraph(f"<para align=right>{float(r.get('Volumen', 0)):.3f}</para>", table_text),
                Paragraph(f"<para align=right>${float(r.get('P.U. Mano de Obra ($)', 0)):,.2f}</para>", table_text),
                Paragraph(f"<para align=right><b>${float(r.get('Total Destajo ($)', 0)):,.2f}</b></para>", table_text)
            ])
        dest_rows.append([
            Paragraph("", table_text),
            Paragraph("", table_text),
            Paragraph("<b>TOTAL DESTAJOS:</b>", table_text),
            Paragraph("", table_text),
            Paragraph("", table_text),
            Paragraph("", table_text),
            Paragraph("", table_text),
            Paragraph("", table_text),
            Paragraph(f"<para align=right><font color='#0288D1'><b>${total_destajos:,.2f}</b></font></para>", table_text)
        ])
        t_dest = Table(dest_rows, colWidths=[20, 52, 95, 45, 138, 30, 45, 55, 60], repeatRows=1)
        dest_table_style = [
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A2530")),
            ('INNERGRID', (0,0), (-1,-2), 0.5, colors.HexColor("#E2E8F0")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")),
            ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor("#0288D1")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]
        # SPAN en columnas 0 (#), 1 (Fecha) y 2 (Trabajador) para grupos consecutivos
        for s_r, e_r, _ in groups_dest:
            if e_r > s_r:
                dest_table_style.append(('SPAN', (0, s_r), (0, e_r)))
                dest_table_style.append(('SPAN', (1, s_r), (1, e_r)))
                dest_table_style.append(('SPAN', (2, s_r), (2, e_r)))

        t_dest.setStyle(TableStyle(dest_table_style))
        story.append(t_dest)
    else:
        story.append(Paragraph("<i>No se registraron actividades por destajo en este periodo.</i>", table_text))

    story.append(Spacer(1, 8))

    # =============================================================
    # TABLA 2: ACTIVIDADES POR JORNADA (INFERIOR)
    # =============================================================
    story.append(Paragraph("<b>2. RELACIÓN DE ACTIVIDADES LIQUIDADAS POR JORNADA Y DESQUITE</b>", section_h_style))
    if filas_jornadas:
        if has_salario_diario:
            jor_rows = [
                [
                    Paragraph("<para align=center>#</para>", table_head),
                    Paragraph("<para align=center>Fecha</para>", table_head),
                    Paragraph("Trabajador", table_head),
                    Paragraph("Especialidad", table_head),
                    Paragraph("Clave", table_head),
                    Paragraph("Concepto", table_head),
                    Paragraph("<para align=right>Valor M.O. ($)</para>", table_head),
                    Paragraph("<para align=right>Salario D. ($)</para>", table_head),
                    Paragraph("<para align=center>Estatus</para>", table_head)
                ]
            ]

            # Agrupación por (Fecha, Trabajador) para combinación visual SPAN (BUG-024)
            groups_jor = []
            curr_key_j = None
            start_row_j = 1
            num_grupo_j = 1

            for i, r in enumerate(filas_jornadas):
                key = (str(r.get("Fecha", "")), str(r.get("Trabajador", "")))
                row_idx = i + 1
                if curr_key_j is None:
                    curr_key_j = key
                    start_row_j = row_idx
                elif key != curr_key_j:
                    groups_jor.append((start_row_j, row_idx - 1, num_grupo_j))
                    num_grupo_j += 1
                    curr_key_j = key
                    start_row_j = row_idx
            if curr_key_j is not None:
                groups_jor.append((start_row_j, len(filas_jornadas), num_grupo_j))

            row_to_group_jor = {}
            for s_r, e_r, n_g in groups_jor:
                for r_i in range(s_r, e_r + 1):
                    row_to_group_jor[r_i] = (s_r, e_r, n_g, r_i == s_r)

            for idx, r in enumerate(filas_jornadas, start=1):
                c_desc = str(r.get("Concepto", ""))
                if len(c_desc) > 28:
                    c_desc = c_desc[:26] + "..."
                fecha_str = str(r.get("Fecha", ""))
                sd_val = r.get("Salario Diario ($)")
                sd_str = f"${float(sd_val):,.2f}" if (sd_val is not None and str(sd_val).strip() != "") else ""

                est_raw = str(r.get("Estatus de Desquite", ""))
                if "Desquitado" in est_raw:
                    ratio_str = est_raw.replace("🟢", "").strip()
                    est_html = f"<font color='#00875A'><b>{ratio_str}</b></font>"
                elif "déficit" in est_raw or "deficit" in est_raw:
                    ratio_str = est_raw.replace("🔴", "").strip()
                    est_html = f"<font color='#DC2626'><b>{ratio_str}</b></font>"
                else:
                    est_html = est_raw

                val_mo = float(r.get("Valor M.O. Producido ($)", 0.0))
                s_r, e_r, n_g, is_first = row_to_group_jor.get(idx, (idx, idx, idx, True))

                p_num = Paragraph(f"<para align=center>{n_g}</para>", table_text) if is_first else Paragraph("", table_text)
                p_fecha = Paragraph(f"<para align=center>{fecha_str}</para>", table_text) if is_first else Paragraph("", table_text)
                p_trab = Paragraph(f"{r.get('Trabajador', '')}", table_text) if is_first else Paragraph("", table_text)
                p_esp = Paragraph(f"{r.get('Especialidad', '')}", table_text) if is_first else Paragraph("", table_text)
                p_sd = Paragraph(f"<para align=right><b>{sd_str}</b></para>", table_text) if is_first else Paragraph("", table_text)
                p_est = Paragraph(f"<para align=center>{est_html}</para>", table_text) if is_first else Paragraph("", table_text)

                jor_rows.append([
                    p_num,
                    p_fecha,
                    p_trab,
                    p_esp,
                    Paragraph(f"{r.get('Clave', '')}", table_text),
                    Paragraph(c_desc, table_text),
                    Paragraph(f"<para align=right>${val_mo:,.2f}</para>", table_text),
                    p_sd,
                    p_est
                ])
            jor_rows.append([
                Paragraph("", table_text),
                Paragraph("", table_text),
                Paragraph("<b>TOTAL JORNADAS:</b>", table_text),
                Paragraph("", table_text),
                Paragraph("", table_text),
                Paragraph(f"<para align=center><b>({total_dias:.1f} jor)</b></para>", table_text),
                Paragraph("", table_text),
                Paragraph(f"<para align=right><font color='#D97706'><b>${total_jornadas:,.2f}</b></font></para>", table_text),
                Paragraph("", table_text)
            ])
            t_jor = Table(jor_rows, colWidths=[20, 50, 95, 65, 45, 115, 50, 50, 50], repeatRows=1)
            jor_table_style = [
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A2530")),
                ('INNERGRID', (0,0), (-1,-2), 0.5, colors.HexColor("#E2E8F0")),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")),
                ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor("#D97706")),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 2.5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ]
            for s_r, e_r, _ in groups_jor:
                if e_r > s_r:
                    jor_table_style.append(('SPAN', (0, s_r), (0, e_r)))
                    jor_table_style.append(('SPAN', (1, s_r), (1, e_r)))
                    jor_table_style.append(('SPAN', (2, s_r), (2, e_r)))
                    jor_table_style.append(('SPAN', (3, s_r), (3, e_r)))
                    jor_table_style.append(('SPAN', (7, s_r), (7, e_r)))
                    jor_table_style.append(('SPAN', (8, s_r), (8, e_r)))
            t_jor.setStyle(TableStyle(jor_table_style))
        else:
            jor_rows = [
                [
                    Paragraph("<para align=center>#</para>", table_head),
                    Paragraph("Trabajador", table_head),
                    Paragraph("Especialidad / Rol", table_head),
                    Paragraph("<para align=right>Jornadas Trabajadas</para>", table_head),
                    Paragraph("<para align=right>Tarifa por Jornada ($)</para>", table_head),
                    Paragraph("<para align=right>Total a Pagar ($)</para>", table_head)
                ]
            ]
            for idx, r in enumerate(filas_jornadas, start=1):
                jor_rows.append([
                    Paragraph(f"<para align=center>{idx}</para>", table_text),
                    Paragraph(f"{r.get('Trabajador', '')}", table_text),
                    Paragraph(f"{r.get('Especialidad', '')}", table_text),
                    Paragraph(f"<para align=right>{float(r.get('Jornadas', 0)):.2f}</para>", table_text),
                    Paragraph(f"<para align=right>${float(r.get('Tarifa Base ($)', 0)):,.2f}</para>", table_text),
                    Paragraph(f"<para align=right><b>${float(r.get('Total a Pagar ($)', 0)):,.2f}</b></para>", table_text)
                ])
            jor_rows.append([
                Paragraph("", table_text),
                Paragraph("<b>TOTAL JORNADAS:</b>", table_text),
                Paragraph("", table_text),
                Paragraph(f"<para align=right><b>{total_dias:.2f}</b></para>", table_text),
                Paragraph("", table_text),
                Paragraph(f"<para align=right><font color='#D97706'><b>${total_jornadas:,.2f}</b></font></para>", table_text)
            ])
            t_jor = Table(jor_rows, colWidths=[25, 160, 115, 80, 80, 80], repeatRows=1)
            t_jor.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A2530")),
                ('INNERGRID', (0,0), (-1,-2), 0.5, colors.HexColor("#E2E8F0")),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")),
                ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor("#D97706")),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 2.5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ]))
        story.append(t_jor)
    else:
        story.append(Paragraph("<i>No se registraron jornadas laboradas en este periodo.</i>", table_text))

    story.append(Spacer(1, 10))

    # =============================================================
    # CONSTANCIAS DE CONFORMIDAD Y LIQUIDACIÓN EN EFECTIVO
    # =============================================================
    story.append(Paragraph("<b>CONSTANCIA DE CONFORMIDAD Y LIQUIDACIÓN EN EFECTIVO</b>", ParagraphStyle('SubH', parent=styles['Normal'], fontSize=8, leading=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#1A2530"))))
    story.append(Spacer(1, 3))

    # Consolidar trabajadores únicos para recibos
    trabajadores_resumen = {}
    for d in filas_destajos:
        t_nom = d.get("Trabajador", "Trabajador")
        t_esp = d.get("Especialidad", "Destajo")
        if t_nom not in trabajadores_resumen:
            trabajadores_resumen[t_nom] = {"nombre": t_nom, "especialidad": t_esp, "total": 0.0}
        trabajadores_resumen[t_nom]["total"] += float(d.get("Total Destajo ($)", 0.0))

    for j in filas_jornadas:
        t_nom = j.get("Trabajador", "Trabajador")
        t_esp = j.get("Especialidad", "Jornada")
        if t_nom not in trabajadores_resumen:
            trabajadores_resumen[t_nom] = {"nombre": t_nom, "especialidad": t_esp, "total": 0.0}
        
        if has_salario_diario:
            sd = j.get("Salario Diario ($)")
            if sd is not None:
                trabajadores_resumen[t_nom]["total"] += float(sd)
        else:
            trabajadores_resumen[t_nom]["total"] += float(j.get("Total a Pagar ($)", 0.0))

    receipt_rows = []
    for t_nom, t_data in trabajadores_resumen.items():
        receipt_rows.append([
            Paragraph(f"<b>Trabajador:</b> {t_data['nombre']} ({t_data['especialidad']})<br/><b>Importe Recibido:</b> ${t_data['total']:,.2f} MXN", table_text),
            Paragraph("<b>Firma de Recibido:</b><br/><br/>________________________________________", table_text)
        ])

    if receipt_rows:
        t_receipts = Table(receipt_rows, colWidths=[280, 260])
        t_receipts.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FAFAFA")),
        ]))
        story.append(t_receipts)
    story.append(Spacer(1, 12))

    # Firmas del Residente y Contratista
    residente_nom = proy_info.get('residente_obra') or 'Supervisión de Obra'
    contratista_nom = proy_info.get('contratista') or 'Contratista'
    sig_data = [
        [
            Paragraph(f"<para align=center>____________________________________<br/><b>{residente_nom}</b><br/>Residente de Obra / Autorizó Pago</para>", table_text),
            Paragraph(f"<para align=center>____________________________________<br/><b>{contratista_nom}</b><br/>Empresa Contratista / Pagador</para>", table_text)
        ]
    ]
    t_sig = Table(sig_data, colWidths=[270, 270])
    t_sig.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(KeepTogether(t_sig))

    doc.build(story)
    return pdf_buffer.getvalue()


def generar_pdf_recibo_raya(proy_info: dict, est_info: dict, filas_raya: list, total_raya: float) -> bytes:
    """Wrapper de compatibilidad retroactiva hacia generar_pdf_recibo_pagos."""
    return generar_pdf_recibo_pagos(proy_info, est_info, [], filas_raya, total_raya)


def generar_pdf_resumen_ejecutivo(proy_info, monto_cont, monto_est, saldo_ejercer, pct_global, df_conceptos, datos_operativos=None):
    """
    Genera el informe ejecutivo en PDF adaptando su estructura, títulos, KPIs
    y gráficos a la modalidad del proyecto ('publica', 'privada', 'mixta').
    """
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    modalidad = str(proy_info.get("modalidad", "publica")).lower()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=14,
        leading=17,
        textColor=colors.HexColor("#1A2530"),
        spaceAfter=2,
        fontName="Helvetica-Bold"
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=10
    )
    table_text = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#222222")
    )
    table_head = ParagraphStyle(
        'TableHead',
        parent=styles['Normal'],
        fontSize=7,
        leading=9,
        textColor=colors.white,
        fontName="Helvetica-Bold"
    )

    fecha_corte_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

    if modalidad == "privada":
        story.append(Paragraph("ESTIMAPP | INFORME EJECUTIVO DE RENTABILIDAD Y CONTROL DE OBRA PRIVADA", title_style))
        story.append(Paragraph(f"Fecha de corte y emisión: {fecha_corte_str} | Control Operativo Interno, Costos Erogados y Margen de Utilidad", subtitle_style))
    elif modalidad == "mixta":
        story.append(Paragraph("ESTIMAPP | INFORME EJECUTIVO INTEGRAL (CONTROL CONTRACTUAL Y OPERATIVO)", title_style))
        story.append(Paragraph(f"Fecha de corte y emisión: {fecha_corte_str} | Balance Contractual Oficial y Control de Rentabilidad Interna", subtitle_style))
    else:
        story.append(Paragraph("ESTIMAPP | INFORME EJECUTIVO DE CONTROL PRESUPUESTAL", title_style))
        story.append(Paragraph(f"Fecha de corte y emisión: {fecha_corte_str} | Sistema Central de Estimaciones de Obra Pública", subtitle_style))

    desc_sintetica = proy_info.get('descripcion_sintetica') or 'General'
    desc_sintetica_corta = f"{desc_sintetica[:50]}..." if len(desc_sintetica) > 50 else desc_sintetica

    # 1. Metadatos de la Obra
    info_data = [
        [
            Paragraph("<b>Obra:</b>", table_text),
            Paragraph(f"{proy_info.get('nombre_obra') or 'N/D'}", table_text),
            Paragraph("<b>Contrato N°:</b>", table_text),
            Paragraph(f"{proy_info.get('contrato_no') or 'S/N'}", table_text)
        ],
        [
            Paragraph("<b>Ubicación:</b>", table_text),
            Paragraph(f"{proy_info.get('ubicacion') or proy_info.get('municipio') or 'N/D'}", table_text),
            Paragraph("<b>Modalidad:</b>", table_text),
            Paragraph(f"Obra {modalidad.capitalize()}", table_text)
        ],
        [
            Paragraph("<b>Contratista / Empresa:</b>", table_text),
            Paragraph(f"{proy_info.get('contratista') or 'N/D'}", table_text),
            Paragraph("<b>Unidad / Inmueble:</b>", table_text),
            Paragraph(f"{proy_info.get('unidad') or 'N/D'}", table_text)
        ],
        [
            Paragraph("<b>Residente:</b>", table_text),
            Paragraph(f"{proy_info.get('residente_obra') or 'N/D'}", table_text),
            Paragraph("<b>Alcance:</b>", table_text),
            Paragraph(f"{desc_sintetica_corta}", table_text)
        ]
    ]
    t_info = Table(info_data, colWidths=[65, 230, 75, 170])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 8))

    # 2. Bloque de KPIs según Modalidad (BUG-023: 6 KPIs para obra privada)
    d_op = datos_operativos or {}
    gasto_real = float(d_op.get("gasto_erogado_real", 0.0))
    utilidad_real = float(d_op.get("utilidad_bruta_real", 0.0))
    pct_margen = float(d_op.get("pct_margen_real", 15.0))
    total_destajos = float(d_op.get("total_destajos_pagados", 0.0))
    pct_iva = float(d_op.get("pct_iva_proy", proy_info.get("porcentaje_iva", 0.0) or 0.0))
    total_con_iva = float(d_op.get("total_con_iva_global", monto_est * (1.0 + pct_iva / 100.0)))

    if modalidad == "privada":
        kpi_data = [
            [
                Paragraph(f"<para align=center><b>Presupuesto Pactado</b><br/><font size=8.5 color='#1A2530'><b>${monto_cont:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Total con I.V.A.</b><br/><font size=8.5 color='#2563EB'><b>${total_con_iva:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Gasto Reportable</b><br/><font size=8.5 color='#0D9488'><b>${monto_est:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Gasto Erogado Real</b><br/><font size=8.5 color='#D32F2F'><b>${gasto_real:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Utilidad Bruta Real</b><br/><font size=8.5 color='#00875A'><b>${utilidad_real:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Margen Real</b><br/><font size=8.5 color='#0288D1'><b>{pct_margen:.1f}%</b></font></para>", table_text)
            ]
        ]
        t_kpi = Table(kpi_data, colWidths=[90, 90, 90, 90, 90, 90])
        t_kpi.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.white),
            ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#2563EB")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t_kpi)

    elif modalidad == "mixta":
        kpi_data = [
            [
                Paragraph(f"<para align=center><b>Presupuesto Contratado</b><br/><font size=9.5 color='#1A2530'><b>${monto_cont:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Estimado Acumulado</b><br/><font size=9.5 color='#00875A'><b>${monto_est:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Saldo por Ejercer</b><br/><font size=9.5 color='#D32F2F'><b>${saldo_ejercer:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>% Avance Oficial</b><br/><font size=9.5 color='#0288D1'><b>{pct_global:.2f}%</b></font></para>", table_text)
            ],
            [
                Paragraph(f"<para align=center><b>Gasto Erogado Real</b><br/><font size=9.5 color='#D32F2F'><b>${gasto_real:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Utilidad Bruta Real</b><br/><font size=9.5 color='#00875A'><b>${utilidad_real:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Margen Real</b><br/><font size=9.5 color='#0D9488'><b>{pct_margen:.1f}%</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Destajos Pagados</b><br/><font size=9.5 color='#F59E0B'><b>${total_destajos:,.2f}</b></font></para>", table_text)
            ]
        ]
        t_kpi = Table(kpi_data, colWidths=[135, 135, 135, 135])
        t_kpi.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.white),
            ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#F8FAFC")),
            ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#0D9488")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t_kpi)

    else:
        # Modo Obra Pública tradicional
        kpi_data = [
            [
                Paragraph(f"<para align=center><b>Monto Contratado Total</b><br/><font size=10 color='#1A2530'><b>${monto_cont:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Monto Estimado Acumulado</b><br/><font size=10 color='#00875A'><b>${monto_est:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Saldo por Ejercer</b><br/><font size=10 color='#D32F2F'><b>${saldo_ejercer:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Avance Global</b><br/><font size=10 color='#0288D1'><b>{pct_global:.2f}%</b></font></para>", table_text)
            ]
        ]
        t_kpi = Table(kpi_data, colWidths=[135, 135, 135, 135])
        t_kpi.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.white),
            ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#00875A")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_kpi)

    story.append(Spacer(1, 8))

    # 3. Gráficas Adaptativas en Matplotlib
    c_mat = float(d_op.get("costo_materiales_erogado", 0.0))
    c_herr = float(d_op.get("costo_herramienta_erogado", 0.0))
    c_ind = float(d_op.get("costo_indirectos_erogado", 0.0))

    section_h_style = ParagraphStyle(
        'SecH',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#0D9488"),
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=4
    )

    def _crear_bloque_dona_y_tabla(titulo_seccion, montos_items, callout_top, callout_bot, col_header_name):
        story.append(Paragraph(f"<b>{titulo_seccion}</b>", section_h_style))

        items_validos = [it for it in montos_items if it[1] > 0]
        tot = sum(it[1] for it in items_validos)

        if tot > 0:
            fig, ax = plt.subplots(figsize=(2.2, 2.2), dpi=250)
            fig.patch.set_alpha(0.0)
            ax.patch.set_alpha(0.0)

            montos_vals = [it[1] for it in items_validos]
            colores_vals = [it[2] for it in items_validos]

            wedges, _ = ax.pie(
                montos_vals,
                colors=colores_vals,
                wedgeprops=dict(width=0.38, edgecolor='white', linewidth=2.5),
                startangle=90
            )

            # Texto central dentro del orificio de la dona (estilo Dashboard)
            ax.text(0, 0.12, callout_top, ha='center', va='center', fontsize=6.5, weight='bold', color='#64748B')
            ax.text(0, -0.12, callout_bot, ha='center', va='center', fontsize=9.0, weight='bold', color='#1A2530')

            ax.axis('equal')
            plt.tight_layout(pad=0.2)

            chart_buf = io.BytesIO()
            plt.savefig(chart_buf, format='png', bbox_inches='tight', transparent=True, dpi=250)
            plt.close(fig)
            chart_buf.seek(0)
            donut_img = RLImage(chart_buf, width=130, height=130)

            # Tabla complementaria elegante con viñetas de color nativas de ReportLab (colWidths=[180, 105, 55], sum=340pt)
            t_desglose_rows = [
                [
                    Paragraph(f"<b>{col_header_name}</b>", table_head),
                    Paragraph("<para align=right><b>Importe ($)</b></para>", table_head),
                    Paragraph("<para align=center><b>% Total</b></para>", table_head)
                ]
            ]
            for nom, mnt, col in items_validos:
                pct = (mnt / tot * 100.0) if tot > 0 else 0.0
                bullet = f"<font color='{col}'>■</font> "
                t_desglose_rows.append([
                    Paragraph(f"{bullet}<b>{nom}</b>", table_text),
                    Paragraph(f"<para align=right>${mnt:,.2f}</para>", table_text),
                    Paragraph(f"<para align=center><b>{pct:.1f}%</b></para>", table_text)
                ])

            t_desglose_rows.append([
                Paragraph("<b>TOTAL ANALIZADO:</b>", table_text),
                Paragraph(f"<para align=right><b>${tot:,.2f}</b></para>", table_text),
                Paragraph("<para align=center><b>100.0%</b></para>", table_text)
            ])

            t_desglose = Table(t_desglose_rows, colWidths=[180, 105, 55])
            t_desglose.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A2530")),
                ('INNERGRID', (0,0), (-1,-2), 0.5, colors.HexColor("#E2E8F0")),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F8FAFC")),
                ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor("#0D9488")),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ]))

            # Disposición horizontal: Columna izquierda 200 pt (dona centrada), Columna derecha 340 pt (tabla flush a la derecha)
            t_layout = Table([[donut_img, t_desglose]], colWidths=[200, 340])
            t_layout.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (0,0), 'CENTER'),
                ('ALIGN', (1,0), (1,0), 'RIGHT'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            story.append(t_layout)
        else:
            story.append(Paragraph("<i>Sin registros para esta sección.</i>", table_text))

    if modalidad in ("privada", "mixta"):
        # 1. Dona General: Costos y Margen
        rubros_def = [
            ("Materiales", max(0.0, c_mat), "#2563EB"),
            ("Mano de Obra / Destajos", max(0.0, total_destajos), "#0D9488"),
            ("Herramienta y Equipo", max(0.0, c_herr), "#F59E0B"),
            ("Gastos Indirectos", max(0.0, c_ind), "#64748B"),
            ("Margen de Utilidad", max(0.0, utilidad_real), "#10B981")
        ]
        _crear_bloque_dona_y_tabla(
            titulo_seccion="1. General: Costos y Margen",
            montos_items=rubros_def,
            callout_top="TOTAL EROGADO",
            callout_bot=f"${gasto_real:,.2f}",
            col_header_name="Rubro Financiero"
        )

        # 2. Dona Personal: Mano de Obra y Cuadrillas
        df_mo = d_op.get("df_mo")
        rubros_mo = []
        palette_mo = ["#0D9488", "#2563EB", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4", "#10B981", "#6366F1", "#D97706", "#4F46E5"]
        total_mo = 0.0
        if isinstance(df_mo, pd.DataFrame) and not df_mo.empty:
            c_idx = 0
            for _, r in df_mo.iterrows():
                imp = float(r.get("Importe", 0.0))
                if imp <= 0:
                    continue
                total_mo += imp
                trab = str(r.get("Trabajador", "Personal"))
                mod = str(r.get("Modalidad", ""))
                label = f"{trab} ({mod})" if mod and mod != "Sin Asignar" else trab
                if trab == "Mano de Obra sin Asignar":
                    col = "#94A3B8"
                else:
                    col = palette_mo[c_idx % len(palette_mo)]
                    c_idx += 1
                rubros_mo.append((label, imp, col))

        _crear_bloque_dona_y_tabla(
            titulo_seccion="2. Personal: Mano de Obra y Cuadrillas",
            montos_items=rubros_mo,
            callout_top="TOTAL M.O.",
            callout_bot=f"${total_mo:,.2f}",
            col_header_name="Trabajador / Cuadrilla"
        )

        # 3. Dona Proveedores: Materiales e Insumos
        df_mat = d_op.get("df_mat")
        rubros_mat = []
        palette_mat = [
            "#2563EB", "#0284C7", "#0D9488", "#10B981", "#8B5CF6", 
            "#EC4899", "#6366F1", "#14B8A6", "#3B82F6", "#4F46E5"
        ]
        total_mat = 0.0
        if isinstance(df_mat, pd.DataFrame) and not df_mat.empty:
            c_idx = 0
            for _, r in df_mat.iterrows():
                imp = float(r.get("Importe", 0.0))
                if imp <= 0:
                    continue
                total_mat += imp
                prov = str(r.get("Proveedor", "Proveedor"))
                if prov == "📦 Otros Proveedores (Consolidado)":
                    col = "#64748B"
                elif prov == "Materiales sin Asignar":
                    col = "#F59E0B"
                else:
                    col = palette_mat[c_idx % len(palette_mat)]
                    c_idx += 1
                rubros_mat.append((prov, imp, col))

        _crear_bloque_dona_y_tabla(
            titulo_seccion="3. Proveedores: Materiales e Insumos",
            montos_items=rubros_mat,
            callout_top="TOTAL MAT.",
            callout_bot=f"${total_mat:,.2f}",
            col_header_name="Proveedor / Comercio"
        )

    else:
        # Obra Pública tradicional
        fig, ax = plt.subplots(figsize=(7.2, 1.0), dpi=150)
        cats = ['Balance Contractual']
        ax.barh(cats, [monto_est], color='#00875A', height=0.45, label=f'Ejercido (${monto_est:,.2f} - {pct_global:.1f}%)')
        ax.barh(cats, [saldo_ejercer], left=[monto_est], color='#CBD5E1', height=0.45, label=f'Saldo (${saldo_ejercer:,.2f})')
        limite = max(monto_cont * 1.05, 1.0)
        ax.set_xlim(0, limite)
        ax.set_xlabel('Monto en MXN', fontsize=7)
        ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.01), ncol=2, frameon=False, fontsize=7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='both', which='both', labelsize=7, left=False)
        plt.tight_layout()

        chart_buf = io.BytesIO()
        plt.savefig(chart_buf, format='png', bbox_inches='tight')
        plt.close(fig)
        chart_buf.seek(0)
        story.append(RLImage(chart_buf, width=540, height=75))

    story.append(Spacer(1, 8))

    # 4. Tabla de Conceptos (BUG-023: Columna Estimación incluida, ancho 540 pt exactos)
    story.append(Paragraph("<b>4. Desglose Detallado por Concepto de Obra</b>", section_h_style))
    table_rows = [
        [
            Paragraph("<para align=center>#</para>", table_head),
            Paragraph("<para align=center>Estimación</para>", table_head),
            Paragraph("<para align=center>Clave</para>", table_head),
            Paragraph("<para align=center>Und</para>", table_head),
            Paragraph("<para align=center>Cant. Cont.</para>", table_head),
            Paragraph("<para align=center>Cant. Est.</para>", table_head),
            Paragraph("<para align=center>P.U. ($)</para>", table_head),
            Paragraph("<para align=center>Importe Est. ($)</para>", table_head),
            Paragraph("<para align=center>Saldo Fin. ($)</para>", table_head),
            Paragraph("<para align=center>% Avance</para>", table_head),
        ]
    ]

    for idx, row in df_conceptos.iterrows():
        p_avance = float(row.get("% Avance", 0.0))
        color_pct = "#D32F2F" if p_avance > 100.0 else "#00875A"
        est_val = str(row.get("Estimación", "")).replace("Estimación ", "Est. ")
        table_rows.append([
            Paragraph(f"<para align=center>{idx+1}</para>", table_text),
            Paragraph(f"<para align=center>{est_val}</para>", table_text),
            Paragraph(f"{row.get('Clave', '')}", table_text),
            Paragraph(f"<para align=center>{row.get('Unidad', '')}</para>", table_text),
            Paragraph(f"<para align=right>{float(row.get('Cant. Contratada', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right>{float(row.get('Cant. Acumulada', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right>${float(row.get('P.U. ($)', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right>${float(row.get('Importe Acumulado ($)', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right>${float(row.get('Saldo Financiero ($)', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=center><font color='{color_pct}'><b>{p_avance:.1f}%</b></font></para>", table_text),
        ])

    t_table = Table(table_rows, colWidths=[20, 62, 60, 30, 56, 56, 58, 72, 72, 54], repeatRows=1)
    t_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A2530")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(t_table)
    story.append(Spacer(1, 15))

    residente_nom = proy_info.get('residente_obra') or 'Supervisión de Obra'
    contratista_nom = proy_info.get('contratista') or 'Contratista'
    sig_data = [
        [
            Paragraph(f"<para align=center>____________________________________<br/><b>{residente_nom}</b><br/>Residente de Obra / Supervisión</para>", table_text),
            Paragraph(f"<para align=center>____________________________________<br/><b>{contratista_nom}</b><br/>Empresa Contratista</para>", table_text)
        ]
    ]
    t_sig = Table(sig_data, colWidths=[270, 270])
    t_sig.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 15),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(KeepTogether(t_sig))

    doc.build(story)
    return pdf_buffer.getvalue()