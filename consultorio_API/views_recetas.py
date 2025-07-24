from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.views.generic import DetailView

from .models import Receta


class RecetaPreviewView(LoginRequiredMixin, DetailView):
    """Previsualización simple de una receta para mostrar en un modal."""

    model = Receta
    template_name = "PAGES/recetas/_preview.html"
    context_object_name = "receta"

    def dispatch(self, request, *args, **kwargs):
        receta = self.get_object()
        if not request.user.has_perm("consultorio.view_receta"):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)
