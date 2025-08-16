"""
Lector SOLO LECTURA del Excel `settings.CATALOGO_EXCEL_PATH`.

Devuelve páginas de artículos con:
- nombre        (Nombre/Presentación)
- clave         (código de barras / GTIN)
- existencia    (int)
- departamento  (str)
- precio        (float, sin $)
- categoria     (str)
- imagen_url    (str, opcional)

Filtra por: nombre, clave, departamento, categoria y precio (si q es numérico).
Tolera: (A) hoja tabular con encabezados, (B) bloques "Clave:/Existencia:/...".
Si el Excel no existe o no hay openpyxl, devuelve 0 resultados sin romper vistas.
"""
from pathlib import Path
from unicodedata import normalize
from typing import Dict, Any, List
from django.conf import settings

try:
    from openpyxl import load_workbook  # type: ignore
except Exception:  # pragma: no cover - openpyxl opcional
    load_workbook = None

EXCEL_PATH = Path(getattr(settings, "CATALOGO_EXCEL_PATH", Path()))


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
    return EXCEL_PATH.exists() and load_workbook is not None


def _add(items: List[Dict[str, Any]], nombre, clave, existencia, dep, precio, cat, img=None):
    if not str(clave or "").strip():
        return
    items.append(
        {
            "nombre": str(nombre or "").strip(),
            "clave": str(clave or "").strip(),
            "existencia": _to_int(existencia),
            "departamento": str(dep or "").strip(),
            "precio": _to_float(precio),
            "categoria": str(cat or "").strip(),
            "imagen_url": str(img or "").strip(),
        }
    )


def _right_value(line: List[str], start_idx: int, max_hop: int = 6):
    """Busca el primer valor no vacío a la derecha de ``start_idx``."""
    for j in range(start_idx + 1, min(len(line), start_idx + 1 + max_hop)):
        if str(line[j]).strip():
            return line[j]
    return ""


def buscar_articulos(q: str = "", page: int = 1, per_page: int = 15) -> Dict[str, Any]:
    if not catalogo_disponible():
        return {"items": [], "total": 0, "page": 1, "per_page": per_page}

    wb = load_workbook(EXCEL_PATH, data_only=True)
    ws = wb.active

    # Intento A: encabezados
    headers = {}
    first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if first:
        for i, v in enumerate(first):
            if v:
                headers[_norm(v)] = i

    items: List[Dict[str, Any]] = []

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
            dep = row[c_dep] if c_dep is not None else ""
            precio = row[c_pre] if c_pre is not None else 0
            cat = row[c_cat] if c_cat is not None else ""
            img = row[c_img] if c_img is not None else ""
            _add(items, nombre, clave, existencia, dep, precio, cat, img)
    else:
        # Intento B: bloques "Etiqueta: valor"
        nom = cla = dep = cat = img = None
        exi = 0
        pre = 0
        for row in ws.iter_rows(values_only=True):
            raw = [c if c is not None else "" for c in row]
            line = [str(c).strip() for c in raw]
            if any(line):
                joined = " ".join(line)
                if ":" not in joined and not nom:
                    nom = joined
                for i, val in enumerate(line):
                    lv = _norm(val)
                    if lv.startswith("clave"):
                        cla = _right_value(raw, i)
                    elif lv.startswith("existencia"):
                        exi = _right_value(raw, i)
                    elif lv.startswith("departamento"):
                        dep = _right_value(raw, i)
                    elif lv.startswith("precio"):
                        pre = _right_value(raw, i)
                    elif lv.startswith("categoria"):
                        cat = _right_value(raw, i)
            else:
                if nom or cla:
                    _add(items, nom, cla, exi, dep, pre, cat)
                nom = cla = dep = cat = None
                exi = pre = 0
        if nom or cla:
            _add(items, nom, cla, exi, dep, pre, cat)

    # Filtro (si q vacío, devolvemos primera página)
    if q:
        s = _norm(q)

        def ok(it):
            return (
                s in _norm(it["nombre"]) or
                s in _norm(it["clave"]) or
                s in _norm(it["departamento"]) or
                s in _norm(it["categoria"]) or
                s in _norm(str(it["existencia"])) or
                (s.replace(".", "").isdigit() and abs(it["precio"] - _to_float(q)) < 1e-9)
            )

        items = [it for it in items if ok(it)]

    total = len(items)
    page = max(page, 1)
    start = (page - 1) * per_page
    end = start + per_page
    return {"items": items[start:end], "total": total, "page": page, "per_page": per_page}

