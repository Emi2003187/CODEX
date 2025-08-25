from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import (
    FileResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import DetailView
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction
from io import BytesIO
from django.utils import timezone
from django.utils.text import slugify

from .models import Receta, MedicamentoRecetado
from .pdf.receta_reportlab import build_receta_pdf
from .catalogo_excel import (
    buscar_articulos,
    catalogo_disponible,
    limpiar_cache_catalogo,
)
from django.views.decorators.csrf import csrf_exempt


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

    buf = BytesIO()
    build_receta_pdf(buf, receta)
    buf.seek(0)
    fecha = receta.fecha_emision or timezone.now()
    filename = f"{receta.pk}_{slugify(receta.consulta.paciente.nombre_completo)}_{fecha.strftime('%Y%m%d')}.pdf"
    return FileResponse(buf, as_attachment=False, filename=filename, content_type="application/pdf")


@login_required
@require_GET
def catalogo_excel_json(request):
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page") or 1)
    per_page = int(request.GET.get("per_page") or 15)

    data = buscar_articulos(q=q, page=page, per_page=per_page)
    for it in data.get("items", []):
        if it.get("imagen_url"):
            it["imagen"] = it["imagen_url"]
        it.pop("imagen_url", None)

    return JsonResponse(data)


@csrf_exempt
@login_required
@require_POST
def catalogo_excel_limpiar_cache(request):
    """Limpia la caché del catálogo de medicamentos."""
    limpiar_cache_catalogo()
    return JsonResponse({"ok": True})


@login_required
@require_GET
def receta_catalogo_excel(request, receta_id):
    receta = get_object_or_404(Receta, id=receta_id)
    return render(
        request,
        "PAGES/recetas/catalogo_excel.html",
        {"receta": receta, "excel_disponible": catalogo_disponible()},
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
    if clave or nombre:
        data = buscar_articulos(q=clave or nombre, page=1, per_page=1)
        items = data.get("items", [])
        if items:
            cat = items[0]

    cat_nombre = cat.get("nombre") if cat else nombre

    mr = None
    if clave:
        mr = MedicamentoRecetado.objects.filter(
            receta=receta, codigo_barras=clave
        ).first()
    if not mr:
        mr = MedicamentoRecetado.objects.filter(
            receta=receta, nombre=cat_nombre
        ).first()

    if mr:
        mr.cantidad += cantidad
        if not mr.codigo_barras and clave:
            mr.codigo_barras = clave
        if cat:
            mr.existencia = cat.get("existencia", mr.existencia)
            mr.categoria = cat.get("categoria", mr.categoria)
            mr.departamento = cat.get("departamento", mr.departamento)
        mr.save()
    else:
        mr = MedicamentoRecetado.objects.create(
            receta=receta,
            nombre=cat_nombre,
            cantidad=cantidad,
            existencia=cat.get("existencia", 0) if cat else 0,
            codigo_barras=cat.get("clave") if cat else (clave or None),
            categoria=cat.get("categoria") if cat else None,
            departamento=cat.get("departamento") if cat else None,
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
    items = [
        {
            "id": mr.id,
            "nombre": mr.nombre,
            "principio_activo": mr.principio_activo or "",
            "cantidad": mr.cantidad,
            "codigo_barras": mr.codigo_barras or "",
        }
        for mr in receta.medicamentos.all()
    ]
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
