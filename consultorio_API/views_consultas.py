from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Consulta


def puede_modificar(user, consulta):
    """Return True if user is admin or the assigned medico."""
    return user.rol == 'admin' or consulta.medico == user


@login_required
@require_POST
def cancelar_consulta(request, pk):
    consulta = get_object_or_404(Consulta, pk=pk)
    if not puede_modificar(request.user, consulta):
        messages.error(request, "Acción no autorizada.")
        return redirect("consultas_lista")

    consulta.estado = "cancelada"
    consulta.save(update_fields=["estado"])

    if consulta.cita:
        consulta.cita.estado = "cancelada"
        consulta.cita.save(update_fields=["estado"])

    messages.success(request, "Consulta cancelada.")
    return redirect(request.POST.get("next") or "consultas_lista")


@login_required
@require_POST
def eliminar_consulta(request, pk):
    consulta = get_object_or_404(Consulta, pk=pk)
    if not puede_modificar(request.user, consulta):
        messages.error(request, "Acción no autorizada.")
        return redirect("consultas_lista")

    if consulta.cita:
        consulta.cita.delete()
    consulta.delete()

    messages.success(request, "Consulta eliminada.")
    return redirect(request.POST.get("next") or "consultas_lista")
