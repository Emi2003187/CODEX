from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
    Image,
    PageBreak,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import eanbc, code128
from reportlab.graphics.shapes import Drawing
from django.utils import timezone
from datetime import datetime, time
from django.conf import settings
from io import BytesIO
import os
import qrcode

# Intenta registrar una fuente que soporte acentos (DejaVu Sans).
# Coloca el TTF en static/fonts si no está. Si no existe, ignora silenciosamente.
def _register_fonts():
    try:
        font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "DejaVuSans.ttf")
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
    except Exception:
        pass

def _style_sheet():
    styles = getSampleStyleSheet()
    # Si registramos DejaVuSans, úsala.
    if "DejaVuSans" in pdfmetrics.getRegisteredFontNames():
        base = "DejaVuSans"
    else:
        base = styles["Normal"].fontName

    styles.add(ParagraphStyle(name="H1", fontName=base, fontSize=16, leading=20, spaceAfter=8, textColor=colors.HexColor("#0d6efd")))
    styles.add(ParagraphStyle(name="H2", fontName=base, fontSize=13, leading=16, spaceAfter=6, textColor=colors.HexColor("#0d6efd")))
    styles.add(ParagraphStyle(name="LBL", fontName=base, fontSize=9, leading=11, textColor=colors.HexColor("#6c757d")))
    styles.add(ParagraphStyle(name="TXT", fontName=base, fontSize=10, leading=13))
    styles.add(ParagraphStyle(name="SM", fontName=base, fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="XS", fontName=base, fontSize=8, leading=10, textColor=colors.HexColor("#6c757d")))
    return styles

def _logo_flowable(usuario=None):
    """Devuelve un flowable con el logo del consultorio.

    Actualmente se utiliza un logo estático ubicado en ``static/img/logo_receta.jpg``.
    Si no se encuentra el archivo, simplemente no se muestra el logo.
    """
    path = os.path.join(settings.BASE_DIR, "static", "img", "logo_receta.jpg")
    if os.path.exists(path):
        try:
            return Image(path, width=28*mm, height=28*mm, hAlign="LEFT")
        except Exception:
            pass
    return None

def _qr_flowable(text):
    try:
        qr = qrcode.QRCode(box_size=2, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Image(buf, width=24*mm, height=24*mm, hAlign="RIGHT")
    except Exception:
        return None

def _barcode_flowable(code: str):
    if not code:
        return None
    try:
        if code.isdigit() and len(code) == 13:
            bc = eanbc.Ean13BarcodeWidget(code, barHeight=12*mm, barWidth=1.2)
        else:
            bc = code128.Code128(str(code), barHeight=12*mm, barWidth=1.2)
        d = Drawing(45 * mm, 15 * mm)
        d.add(bc)
        return d
    except Exception:
        return None

def _fmt(v, default="—"):
    return default if v in (None, "", []) else str(v)

def build_receta_pdf(buffer, receta):
    """
    Escribe un PDF de receta en `buffer` (BytesIO) usando ReportLab.
    `receta` es instancia de consultorio_API.models.Receta.
    """
    _register_fonts()
    styles = _style_sheet()

    consulta = receta.consulta
    paciente = consulta.paciente
    medico = consulta.medico or receta.medico
    consultorio = getattr(medico, "consultorio", None)

    # Válido hasta: receta.valido_hasta o receta.fecha_emision + 2 días
    valido_hasta = receta.valido_hasta
    if not valido_hasta and receta.fecha_emision:
        valido_hasta = receta.fecha_emision + timezone.timedelta(days=2)

    def create_page_content():
        content = []
        
        # Encabezado con logo y datos del médico
        logo = _logo_flowable()
        info = []
        if medico:
            info.append(Paragraph(f"Dr. {_fmt(medico.get_full_name())}", styles["H1"]))
            if consultorio and getattr(consultorio, "nombre", None):
                info.append(Paragraph(_fmt(consultorio.nombre), styles["TXT"]))
            if getattr(medico, "cedula_profesional", None):
                info.append(Paragraph(f"Cédula: {_fmt(medico.cedula_profesional)}", styles["XS"]))
            if getattr(medico, "institucion_cedula", None):
                info.append(Paragraph(f"Institución: {_fmt(medico.institucion_cedula)}", styles["XS"]))
            telefono = getattr(medico, "telefono", None)
            if telefono and any(ch.isdigit() for ch in str(telefono)):
                info.append(Paragraph(f"Tel.: {_fmt(telefono)}", styles["XS"]))

        header_tbl = Table(
            [[logo, info]],
            colWidths=[32*mm, None],
            hAlign="LEFT",
            style=TableStyle([
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 0),
                ("RIGHTPADDING", (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                ("TOPPADDING", (0,0), (-1,-1), 0),
            ])
        )
        content += [
            header_tbl,
            Spacer(1, 2*mm),
            HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#0d6efd")),
            Spacer(1, 2*mm),
            Paragraph("Receta Médica", styles["H1"]),
            Spacer(1, 3*mm),
        ]

        # Información del Paciente
        content += [Paragraph("Información del Paciente", styles["H2"])]
        p_info = [
            ["Nombre", _fmt(paciente.nombre_completo)],
            ["Edad", f"{_fmt(paciente.edad)} años"],
        ]
        if consultorio and getattr(consultorio, "nombre", None):
            p_info.append(["Consultorio", _fmt(consultorio.nombre)])
        p_tbl = Table(p_info, colWidths=[35*mm, None], style=TableStyle([
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#6c757d")),
            ("ALIGN", (0,0), (0,-1), "RIGHT"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        content += [p_tbl, Spacer(1, 2*mm)]
        
        return content

    # Documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=10*mm,
        rightMargin=10*mm,
        topMargin=10*mm,
        bottomMargin=10*mm,
    )
    story = []

    # Agregar contenido base de la primera página
    story.extend(create_page_content())

    # Información de la Consulta (solo en primera página)
    story += [Paragraph("Información de la Consulta", styles["H2"])]
    def box(lbl, txt):
        return [
            [Paragraph(f"<font color='#6c757d'>{lbl}</font>", styles["SM"])],
            [Paragraph(_fmt(txt), styles["TXT"])]
        ]
    c_tbl = Table(
        [
            [Table(box("Motivo de consulta", consulta.motivo_consulta), style=TableStyle([("BOX",(0,0),(-1,-1),0.3,colors.HexColor("#dee2e6")), ("INNERPADDING",(0,0),(-1,-1),4)])),
             Table(box("Diagnóstico", consulta.diagnostico), style=TableStyle([("BOX",(0,0),(-1,-1),0.3,colors.HexColor("#dee2e6")), ("INNERPADDING",(0,0),(-1,-1),4)]))],
            [Table(box("Tratamiento", consulta.tratamiento), style=TableStyle([("BOX",(0,0),(-1,-1),0.3,colors.HexColor("#dee2e6")), ("INNERPADDING",(0,0),(-1,-1),4)])),
             Table(box("Observaciones", consulta.observaciones), style=TableStyle([("BOX",(0,0),(-1,-1),0.3,colors.HexColor("#dee2e6")), ("INNERPADDING",(0,0),(-1,-1),4)]))],
        ],
        colWidths=[None, None]
    )
    story += [c_tbl, Spacer(1, 2*mm)]

    # Signos vitales (si existen, solo en primera página)
    signos = getattr(consulta, "signos_vitales", None)
    if signos:
        story += [Paragraph("Signos Vitales", styles["H2"])]
        # IMC: usa el campo si viene, o calcúlalo
        imc_val = signos.imc
        try:
            if not imc_val and signos.peso and signos.talla:
                imc_val = float(signos.peso) / (float(signos.talla) ** 2)
        except Exception:
            pass
        sv = [
            ["Tensión Arterial", _fmt(signos.tension_arterial), "Frec. Cardíaca (lpm)", _fmt(signos.frecuencia_cardiaca)],
            ["Temperatura (°C)", _fmt(signos.temperatura), "Frec. Respiratoria (rpm)", _fmt(signos.frecuencia_respiratoria)],
            ["Peso (kg)", _fmt(signos.peso), "Talla (m)", _fmt(signos.talla)],
            ["Circ. Abdominal (cm)", _fmt(signos.circunferencia_abdominal), "IMC", _fmt(round(imc_val, 2) if imc_val else None)],
        ]
        sv_tbl = Table(sv, colWidths=[45*mm, 40*mm, 50*mm, None], style=TableStyle([
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e9ecef")),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("TEXTCOLOR", (0,0), (-1,-1), colors.black),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))
        story += [sv_tbl, Spacer(1, 2*mm)]
        # Alergias y Síntomas
        story += [
            Paragraph("<font color='#6c757d'>Alergias</font>", styles["SM"]),
            Paragraph(_fmt(signos.alergias), styles["TXT"]),
            Spacer(1, 1*mm),
            Paragraph("<font color='#6c757d'>Síntomas</font>", styles["SM"]),
            Paragraph(_fmt(signos.sintomas), styles["TXT"]),
            Spacer(1, 2*mm),
        ]

    # Receta (solo en primera página)
    story += [Paragraph("Receta Médica", styles["H2"])]
    story += [
        Paragraph("<font color='#6c757d'>Indicaciones Generales</font>", styles["SM"]),
        Paragraph(_fmt(receta.indicaciones_generales), styles["TXT"]),
        Spacer(1, 2*mm),
    ]

    r_meta = [
        ["Válido hasta", _fmt(valido_hasta.strftime("%d/%m/%Y") if valido_hasta else None), "Notas", _fmt(receta.notas)],
    ]
    r_tbl = Table(r_meta, colWidths=[30*mm, 35*mm, 20*mm, None], style=TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story += [r_tbl, Spacer(1, 2*mm)]

    meds = list(receta.medicamentos.all()) if hasattr(receta, "medicamentos") else []
    if meds:
        story += [Paragraph("Medicamentos Recetados", styles["H2"])]
        
        # Calcular cuántos medicamentos caben por página (aproximadamente 6-8 por página)
        meds_per_page = 6
        total_pages = (len(meds) + meds_per_page - 1) // meds_per_page
        
        for page_num in range(total_pages):
            if page_num > 0:
                # Agregar salto de página y contenido base para páginas adicionales
                story.append(PageBreak())
                story.extend(create_page_content())
                story += [Paragraph("Medicamentos Recetados (continuación)", styles["H2"])]
            
            # Medicamentos para esta página
            start_idx = page_num * meds_per_page
            end_idx = min(start_idx + meds_per_page, len(meds))
            page_meds = meds[start_idx:end_idx]
            
            for m in page_meds:
                # Crear bloque individual para cada medicamento
                med_content = []
                
                # Nombre del medicamento
                med_content.append([Paragraph(f"<b>{_fmt(m.nombre)}</b>", styles["TXT"])])
                
                # Cantidad y código de barras en la misma fila
                bc = _barcode_flowable(getattr(m, "codigo_barras", ""))
                
                if bc:
                    # Crear una sola fila con nombre, cantidad y código de barras
                    med_row = [
                        Paragraph(f"<b>{_fmt(m.nombre)}</b>", styles["TXT"]),
                        Paragraph(f"Cantidad: {_fmt(m.cantidad)}", styles["TXT"]),
                        bc
                    ]
                    
                    med_table = Table(
                        [med_row],
                        colWidths=[80*mm, 40*mm, 50*mm],
                        style=TableStyle([
                            ("BOX", (0,0), (-1,-1), 1, colors.HexColor("#dee2e6")),
                            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f8f9fa")),
                            ("LEFTPADDING", (0,0), (-1,-1), 8),
                            ("RIGHTPADDING", (0,0), (-1,-1), 8),
                            ("TOPPADDING", (0,0), (-1,-1), 6),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                            ("ALIGN", (2,0), (2,0), "CENTER"),  # Centrar código de barras
                        ])
                    )
                else:
                    # Si no hay código de barras, solo mostrar nombre y cantidad
                    med_row = [
                        Paragraph(f"<b>{_fmt(m.nombre)}</b>", styles["TXT"]),
                        Paragraph(f"Cantidad: {_fmt(m.cantidad)}", styles["TXT"])
                    ]
                    
                    med_table = Table(
                        [med_row],
                        colWidths=[80*mm, 90*mm],
                        style=TableStyle([
                            ("BOX", (0,0), (-1,-1), 1, colors.HexColor("#dee2e6")),
                            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f8f9fa")),
                            ("LEFTPADDING", (0,0), (-1,-1), 8),
                            ("RIGHTPADDING", (0,0), (-1,-1), 8),
                            ("TOPPADDING", (0,0), (-1,-1), 6),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                        ])
                    )
                
                story += [med_table, Spacer(1, 3*mm)]

    # QR + folio/fecha en una fila (solo en la última página o primera si no hay medicamentos)
    folio = f"Folio: {receta.pk}"
    emision = receta.fecha_emision or timezone.now()

    # ``fecha_emision`` es un DateField, por lo que puede devolver un ``date``.
    # Convertimos a ``datetime`` para evitar errores de atributos y poder
    # formatear con hora.
    if not isinstance(emision, datetime):
        emision = datetime.combine(emision, timezone.now().time())

    if timezone.is_aware(emision):
        emision = timezone.localtime(emision)
    fecha_emision = f"Emitida: {emision.strftime('%d/%m/%Y %H:%M')}"
    qr = _qr_flowable(f"{folio} | {fecha_emision}")
    meta_tbl = Table(
        [[qr, Paragraph(f"{folio}<br/>{fecha_emision}", styles['XS'])]],
        colWidths=[28*mm, None],
        style=TableStyle([
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN", (0,0), (0,0), "LEFT"),
            ("LEFTPADDING", (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ])
    )
    story += [Spacer(1, 2*mm), meta_tbl]

    # Callback pie de página
    def _footer(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6c757d"))
        canvas.drawRightString(w - 10*mm, 8*mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    # Render
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer
