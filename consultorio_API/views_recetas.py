from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden
from django.views.generic import DetailView
from django.utils import timezone
from datetime import timedelta

from .models import Receta

# NUEVO:
from io import BytesIO
from .pdf.receta_reportlab import build_receta_pdf


def receta_pdf_reportlab(request, pk: int):
    receta = Receta.objects.select_related(
        "consulta", "consulta__paciente", "consulta__medico"
    ).prefetch_related("medicamentos").get(pk=pk)

    # Permisos equivalentes a las vistas actuales de receta
    if not request.user.has_perm("consultorio.view_receta"):
        return HttpResponseForbidden()

    buf = BytesIO()
    build_receta_pdf(buf, receta)
    buf.seek(0)

    filename = f"receta_{receta.pk}.pdf"
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


class RecetaPreviewView(LoginRequiredMixin, DetailView):
    """Previsualización de receta reutilizada para impresión y PDF."""

    model = Receta
    template_name = "PAGES/recetas/_receta_base.html"
    context_object_name = "receta"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["show_logo"] = True
        receta = ctx["receta"]
        receta.fecha_validez = receta.valido_hasta or (
            receta.fecha_emision + timedelta(days=2)
        )
        return ctx

    def dispatch(self, request, *args, **kwargs):
        receta = self.get_object()
        if not request.user.has_perm("consultorio.view_receta"):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class RxRecetaView(LoginRequiredMixin, DetailView):
    """Receta con estilo tipo Rx para impresión simplificada."""

    model = Receta
    template_name = "PAGES/recetas/rx_receta.html"
    context_object_name = "receta"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        receta = ctx["receta"]
        receta.fecha_validez = receta.fecha_emision + timedelta(days=2)
        ctx["show_logo"] = True
        return ctx

    def dispatch(self, request, *args, **kwargs):
        receta = self.get_object()
        if not request.user.has_perm("consultorio.view_receta"):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class RecetaA5View(LoginRequiredMixin, DetailView):
    model = Receta
    template_name = "PAGES/recetas/receta_a5.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["show_logo"] = True
        ctx["receta"].fecha_validez = ctx["receta"].fecha_emision + timedelta(days=2)
        return ctx
