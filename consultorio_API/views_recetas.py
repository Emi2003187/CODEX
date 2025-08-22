from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import (
    FileResponse,
    HttpResponseForbidden,
    JsonResponse,
    HttpResponseBadRequest,
)
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import DetailView
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction
from io import BytesIO
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings

from .models import Receta, MedicamentoRecetado, MedicamentoCatalogo
from .pdf.receta_reportlab import build_receta_pdf
from django.db.models import Q
from .catalogo_excel import buscar_articulos, catalogo_disponible
from .utils_barcode import barcode_base64


class _RecetaPDFBase(LoginRequiredMixin, DetailView):
    model = Receta
    pk_url_kwarg = "pk"

    def get(self, request, *args, **kwargs):
        receta = self.get_object()
        if receta.consulta.estado != "finalizada":
            messages.error(
                request,
                "La receta solo puede emitirse cuando la consulta está finalizada.",
            )
            return redirect("consulta_detalle", pk=receta.consulta.pk)

        # Generar códigos de barras en base64
        receta.barcode_base64 = barcode_base64(str(receta.pk))
        for m in receta.medicamentos.all():
            m.barcode_base64 = barcode_base64(m.codigo_barras or "")

        buf = BytesIO()
        build_receta_pdf(buf, receta)
        buf.seek(0)
        fecha = receta.fecha_emision or timezone.now()
        filename = f"{receta.pk}_{slugify(receta.consulta.paciente.nombre_completo)}_{fecha.strftime('%Y%m%d')}.pdf"
        return FileResponse(buf, as_attachment=False, filename=filename, content_type="application/pdf")


class RecetaPreviewView(_RecetaPDFBase):
    """Previsualización/impresión de receta generada con ReportLab."""

    def dispatch(self, request, *args, **kwargs):
        receta = self.get_object()
        if not (
            request.user.has_perm("consultorio.view_receta")
            or request.user == receta.consulta.medico
        ):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class RxRecetaView(RecetaPreviewView):
    pass


class RecetaA5View(_RecetaPDFBase):
    pass


def receta_pdf_reportlab(request, pk: int):
    receta = Receta.objects.select_related(
        "consulta", "consulta__paciente", "consulta__medico"
    ).prefetch_related("medicamentos").get(pk=pk)

    if not (
        request.user.has_perm("consultorio.view_receta")
        or request.user == getattr(receta.consulta, "medico", None)
    ):
        return HttpResponseForbidden()

    if receta.consulta.estado != "finalizada":
        messages.error(
            request,
            "La receta solo puede emitirse cuando la consulta está finalizada.",
        )
        return redirect("consulta_detalle", pk=receta.consulta.pk)

    receta.barcode_base64 = barcode_base64(str(receta.pk))
    for m in receta.medicamentos.all():
        m.barcode_base64 = barcode_base64(m.codigo_barras or "")

    buf = BytesIO()
    build_receta_pdf(buf, receta)
    buf.seek(0)
    fecha = receta.fecha_emision or timezone.now()
    filename = f"{receta.pk}_{slugify(receta.consulta.paciente.nombre_completo)}_{fecha.strftime('%Y%m%d')}.pdf"
    return FileResponse(buf, as_attachment=False, filename=filename, content_type="application/pdf")


# --- Catálogo Excel -------------------------------------------------------


def _ensure_catalogo():
    """Populate `MedicamentoCatalogo` from Excel if it's empty."""
    if MedicamentoCatalogo.objects.exists():
        return
    if not catalogo_disponible():
        return
    data = buscar_articulos(q="", page=1, per_page=1000000)
    items = data.get("items", [])
    if not items:
        return
    for it in items:
        codigo = str(it.get("codigo_barras") or it.get("clave") or "").strip()
        if not codigo:
            continue
        defaults = {
            "nombre": it.get("nombre", "")[:255],
            "presentacion": it.get("presentacion") or None,
            "clave": it.get("clave") or None,
            "imagen_url": it.get("imagen_url") or None,
        }
        MedicamentoCatalogo.objects.update_or_create(
            codigo_barras=codigo, defaults=defaults
        )


@login_required
@require_GET
def catalogo_excel_json(request):
    _ensure_catalogo()
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page") or 1)
    per_page = int(request.GET.get("per_page") or 15)

    qs = MedicamentoCatalogo.objects.all()
    if q:
        qs = qs.filter(
            Q(nombre__icontains=q)
            | Q(presentacion__icontains=q)
            | Q(codigo_barras__icontains=q)
            | Q(clave__icontains=q)
        )

    total = qs.count()
    start = (page - 1) * per_page
    items = []
    for m in qs[start : start + per_page]:
        items.append(
            {
                "nombre": m.nombre,
                "presentacion": m.presentacion or "",
                "clave": m.clave or "",
                "codigo_barras": m.codigo_barras,
                "imagen_url": m.imagen_url or "",
                "barcode_base64": barcode_base64(m.codigo_barras),
            }
        )
    return JsonResponse({"items": items, "total": total, "page": page, "per_page": per_page})


@login_required
@require_GET
def receta_catalogo_excel(request, receta_id):
    receta = get_object_or_404(Receta, id=receta_id)
    _ensure_catalogo()
    return render(
        request,
        "PAGES/recetas/catalogo_excel.html",
        {"receta": receta, "excel_disponible": MedicamentoCatalogo.objects.exists()},
    )


@login_required
@require_POST
@transaction.atomic
def receta_catalogo_excel_agregar(request, receta_id):
    receta = get_object_or_404(Receta, id=receta_id)
    nombre = (request.POST.get("nombre") or "").strip()
    clave = (request.POST.get("clave") or "").strip()
    try:
        cantidad = int(request.POST.get("cantidad") or "1")
    except Exception:
        cantidad = 1
    if cantidad < 1:
        cantidad = 1
    if not nombre and not clave:
        return JsonResponse({"ok": False, "error": "Nombre requerido"}, status=400)
    cat = None
    if clave:
        cat = MedicamentoCatalogo.objects.filter(codigo_barras=clave).first()
    mr = MedicamentoRecetado.objects.create(
        receta=receta,
        nombre=cat.nombre if cat else nombre,
        cantidad=cantidad,
        codigo_barras=cat.codigo_barras if cat else (clave or None),
    )
    return JsonResponse(
        {
            "ok": True,
            "id": str(mr.id),
            "nombre": mr.nombre,
            "cantidad": mr.cantidad,
            "codigo_barras": mr.codigo_barras or "",
            "principio_activo": mr.principio_activo or "",
        }
    )


@login_required
@require_GET
def receta_medicamentos_json(request, receta_id):
    """Devuelve los medicamentos actuales de la receta."""
    receta = get_object_or_404(Receta, id=receta_id)
    items = []
    for mr in receta.medicamentos.all():
        items.append(
            {
                "id": mr.id,
                "nombre": mr.nombre,
                "principio_activo": mr.principio_activo or "",
                "cantidad": mr.cantidad,
                "codigo_barras": mr.codigo_barras or "",
                "barcode_base64": barcode_base64(mr.codigo_barras or ""),
            }
        )
    return JsonResponse({"items": items})


@login_required
@require_POST
@transaction.atomic
def receta_medicamento_actualizar(request, receta_id, med_id):
    """Actualiza la cantidad de un medicamento en la receta."""
    receta = get_object_or_404(Receta, id=receta_id)
    med = get_object_or_404(MedicamentoRecetado, id=med_id, receta=receta)
    try:
        cantidad = int(request.POST.get("cantidad") or "1")
    except Exception:
        cantidad = 1
    if cantidad < 1:
        cantidad = 1
    med.cantidad = cantidad
    med.save()
    return JsonResponse({"ok": True, "id": med.id, "cantidad": med.cantidad})


@login_required
@require_POST
@transaction.atomic
def receta_medicamento_eliminar(request, receta_id, med_id):
    """Elimina un medicamento de la receta."""
    receta = get_object_or_404(Receta, id=receta_id)
    med = get_object_or_404(MedicamentoRecetado, id=med_id, receta=receta)
    med.delete()
    return JsonResponse({"ok": True})
