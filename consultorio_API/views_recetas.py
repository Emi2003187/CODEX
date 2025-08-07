from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden
from django.views.generic import DetailView
from io import BytesIO

from .models import Receta
from .pdf.receta_reportlab import build_receta_pdf


class _RecetaPDFBase(LoginRequiredMixin, DetailView):
    model = Receta
    pk_url_kwarg = "pk"

    def get(self, request, *args, **kwargs):
        receta = self.get_object()
        if not request.user.has_perm("consultorio.view_receta"):
            return HttpResponseForbidden()
        buf = BytesIO()
        build_receta_pdf(buf, receta)
        buf.seek(0)
        filename = f"receta_{receta.pk}.pdf"
        resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{filename}"'
        return resp


class RecetaPreviewView(_RecetaPDFBase):
    """Previsualización/impresión de receta generada con ReportLab."""


class RxRecetaView(_RecetaPDFBase):
    pass


class RecetaA5View(_RecetaPDFBase):
    pass
