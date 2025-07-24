from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.views.generic import DetailView
from django.utils import timezone

from .models import Receta


class RecetaPreviewView(LoginRequiredMixin, DetailView):
    """Previsualización simple de una receta para mostrar en un modal."""

    model = Receta
    template_name = "PAGES/pdf/receta_consulta.html"
    context_object_name = "receta"
    pk_url_kwarg = "receta_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["consulta"] = self.object.consulta
        context["fecha_actual"] = timezone.now()
        return context

    def dispatch(self, request, *args, **kwargs):
        receta = self.get_object()
        if not request.user.has_perm("consultorio.view_receta"):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)
