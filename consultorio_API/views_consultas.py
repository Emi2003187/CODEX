from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Consulta


@require_POST
@login_required
def eliminar_consulta(request, pk):
    """Eliminar una consulta y su cita asociada si existe."""
    consulta = get_object_or_404(Consulta, pk=pk)

    if not (request.user == consulta.medico or request.user.rol == "admin"):
        messages.error(request, "Acción no autorizada.")
        return redirect(request.POST.get("next") or reverse("consultas_lista"))

    if consulta.estado == "en_progreso":
        messages.error(request, "Acción no autorizada.")
        return redirect(request.POST.get("next") or reverse("consultas_lista"))

    if consulta.cita:
        consulta.cita.delete()
    consulta.delete()

    messages.success(request, "Consulta eliminada correctamente.")
    return redirect(request.POST.get("next") or reverse("consultas_lista"))


@require_POST
@login_required
def cancelar_consulta(request, pk):
    """Cancelar una consulta y su cita asociada si existe."""
    consulta = get_object_or_404(Consulta, pk=pk)

    if not (request.user == consulta.medico or request.user.rol == "admin"):
        messages.error(request, "Acción no autorizada.")
        return redirect(request.POST.get("next") or reverse("consultas_lista"))

    if consulta.estado not in ["espera", "en_progreso"]:
        messages.error(request, "Acción no autorizada.")
        return redirect(request.POST.get("next") or reverse("consultas_lista"))

    consulta.estado = "cancelada"
    consulta.save()

    if consulta.cita:
        consulta.cita.estado = "cancelada"
        consulta.cita.save()

    messages.success(request, "Consulta cancelada.")
    return redirect(request.POST.get("next") or reverse("consultas_lista"))
