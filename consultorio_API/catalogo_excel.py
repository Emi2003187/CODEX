"""
Lector SOLO LECTURA del Excel `settings.CATALOGO_EXCEL_PATH`.

Campos devueltos por artículo:
- nombre        (Nombre/Presentación) -> str
- clave         (código de barras/GTIN)-> str
- existencia    -> int
- departamento  -> str
- precio        -> float (sin $)
- categoria     -> str
- imagen_url    -> str (opcional; si no existe, usar placeholder en la UI)

Filtra por: nombre, clave, departamento, categoria y, si q es numérico, precio.
Tolerante a dos formatos del Excel:
  a) Hoja tabular con encabezados (descripcion/nombre/presentacion, clave/codigo, existencia, departamento, precio, categoria, imagen/url_imagen/foto).
  b) Bloques "Etiqueta: valor" (Clave:, Existencia:, Departamento:, Precio:, Categoría:) con el nombre arriba.

Si el Excel no existe, devolver 0 resultados sin romper la vista.
"""
from pathlib import Path
from unicodedata import normalize
from django.conf import settings
from openpyxl import load_workbook

EXCEL_PATH = Path(getattr(settings, "CATALOGO_EXCEL_PATH"))


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.lower()


def _to_int(v):
    try:
        return int(str(v).replace(",", "").strip())
    except Exception:
        return 0


def _to_float(v):
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except Exception:
        return 0.0


def catalogo_disponible() -> bool:
    return EXCEL_PATH.exists()


def buscar_articulos(q: str = "", limit: int = 30):
    if not EXCEL_PATH.exists():
        return []

    wb = load_workbook(EXCEL_PATH, data_only=True)
    ws = wb.active

    # Intento A: encabezados tabulares en la primera fila
    headers = {}
    first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if first:
        for i, v in enumerate(first):
            if v:
                headers[_norm(v)] = i

    items = []

    def add(nombre, clave, existencia, departamento, precio, categoria, imagen_url=None):
        if not str(clave or "").strip():
            return
        items.append({
            "nombre": str(nombre or "").strip(),
            "clave": str(clave or "").strip(),
            "existencia": _to_int(existencia),
            "departamento": str(departamento or "").strip(),
            "precio": _to_float(precio),
            "categoria": str(categoria or "").strip(),
            "imagen_url": str(imagen_url or "").strip(),
        })

    if headers:
        def col(*alts):
            for a in alts:
                for k, idx in headers.items():
                    if a in k:
                        return idx
            return None

        c_nom = col("descripcion", "nombre", "presentacion", "articulo")
        c_cla = col("clave", "codigo", "codigo_barras", "barcode", "gtin")
        c_exi = col("existencia", "stock")
        c_dep = col("departamento")
        c_pre = col("precio")
        c_cat = col("categoria")
        c_img = col("imagen", "url_imagen", "foto")

        for row in ws.iter_rows(min_row=2, values_only=True):
            nombre = row[c_nom] if c_nom is not None else ""
            clave = row[c_cla] if c_cla is not None else ""
            existencia = row[c_exi] if c_exi is not None else 0
            departamento = row[c_dep] if c_dep is not None else ""
            precio = row[c_pre] if c_pre is not None else 0
            categoria = row[c_cat] if c_cat is not None else ""
            imagen = row[c_img] if c_img is not None else ""
            add(nombre, clave, existencia, departamento, precio, categoria, imagen)
    else:
        # Intento B: bloques "Etiqueta: Valor"
        nom = cla = dep = cat = img = None
        exi = 0
        pre = 0
        for row in ws.iter_rows(values_only=True):
            line = [str(c or "").strip() for c in row]
            if any(line):
                joined = " ".join(line)
                if ":" not in joined and not nom:
                    nom = joined
                for i, val in enumerate(line):
                    lv = _norm(val)
                    nxt = line[i + 1] if i + 1 < len(line) else ""
                    if lv.startswith("clave"):
                        cla = nxt
                    elif lv.startswith("existencia"):
                        exi = nxt
                    elif lv.startswith("departamento"):
                        dep = nxt
                    elif lv.startswith("precio"):
                        pre = nxt
                    elif lv.startswith("categoria"):
                        cat = nxt
                    elif lv.startswith("imagen") or lv.startswith("foto"):
                        img = nxt
            else:
                if nom or cla:
                    add(nom, cla, exi, dep, pre, cat, img)
                nom = cla = dep = cat = img = None
                exi = pre = 0
        if nom or cla:
            add(nom, cla, exi, dep, pre, cat, img)

    if q:
        s = _norm(q)
        def match(it):
            return (
                s in _norm(it["nombre"]) or
                s in _norm(it["clave"]) or
                s in _norm(it["departamento"]) or
                s in _norm(it["categoria"]) or
                (s.replace(".", "").isdigit() and it["precio"] == _to_float(q))
            )
        items = [it for it in items if match(it)]

    return items[:limit]
