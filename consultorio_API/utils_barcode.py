import base64
from io import BytesIO
from typing import Optional

from reportlab.graphics.barcode import eanbc, code128
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPM


def barcode_base64(code: str) -> str:
    """Return a base64 PNG representation of ``code``.

    The image is generated in-memory using ReportLab's barcode widgets and no
    files are written to disk. If ``code`` is empty or an error occurs, an
    empty string is returned.
    """
    if not code:
        return ""
    try:
        # Choose barcode type depending on the content
        if code.isdigit() and len(code) == 13:
            widget = eanbc.Ean13BarcodeWidget(code)
        else:
            widget = code128.Code128(code)
        # Determine drawing size
        bounds = widget.getBounds()
        width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        drawing = Drawing(width, height)
        drawing.add(widget)
        png_bytes = renderPM.drawToString(drawing, fmt="PNG")
        return base64.b64encode(png_bytes).decode("ascii")
    except Exception:
        return ""
