import streamlit as st
import io
import datetime
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

@st.cache_data(show_spinner=False)
def generar_pdf_resumen_ejecutivo(proy_info, monto_cont, monto_est, saldo_ejercer, pct_global, df_conceptos):
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
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=15,
        leading=18,
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

    story.append(Paragraph("ESTIMAPP | INFORME EJECUTIVO DE CONTROL PRESUPUESTAL", title_style))
    story.append(Paragraph(f"Fecha de corte y emisión: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} | Sistema Central de Estimaciones", subtitle_style))

    desc_sintetica = proy_info.get('descripcion_sintetica') or 'General'
    desc_sintetica_corta = f"{desc_sintetica[:50]}..." if len(desc_sintetica) > 50 else desc_sintetica

    info_data = [
        [
            Paragraph("<b>Obra:</b>", table_text),
            Paragraph(f"{proy_info.get('nombre_obra') or 'N/D'}", table_text),
            Paragraph("<b>Contrato N°:</b>", table_text),
            Paragraph(f"{proy_info.get('contrato_no') or 'S/N'}", table_text)
        ],
        [
            Paragraph("<b>Ubicación:</b>", table_text),
            Paragraph(f"{proy_info.get('ubicacion') or 'N/D'}", table_text),
            Paragraph("<b>Licitación:</b>", table_text),
            Paragraph(f"{proy_info.get('concurso_no') or 'S/N'}", table_text)
        ],
        [
            Paragraph("<b>Contratista:</b>", table_text),
            Paragraph(f"{proy_info.get('contratista') or 'N/D'}", table_text),
            Paragraph("<b>Unidad:</b>", table_text),
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