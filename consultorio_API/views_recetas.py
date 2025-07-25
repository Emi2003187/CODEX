from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.views.generic import DetailView
from django.utils import timezone
from datetime import timedelta

from .models import Receta


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["medico"] = self.object.consulta.medico
        ctx["paciente"] = self.object.consulta.paciente
        ctx["consultorio"] = self.object.consulta.medico.consultorio
        return ctx

    def dispatch(self, request, *args, **kwargs):
        receta = self.get_object()
        if not request.user.has_perm("consultorio.view_receta"):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)
