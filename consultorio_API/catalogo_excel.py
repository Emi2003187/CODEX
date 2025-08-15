"""
Lector SOLO LECTURA del catálogo Excel.

Campos por artículo a devolver:
- nombre         (Nombre/Presentación)
- clave          (código de barras / GTIN)
- existencia     (int)
- departamento   (str)
- precio         (float, sin $)
- categoria      (str)

Filtra por: nombre, clave, existencia, departamento, precio, categoria
(case/acento-insensible). Si el Excel no existe, devolver 0 resultados.
"""
from pathlib import Path
from typing import List, Dict
import unicodedata
from django.conf import settings

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover - openpyxl may not be installed
    load_workbook = None

EXCEL_PATH = Path(getattr(settings, "CATALOGO_EXCEL_PATH"))


def catalogo_disponible() -> bool:
    return EXCEL_PATH.exists() and load_workbook is not None


# ---- Helpers ---------------------------------------------------------------

FIELD_ALIASES = {
    "nombre": ["descripcion", "nombre", "presentacion", "articulo"],
    "clave": ["clave", "codigo", "codigo_barras", "barcode", "gtin", "codigo de barras", "código", "código barras"],
    "existencia": ["existencia", "stock"],
    "departamento": ["departamento"],
    "precio": ["precio"],
    "categoria": ["categoria", "categoria", "categoría"],
}

LABEL_ALIASES = {
    **{f"{a}": k for k, v in FIELD_ALIASES.items() for a in v},
    "nombre/presentacion": "nombre",
    "nombre presentacion": "nombre",
}


def _norm_text(s: str) -> str:
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()


def _parse_int(v):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None


def _parse_float(v):
    if v is None:
        return None
    try:
        s = str(v)
        for ch in "$ ,":
            s = s.replace(ch, "")
        return float(s)
    except Exception:
        return None


def _clean_str(v):
    return str(v).strip() if v is not None else ""


def _parse_rows_tabular(rows) -> List[Dict]:
    items: List[Dict] = []
    header_map = {}
    for idx, row in enumerate(rows[:20]):
        normalized = [_norm_text(c) for c in row]
        tmp = {}
        for col_idx, val in enumerate(normalized):
            key = LABEL_ALIASES.get(val)
            if key:
                tmp[col_idx] = key
        if "clave" in tmp.values():
            header_map = tmp
            start = idx + 1
            break
    if not header_map:
        return items
    for row in rows[start:]:
        if all(c in (None, "") for c in row):
            continue
        item = {"nombre": "", "clave": "", "existencia": None, "departamento": "", "precio": None, "categoria": ""}
        for col_idx, key in header_map.items():
            if col_idx >= len(row):
                continue
            val = row[col_idx]
            if key == "existencia":
                item[key] = _parse_int(val)
            elif key == "precio":
                item[key] = _parse_float(val)
            else:
                item[key] = _clean_str(val)
        if item.get("clave"):
            items.append(item)
    return items


def _parse_rows_block(rows) -> List[Dict]:
    items: List[Dict] = []
    current = {}
    for row in rows:
        if not row or all(c in (None, "") for c in row):
            continue
        key_cell = row[0]
        val_cell = row[1] if len(row) > 1 else None
        if isinstance(key_cell, str):
            key_norm = _norm_text(key_cell).rstrip(":")
            field = LABEL_ALIASES.get(key_norm)
            if field:
                if field == "clave" and current.get("clave"):
                    if current.get("clave"):
                        items.append(current)
                    current = {}
                if field == "existencia":
                    current[field] = _parse_int(val_cell)
                elif field == "precio":
                    current[field] = _parse_float(val_cell)
                else:
                    current[field] = _clean_str(val_cell)
    if current.get("clave"):
        items.append(current)
    return items


def _leer_items() -> List[Dict]:
    if not catalogo_disponible():
        return []
    try:
        wb = load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    except Exception:
        return []
    items: List[Dict] = []
    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        parsed = _parse_rows_tabular(rows)
        if not parsed:
            parsed = _parse_rows_block(rows)
        items.extend(parsed)
    return items


def buscar_articulos(q: str = "", page: int = 1, per_page: int = 15) -> dict:
    """
    Implementar con openpyxl *sin* pandas.
    - Tolerante a formatos: etiqueta "Clave:" a la izquierda y valor a la derecha,
      o bien hoja tabular con encabezados.
    - Normaliza valores (quita '$', castea enteros/floats, strip).
    - Búsqueda case/acento-insensible en: nombre, clave, departamento, categoria;
      si q es numérico, compara también contra precio.
    - Paginación simple.
    Return:
      {"items":[{nombre, clave, existencia, departamento, precio, categoria}],
       "total": N, "page": page, "per_page": per_page}
    """
    items = _leer_items()
    if q:
        q_norm = _norm_text(q)
        q_num = None
        try:
            q_num = float(q.replace(",", "."))
        except Exception:
            pass
        filtered = []
        for it in items:
            if (
                q_norm in _norm_text(it.get("nombre"))
                or q_norm in _norm_text(it.get("clave"))
                or q_norm in _norm_text(it.get("departamento"))
                or q_norm in _norm_text(it.get("categoria"))
            ):
                filtered.append(it)
                continue
            if q_num is not None:
                if (it.get("precio") is not None and it["precio"] == q_num) or (
                    it.get("existencia") is not None and float(it["existencia"]) == q_num
                ):
                    filtered.append(it)
        items = filtered
    total = len(items)
    start = max((page - 1) * per_page, 0)
    end = start + per_page
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
