from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django import forms

from .forms import ConsultaSinCitaForm
from .models import Consulta, Paciente
from .views import ConsultaSinCitaCreateView

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
