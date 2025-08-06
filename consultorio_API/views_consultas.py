from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseForbidden, JsonResponse
from django import forms
from django.db.models import Q

from .forms import ConsultaSinCitaForm
from .models import Consulta, Paciente
from .views import ConsultaSinCitaCreateView

def puede_modificar(user, consulta):
    """Return True if user is admin or the assigned medico."""
    return user.rol == 'admin' or consulta.medico == user


@login_required
@require_POST
def cancelar_consulta(request, pk):
    """Cancelar una consulta si el usuario tiene permisos."""
    ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if request.user.rol == "asistente":
        if ajax:
            return JsonResponse(
                {"error": "No tienes permiso para cancelar consultas."},
                status=403,
            )
        return HttpResponseForbidden("No tienes permiso para cancelar consultas.")

    consulta = get_object_or_404(Consulta, pk=pk)
    if not puede_modificar(request.user, consulta):
        if ajax:
            return JsonResponse(
                {"error": "Acción no autorizada."},
                status=403,
            )
        messages.error(request, "Acción no autorizada.")
        return redirect("consultas_lista")

    consulta.estado = "cancelada"
    consulta.save(update_fields=["estado"])

    if consulta.cita:
        consulta.cita.estado = "cancelada"
        consulta.cita.save(update_fields=["estado"])

    if ajax:
        next_url = request.POST.get("next") or reverse("consultas_lista")
        return JsonResponse({"success": True, "redirect_url": next_url})

    messages.success(request, "Consulta cancelada.")
    return redirect(request.POST.get("next") or "consultas_lista")


@login_required
@require_POST
def eliminar_consulta(request, pk):
    """Eliminar una consulta si el usuario tiene permisos."""
    ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if request.user.rol != "admin":
        if ajax:
            return JsonResponse(
                {"error": "No tienes permiso para eliminar consultas."},
                status=403,
            )
        messages.error(request, "No puedes eliminar consultas.")
        return redirect("consultas_lista")

    consulta = get_object_or_404(Consulta, pk=pk)
    if not puede_modificar(request.user, consulta):
        if ajax:
            return JsonResponse(
                {"error": "Acción no autorizada."},
                status=403,
            )
        messages.error(request, "Acción no autorizada.")
        return redirect("consultas_lista")

    if consulta.cita:
        consulta.cita.delete()
    consulta.delete()

    if ajax:
        next_url = request.POST.get("next") or reverse("consultas_lista")
        return JsonResponse({"success": True, "redirect_url": next_url})

    messages.success(request, "Consulta eliminada.")
    return redirect(request.POST.get("next") or "consultas_lista")


class ConsultaCreateFromPacienteView(ConsultaSinCitaCreateView):
    """Crear una consulta con el paciente preseleccionado."""
    model = Consulta
    form_class = ConsultaSinCitaForm
    template_name = 'PAGES/consultas/crear_sin_cita.html'
    success_url = reverse_lazy('consultas_lista')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        paciente_id = self.kwargs.get('paciente_id')
        if paciente_id:
            initial['paciente'] = get_object_or_404(Paciente, pk=paciente_id)
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        paciente_id = self.kwargs.get('paciente_id')
        if paciente_id:
            form.fields['paciente'].queryset = Paciente.objects.filter(pk=paciente_id)
            form.fields['paciente'].empty_label = None
            form.fields['paciente'].disabled = True
        return form


@login_required
def lista_consultas(request):
    """Listado básico de consultas con filtros por fecha, estado y médico"""
    consultas = Consulta.objects.all().select_related("paciente", "medico")

    buscar = request.GET.get("buscar", "").strip()
    estado = request.GET.get("estado", "").strip()
    medico = request.GET.get("medico", "").strip()
    fecha = request.GET.get("fecha", "").strip()

    if buscar:
        consultas = consultas.filter(
            Q(paciente__nombre_completo__icontains=buscar)
            | Q(motivo_consulta__icontains=buscar)
        )

    if estado:
        consultas = consultas.filter(estado=estado)

    if medico:
        consultas = consultas.filter(medico_id=medico)

    if fecha:
        consultas = consultas.filter(fecha_atencion__date=fecha)

    consultas = consultas.order_by("-fecha_atencion")

    return render(request, "PAGES/consultas/lista.html", {"consultas": consultas})
