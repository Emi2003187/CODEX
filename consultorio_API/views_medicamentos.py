from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, List

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .forms import ExcelUploadForm, MedicamentoCatalogoForm
from .models import MedicamentoCatalogo

try:  # pragma: no cover - dependencia opcional
    import xlrd
except Exception:  # pragma: no cover
    xlrd = None

try:  # pragma: no cover
    from openpyxl import load_workbook
except Exception:  # pragma: no cover
    load_workbook = None


LABEL_PREFIXES = (
    "clave:",
    "departamento:",
    "categoría:",
    "categoria:",
    "existencia:",
    "precio:",
)


def _clean_price(value: str) -> Decimal | None:
    raw = (value or "").replace("$", "").replace(",", "").strip()
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch in "-." )
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _clean_int(value: str) -> int | None:
    raw = (value or "").strip().replace(",", "")
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch in "-.")
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except (TypeError, ValueError):
        return None


def _extract_lines_from_xlsx(content: bytes) -> List[str]:
    if not load_workbook:
        raise ValueError("No se puede procesar archivos .xlsx en este entorno.")
    wb = load_workbook(filename=io.BytesIO(content), data_only=True)
    lines: List[str] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell is None:
                    continue
                text = str(cell).strip()
                if text:
                    lines.append(text)
    return lines


def _extract_lines_from_xls(content: bytes) -> List[str]:
    if not xlrd:
        raise ValueError("Instale xlrd para procesar archivos .xls")
    book = xlrd.open_workbook(file_contents=content)
    lines: List[str] = []
    for sheet in book.sheets():
        for rx in range(sheet.nrows):
            for cx in range(sheet.ncols):
                val = sheet.cell_value(rx, cx)
                if val in (None, ""):
                    continue
                text = str(val).strip()
                if text:
                    lines.append(text)
    return lines


def _extract_lines_from_csv(content: bytes) -> List[str]:
    text = content.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    lines: List[str] = []
    for row in reader:
        for cell in row:
            cell = (cell or "").strip()
            if cell:
                lines.append(cell)
    return lines


def _extract_text_lines(uploaded_file) -> List[str]:
    content = uploaded_file.read()
    ext = Path(uploaded_file.name).suffix.lower()
    if ext == ".xlsx":
        return _extract_lines_from_xlsx(content)
    if ext == ".xls":
        return _extract_lines_from_xls(content)
    if ext == ".csv":
        return _extract_lines_from_csv(content)
    raise ValueError("Formato no soportado")


def _find_value(block: Iterable[str], label: str) -> str:
    for entry in block:
        e = str(entry)
        if e.lower().startswith(label):
            return e.split(":", 1)[-1].strip()
    return ""


@transaction.atomic
def procesar_catalogo_excel(uploaded_file) -> dict:
    lines = _extract_text_lines(uploaded_file)
    created = 0
    updated = 0
    errores: List[str] = []
    processed = 0

    i = 0
    total_lines = len(lines)
    while i < total_lines:
        texto = (lines[i] or "").strip()
        lower = texto.lower()
        if not texto:
            i += 1
            continue
        if any(lower.startswith(prefix) for prefix in LABEL_PREFIXES):
            i += 1
            continue

        nombre = texto
        ventana = lines[i + 1 : i + 7]
        block_span = 1 + len(ventana)  # nombre + filas capturadas
        clave = _find_value(ventana, "clave:")
        departamento = _find_value(ventana, "departamento:") or None
        categoria = _find_value(ventana, "categoría:") or _find_value(
            ventana, "categoria:"
        )
        existencia_raw = _find_value(ventana, "existencia:")
        precio_raw = _find_value(ventana, "precio:")

        existencia = _clean_int(existencia_raw)
        precio = _clean_price(precio_raw)

        errores_item = []
        if not clave:
            errores_item.append("Falta la clave")
        if not existencia_raw:
            errores_item.append("Falta la existencia")
        elif existencia is None:
            errores_item.append("Existencia inválida")
        if not precio_raw:
            errores_item.append("Falta el precio")
        elif precio is None:
            errores_item.append("Precio inválido")

        if errores_item:
            errores.append(f"{nombre}: {', '.join(errores_item)}")
            i += block_span
            continue

        defaults = {
            "nombre": nombre[:255],
            "departamento": departamento or None,
            "categoria": categoria or None,
            "existencia": existencia or 0,
            "precio": precio,
        }
        obj, creado = MedicamentoCatalogo.objects.update_or_create(
            clave=str(clave).strip(), defaults=defaults
        )
        created += int(creado)
        updated += int(not creado)
        processed += 1
        i += block_span

    if processed == 0:
        raise ValueError("El archivo no tiene el formato esperado o está vacío.")

    return {"creados": created, "actualizados": updated, "errores": errores}


class MedicamentoExcelUploadView(LoginRequiredMixin, View):
    template_name = "medicamentos/cargar_excel.html"

    def get(self, request):
        form = ExcelUploadForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = ExcelUploadForm(request.POST, request.FILES)
        reporte = None
        if form.is_valid():
            try:
                reporte = procesar_catalogo_excel(request.FILES["archivo"])
                mensajes = []
                if reporte["creados"]:
                    mensajes.append(f"{reporte['creados']} creados")
                if reporte["actualizados"]:
                    mensajes.append(f"{reporte['actualizados']} actualizados")
                resumen = ", ".join(mensajes) or "Sin cambios"
                messages.success(request, f"Importación completada: {resumen}.")
                if reporte.get("errores"):
                    messages.warning(
                        request,
                        "Algunos artículos presentaron errores y se omitieron.",
                    )
            except ValueError as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Cargue un archivo válido (.xlsx, .xls o .csv).")

        return render(request, self.template_name, {"form": form, "reporte": reporte})


@login_required
def medicamentos_lista(request):
    query = MedicamentoCatalogo.objects.all().order_by("nombre")
    q = (request.GET.get("q") or "").strip()
    if q:
        query = query.filter(
            Q(nombre__icontains=q)
            | Q(clave__icontains=q)
            | Q(categoria__icontains=q)
            | Q(departamento__icontains=q)
        )
    paginator = Paginator(query, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {
        "page_obj": page_obj,
        "medicamentos": page_obj,
        "q": q,
    }
    return render(request, "medicamentos/lista.html", context)


@login_required
def medicamentos_crear(request):
    if request.method == "POST":
        form = MedicamentoCatalogoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Medicamento creado correctamente.")
            return redirect("medicamentos_lista")
    else:
        form = MedicamentoCatalogoForm()
    return render(request, "medicamentos/crear.html", {"form": form})


@login_required
def medicamentos_editar(request, pk: int):
    medicamento = get_object_or_404(MedicamentoCatalogo, pk=pk)
    if request.method == "POST":
        form = MedicamentoCatalogoForm(request.POST, request.FILES, instance=medicamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Medicamento actualizado correctamente.")
            return redirect("medicamentos_lista")
    else:
        form = MedicamentoCatalogoForm(instance=medicamento)
    return render(
        request,
        "medicamentos/editar.html",
        {"form": form, "medicamento": medicamento},
    )


@login_required
def medicamentos_eliminar(request, pk: int):
    medicamento = get_object_or_404(MedicamentoCatalogo, pk=pk)
    if request.method == "POST":
        medicamento.delete()
        messages.success(request, "Medicamento eliminado correctamente.")
        return redirect("medicamentos_lista")
    return render(
        request,
        "medicamentos/eliminar.html",
        {"medicamento": medicamento},
    )
