from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
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


def _register_fonts():
    try:
        font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "DejaVuSans.ttf")
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
    except Exception:
        pass


def _qr_flowable(text):
    try:
        qr = qrcode.QRCode(box_size=2, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Image(buf, width=24 * mm, height=24 * mm, hAlign="RIGHT")
    except Exception:
        return None


def _barcode_flowable(code: str):
    if not code:
        return None
    try:
        if code.isdigit() and len(code) == 13:
            bc = eanbc.Ean13BarcodeWidget(code, barHeight=15 * mm, barWidth=0.4)
        else:
            bc = code128.Code128(str(code), barHeight=15 * mm, barWidth=0.4)
        d = Drawing(40 * mm, 15 * mm)
        d.add(bc)
        return d
    except Exception:
        return None


def _fmt(v, default="—"):
    return default if v in (None, "", []) else str(v)


def build_receta_pdf(buffer, receta):
    """Genera el PDF de una receta médica con un diseño profesional."""
    _register_fonts()

    styles = {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=12, alignment=1, spaceAfter=6),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=12, spaceAfter=4),
        "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=10),
        "text": ParagraphStyle("text", fontName="Helvetica", fontSize=10),
    }

    consulta = receta.consulta
    paciente = consulta.paciente
    medico = consulta.medico or receta.medico
    consultorio = getattr(medico, "consultorio", None)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    story = []

    if medico:
        story.append(Paragraph(f"Dr. {_fmt(medico.get_full_name())}", styles["text"]))
        if consultorio and getattr(consultorio, "nombre", None):
            story.append(Paragraph(_fmt(consultorio.nombre), styles["text"]))
        if getattr(medico, "cedula_profesional", None):
            story.append(Paragraph(f"Cédula: {_fmt(medico.cedula_profesional)}", styles["text"]))
        if getattr(medico, "institucion_cedula", None):
            story.append(Paragraph(f"Institución: {_fmt(medico.institucion_cedula)}", styles["text"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("RECETA MÉDICA", styles["title"]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Información del Paciente", styles["section"]))
    p_rows = [
        [Paragraph("Nombre", styles["label"]), Paragraph(_fmt(paciente.nombre_completo), styles["text"])],
        [Paragraph("Edad", styles["label"]), Paragraph(f"{_fmt(paciente.edad)} años", styles["text"])],
    ]
    if consultorio and getattr(consultorio, "nombre", None):
        p_rows.append([Paragraph("Consultorio", styles["label"]), Paragraph(_fmt(consultorio.nombre), styles["text"])])
    p_tbl = Table(p_rows, colWidths=[doc.width * 0.25, doc.width * 0.75], style=TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d9d9")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d9d9")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f2f2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [p_tbl, Spacer(1, 6 * mm)]

    story.append(Paragraph("Información de la Consulta", styles["section"]))
    c_rows = [
        ("Motivo", _fmt(consulta.motivo_consulta)),
        ("Diagnóstico", _fmt(consulta.diagnostico)),
        ("Tratamiento", _fmt(consulta.tratamiento)),
        ("Observaciones", _fmt(consulta.observaciones)),
    ]
    signos = getattr(consulta, "signos_vitales", None)
    if signos:
        sv_parts = []
        if signos.tension_arterial:
            sv_parts.append(f"TA: {signos.tension_arterial}")
        if signos.frecuencia_cardiaca:
            sv_parts.append(f"FC: {signos.frecuencia_cardiaca}")
        if signos.temperatura:
            sv_parts.append(f"T: {signos.temperatura}°C")
        if signos.frecuencia_respiratoria:
            sv_parts.append(f"FR: {signos.frecuencia_respiratoria}")
        if signos.peso:
            sv_parts.append(f"Peso: {signos.peso}kg")
        if signos.talla:
            sv_parts.append(f"Talla: {signos.talla}m")
        c_rows.append(("Signos vitales", ", ".join(sv_parts)))
        c_rows.append(("Alergias", _fmt(signos.alergias)))
        c_rows.append(("Síntomas", _fmt(signos.sintomas)))
    c_tbl = Table(
        [[Paragraph(f"<b>{lbl}</b>", styles["label"]), Paragraph(txt, styles["text"])] for lbl, txt in c_rows],
        colWidths=[doc.width * 0.25, doc.width * 0.75],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9d9d9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]),
    )
    story += [c_tbl, Spacer(1, 6 * mm)]

    meds = list(receta.medicamentos.all()) if hasattr(receta, "medicamentos") else []
    if meds:
        story.append(Paragraph("Medicamentos Recetados", styles["section"]))
        header = [
            Paragraph("Nombre", styles["label"]),
            Paragraph("Principio Activo", styles["label"]),
            Paragraph("Dosis", styles["label"]),
            Paragraph("Frecuencia", styles["label"]),
            Paragraph("Vía", styles["label"]),
            Paragraph("Duración", styles["label"]),
            Paragraph("Cantidad", styles["label"]),
            Paragraph("Indicaciones", styles["label"]),
            Paragraph("Código", styles["label"]),
        ]
        data = [header]
        for m in meds:
            data.append([
                Paragraph(_fmt(m.nombre), styles["text"]),
                Paragraph(_fmt(m.principio_activo), styles["text"]),
                Paragraph(_fmt(m.dosis), styles["text"]),
                Paragraph(_fmt(m.frecuencia), styles["text"]),
                Paragraph(_fmt(m.via_administracion), styles["text"]),
                Paragraph(_fmt(m.duracion), styles["text"]),
                Paragraph(_fmt(m.cantidad), styles["text"]),
                Paragraph(_fmt(m.indicaciones_especificas), styles["text"]),
                Paragraph(_fmt(m.codigo_barras), styles["text"]),
            ])
        col_widths = [
            doc.width * 0.15,
            doc.width * 0.15,
            doc.width * 0.1,
            doc.width * 0.1,
            doc.width * 0.07,
            doc.width * 0.1,
            doc.width * 0.07,
            doc.width * 0.16,
            doc.width * 0.1,
        ]
        meds_tbl = Table(data, colWidths=col_widths, repeatRows=1, style=TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9d9d9")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
            ("ALIGN", (6, 1), (6, -1), "CENTER"),
            ("ALIGN", (8, 1), (8, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story += [meds_tbl, Spacer(1, 6 * mm)]

        barcode = _barcode_flowable(str(receta.pk))
        if barcode:
            bc_tbl = Table([["", barcode]], colWidths=[doc.width - 40 * mm, 40 * mm], style=TableStyle([
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story += [bc_tbl, Spacer(1, 6 * mm)]

    folio = f"Folio: {receta.pk}"
    emision = receta.fecha_emision or timezone.now()
    if not isinstance(emision, datetime):
        emision = datetime.combine(emision, time())
    if timezone.is_aware(emision):
        emision = timezone.localtime(emision)
    fecha_emision = f"Emitida: {emision.strftime('%d/%m/%Y %H:%M')}"
    qr = _qr_flowable(f"{folio} | {fecha_emision}")
    meta_tbl = Table([[qr, Paragraph(f"{folio}<br/>{fecha_emision}", styles["text"])]],
                     colWidths=[24 * mm, None],
                     style=TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                     ]))
    story.append(meta_tbl)

    doc.build(story)
    return buffer
