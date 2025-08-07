from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.utils import timezone
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
    if "DejaVuSans" in [f.name for f in pdfmetrics._fonts.values()]:
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

def _logo_flowable(usuario):
    # Busca un logo razonable: usuario.consultorio.logo (si existiera), o static/logo.png, o nada
    candidatos = [
        getattr(getattr(usuario, "consultorio", None), "logo", None).path
        if getattr(getattr(usuario, "consultorio", None), "logo", None) else None,
        os.path.join(settings.BASE_DIR, "static", "img", "logo.png"),
        os.path.join(settings.BASE_DIR, "static", "logo.png"),
    ]
    for path in candidatos:
        if path and os.path.exists(path):
            try:
                img = Image(path, width=28*mm, height=28*mm, hAlign="LEFT")
                return img
            except Exception:
                continue
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

    # Documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm
    )
    story = []

    # Encabezado (logo + info consultorio/médico)
    logo = _logo_flowable(medico) if medico else None
    titulo = []
    titulo.append(Paragraph("<b>Receta Médica</b>", styles["H1"]))
    if consultorio and getattr(consultorio, "nombre", None):
        titulo.append(Paragraph(_fmt(consultorio.nombre), styles["TXT"]))
    # Datos del médico
    if medico:
        nombre_medico = f"{_fmt(medico.get_full_name())} ({_fmt(medico.rol)})"
        titulo.append(Paragraph(nombre_medico, styles["SM"]))
        if getattr(medico, "cedula_profesional", None):
            titulo.append(Paragraph(f"Cédula: {_fmt(medico.cedula_profesional)}", styles["XS"]))
        if getattr(medico, "telefono", None):
            titulo.append(Paragraph(f"Tel.: {_fmt(medico.telefono)}", styles["XS"]))

    header_tbl = Table(
        [[logo, titulo]],
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
    story += [header_tbl, Spacer(1, 4*mm)]

    # Información del Paciente
    story += [Paragraph("Información del Paciente", styles["H2"])]
    p_info = [
        ["Nombre", _fmt(paciente.nombre_completo)],
        ["Edad", f"{_fmt(paciente.edad)} años"],
        ["Teléfono", _fmt(paciente.telefono)],
        ["Email", _fmt(paciente.correo)],
    ]
    p_tbl = Table(p_info, colWidths=[35*mm, None], style=TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#6c757d")),
        ("ALIGN", (0,0), (0,-1), "RIGHT"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story += [p_tbl, Spacer(1, 3*mm)]

    # Información de la Consulta
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
             Table(box("Observaciones", consulta.observaciones), style=TableStyle([("BOX",(0,0),(-1,-1),0.3,colors.HexColor("#dee2e6")), ("INNERPADDING",(0,0),(-1,-1),4)]))]
        ],
        colWidths=[None, None]
    )
    story += [c_tbl, Spacer(1, 4*mm)]

    # Signos vitales (si existen)
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
            Spacer(1, 3*mm),
        ]

    # Receta
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
    story += [r_tbl, Spacer(1, 3*mm)]

    # Medicamentos recetados
    meds = list(receta.medicamentos.all()) if hasattr(receta, "medicamentos") else []
    if meds:
        story += [Paragraph("Medicamentos Recetados", styles["H2"])]
        data = [["Nombre", "Principio activo", "Dosis", "Frecuencia", "Vía", "Duración", "Cant.", "Indicaciones"]]
        for m in meds:
            data.append([
                _fmt(m.nombre), _fmt(m.principio_activo), _fmt(m.dosis),
                _fmt(m.frecuencia), _fmt(m.via_administracion),
                _fmt(m.duracion), _fmt(m.cantidad), _fmt(m.indicaciones_especificas)
            ])
        meds_tbl = Table(data, repeatRows=1, style=TableStyle([
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dee2e6")),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f1f3f5")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story += [meds_tbl, Spacer(1, 2*mm)]

    # QR + folio/fecha en una fila
    folio = f"Folio: {getattr(getattr(consulta, 'cita', None), 'numero_cita', None) or f'R-{receta.pk}'}"
    fecha_emision = f"Emitida: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M') if timezone.is_aware(timezone.now()) else timezone.now().strftime('%d/%m/%Y %H:%M')}"
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
        page = f"Página {doc.page} de "  # total se completa con onLaterPages
        canvas.drawRightString(w - 18*mm, 12*mm, page)
        canvas.restoreState()

    # Render
    doc.build(story)
    return buffer
