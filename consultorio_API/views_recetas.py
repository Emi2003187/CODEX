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
from django.core.paginator import Paginator
from django.db import transaction
from io import BytesIO
from django.utils import timezone
from django.utils.text import slugify

from .models import Receta, MedicamentoRecetado
from .pdf.receta_reportlab import build_receta_pdf
from .catalogo_excel import buscar_articulos, catalogo_disponible


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


# --- Catálogo Excel -------------------------------------------------------


@login_required
@require_GET
def catalogo_excel_json(request):
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page") or 1)
    per_page = int(request.GET.get("per_page") or 15)
    if not catalogo_disponible():
        return JsonResponse({"items": [], "total": 0, "page": 1, "per_page": per_page})
    return JsonResponse(buscar_articulos(q=q, page=page, per_page=per_page))


@login_required
@require_GET
def receta_catalogo_excel(request, receta_id):
    receta = get_object_or_404(Receta, id=receta_id)
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page") or 1)
    per_page = 15
    data = (
        buscar_articulos(q=q, page=page, per_page=per_page)
        if catalogo_disponible()
        else {"items": [], "total": 0, "page": 1, "per_page": per_page}
    )
    paginator = Paginator(range(data["total"]), per_page)
    try:
        page_obj = paginator.page(page)
    except Exception:
        page_obj = paginator.page(1)
    return render(
        request,
        "PAGES/recetas/catalogo_excel.html",
        {
            "receta": receta,
            "q": q,
            "items": data["items"],
            "page_obj": page_obj,
            "per_page": per_page,
            "excel_disponible": catalogo_disponible(),
        },
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
    if not nombre:
        return JsonResponse({"ok": False, "error": "Nombre requerido"}, status=400)
    mr = MedicamentoRecetado.objects.create(
        receta=receta,
        nombre=nombre,
        cantidad=cantidad,
        codigo_barras=clave or None,
    )
    return JsonResponse(
        {
            "ok": True,
            "id": str(mr.id),
            "nombre": mr.nombre,
            "cantidad": mr.cantidad,
            "codigo_barras": mr.codigo_barras or "",
        }
    )
