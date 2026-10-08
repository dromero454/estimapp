import streamlit as st
import io
import datetime
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


@st.cache_data(show_spinner=False)
def generar_pdf_recibo_raya(proy_info: dict, est_info: dict, filas_raya: list, total_raya: float) -> bytes:
    """
    Genera un recibo oficial de liquidación de raya y destajos en PDF (ReportLab),
    con diseño corporativo, desglose de jornales, tarifas y firmas de conformidad.
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
        'RayaTitle',
        parent=styles['Heading1'],
        fontSize=14,
        leading=17,
        textColor=colors.HexColor("#1A2530"),
        spaceAfter=2,
        fontName="Helvetica-Bold"
    )
    subtitle_style = ParagraphStyle(
        'RayaSubtitle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=10
    )
    table_text = ParagraphStyle(
        'RayaTableText',
        parent=styles['Normal'],
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#222222")
    )
    table_head = ParagraphStyle(
        'RayaTableHead',
        parent=styles['Normal'],
        fontSize=7.5,
        leading=10,
        textColor=colors.white,
        fontName="Helvetica-Bold"
    )

    story.append(Paragraph("ESTIMAPP | RECIBO OFICIAL DE LIQUIDACIÓN DE RAYA Y DESTAJOS", title_style))
    fecha_emision = datetime.date.today().strftime('%d/%m/%Y')
    p_ini = est_info.get('periodo_inicio', '—')
    p_fin = est_info.get('periodo_fin', '—')
    story.append(Paragraph(f"Fecha de Emisión: {fecha_emision} | Periodo de Corte: Del {p_ini} al {p_fin} | Sistema de Control de Destajos", subtitle_style))

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

    # KPIs de Raya
    total_jornales = sum(float(r.get("Jornales", 0.0)) for r in filas_raya)
    kpi_data = [
        [
            Paragraph(f"<para align=center><b>Total Trabajadores</b><br/><font size=10 color='#1A2530'><b>{len(filas_raya)}</b></font></para>", table_text),
            Paragraph(f"<para align=center><b>Jornales Acumulados</b><br/><font size=10 color='#0288D1'><b>{total_jornales:.2f}</b></font></para>", table_text),
            Paragraph(f"<para align=center><b>Monto Total Liquidado</b><br/><font size=10 color='#00875A'><b>${total_raya:,.2f} MXN</b></font></para>", table_text)
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

    # Tabla Desglosada de Trabajadores
    worker_rows = [
        [
            Paragraph("<para align=center>#</para>", table_head),
            Paragraph("Trabajador", table_head),
            Paragraph("Especialidad", table_head),
            Paragraph("<para align=center>Conceptos</para>", table_head),
            Paragraph("<para align=right>Jornales</para>", table_head),
            Paragraph("<para align=right>Tarifa Base ($)</para>", table_head),
            Paragraph("<para align=right>Total Raya ($)</para>", table_head)
        ]
    ]

    for idx, r in enumerate(filas_raya, start=1):
        worker_rows.append([
            Paragraph(f"<para align=center>{idx}</para>", table_text),
            Paragraph(f"{r.get('Trabajador', '')}", table_text),
            Paragraph(f"{r.get('Especialidad', '')}", table_text),
            Paragraph(f"<para align=center>{r.get('Conceptos Ejecutados', 1)}</para>", table_text),
            Paragraph(f"<para align=right>{float(r.get('Jornales', 0)):.2f}</para>", table_text),
            Paragraph(f"<para align=right>${float(r.get('Tarifa Base ($)', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right><b>${float(r.get('Total a Pagar ($)', 0)):,.2f}</b></para>", table_text)
        ])

    # Fila de Totales
    worker_rows.append([
        Paragraph("", table_text),
        Paragraph("<b>TOTAL LIQUIDACIÓN DEL PERIODO:</b>", table_text),
        Paragraph("", table_text),
        Paragraph("", table_text),
        Paragraph(f"<para align=right><b>{total_jornales:.2f}</b></para>", table_text),
        Paragraph("", table_text),
        Paragraph(f"<para align=right><font color='#00875A'><b>${total_raya:,.2f}</b></font></para>", table_text)
    ])

    t_workers = Table(worker_rows, colWidths=[25, 145, 95, 60, 65, 75, 75], repeatRows=1)
    t_workers.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A2530")),
        ('INNERGRID', (0,0), (-1,-2), 0.5, colors.HexColor("#E2E8F0")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.HexColor("#0D9488")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(t_workers)
    story.append(Spacer(1, 10))

    # Recibos de conformidad individuales
    story.append(Paragraph("<b>CONSTANCIA DE CONFORMIDAD Y LIQUIDACIÓN EN EFECTIVO</b>", ParagraphStyle('SubH', parent=styles['Normal'], fontSize=8, leading=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#1A2530"))))
    story.append(Spacer(1, 3))

    receipt_rows = []
    for r in filas_raya:
        receipt_rows.append([
            Paragraph(f"<b>Trabajador:</b> {r.get('Trabajador')} ({r.get('Especialidad')})<br/><b>Importe Recibido:</b> ${float(r.get('Total a Pagar ($)', 0)):,.2f} MXN", table_text),
            Paragraph("<b>Firma de Recibido / Huella:</b><br/><br/>________________________________________", table_text)
        ])
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


@st.cache_data(show_spinner=False)
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

    # 2. Bloque de KPIs según Modalidad
    d_op = datos_operativos or {}
    gasto_real = float(d_op.get("gasto_erogado_real", 0.0))
    utilidad_real = float(d_op.get("utilidad_bruta_real", 0.0))
    pct_margen = float(d_op.get("pct_margen_real", 15.0))
    total_destajos = float(d_op.get("total_destajos_pagados", 0.0))

    if modalidad == "privada":
        kpi_data = [
            [
                Paragraph(f"<para align=center><b>Presupuesto Cliente</b><br/><font size=10 color='#1A2530'><b>${monto_cont:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Gasto Erogado Real</b><br/><font size=10 color='#D32F2F'><b>${gasto_real:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Utilidad Bruta Real</b><br/><font size=10 color='#00875A'><b>${utilidad_real:,.2f}</b></font></para>", table_text),
                Paragraph(f"<para align=center><b>Margen Real</b><br/><font size=10 color='#0288D1'><b>{pct_margen:.1f}%</b></font></para>", table_text)
            ]
        ]
        t_kpi = Table(kpi_data, colWidths=[135, 135, 135, 135])
        t_kpi.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.white),
            ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor("#2563EB")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
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

    if modalidad == "privada":
        fig, ax = plt.subplots(figsize=(7.2, 1.1), dpi=150)
        rubros = ['Materiales', 'Mano Obra', 'Herramienta', 'Indirectos', 'Utilidad']
        montos = [max(0.0, c_mat), max(0.0, total_destajos), max(0.0, c_herr), max(0.0, c_ind), max(0.0, utilidad_real)]
        colores = ['#2563EB', '#0D9488', '#F59E0B', '#64748B', '#10B981']

        y_pos = range(len(rubros))
        ax.barh(rubros[::-1], montos[::-1], color=colores[::-1], height=0.55)
        ax.set_xlabel('Monto en MXN', fontsize=7)
        ax.set_title('Distribución de Costos y Utilidad Operativa', fontsize=8, pad=3)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(axis='both', which='both', labelsize=7)
        plt.tight_layout()

        chart_buf = io.BytesIO()
        plt.savefig(chart_buf, format='png', bbox_inches='tight')
        plt.close(fig)
        chart_buf.seek(0)
        story.append(RLImage(chart_buf, width=540, height=80))

    elif modalidad == "mixta":
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 1.0), dpi=150)
        # Bar 1: Contractual
        cats = ['Balance']
        ax1.barh(cats, [monto_est], color='#00875A', height=0.45, label=f'Ejercido ({pct_global:.1f}%)')
        ax1.barh(cats, [saldo_ejercer], left=[monto_est], color='#CBD5E1', height=0.45, label='Saldo')
        limite = max(monto_cont * 1.05, 1.0)
        ax1.set_xlim(0, limite)
        ax1.set_title('Avance Contractual Oficial', fontsize=7.5, pad=3)
        ax1.legend(loc='lower center', bbox_to_anchor=(0.5, 1.02), ncol=2, frameon=False, fontsize=6.5)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.tick_params(axis='both', labelsize=6.5)

        # Bar 2: Desglose de Costos
        rubros = ['Mat', 'M.O.', 'Herr', 'Ind', 'Util']
        montos = [max(0.0, c_mat), max(0.0, total_destajos), max(0.0, c_herr), max(0.0, c_ind), max(0.0, utilidad_real)]
        colores = ['#2563EB', '#0D9488', '#F59E0B', '#64748B', '#10B981']
        ax2.bar(rubros, montos, color=colores, width=0.55)
        ax2.set_title('Distribución de Costos Erogados', fontsize=7.5, pad=3)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.tick_params(axis='both', labelsize=6.5)
        plt.tight_layout()

        chart_buf = io.BytesIO()
        plt.savefig(chart_buf, format='png', bbox_inches='tight')
        plt.close(fig)
        chart_buf.seek(0)
        story.append(RLImage(chart_buf, width=540, height=75))

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

    # 4. Tabla de Conceptos
    table_rows = [
        [
            Paragraph("<para align=center>#</para>", table_head),
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
        table_rows.append([
            Paragraph(f"<para align=center>{idx+1}</para>", table_text),
            Paragraph(f"{row.get('Clave', '')}", table_text),
            Paragraph(f"<para align=center>{row.get('Unidad', '')}</para>", table_text),
            Paragraph(f"<para align=right>{float(row.get('Cant. Contratada', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right>{float(row.get('Cant. Acumulada', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right>${float(row.get('P.U. ($)', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right>${float(row.get('Importe Acumulado ($)', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=right>${float(row.get('Saldo Financiero ($)', 0)):,.2f}</para>", table_text),
            Paragraph(f"<para align=center><font color='{color_pct}'><b>{p_avance:.1f}%</b></font></para>", table_text),
        ])

    t_table = Table(table_rows, colWidths=[23, 72, 35, 65, 65, 60, 75, 75, 70], repeatRows=1)
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