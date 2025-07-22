from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .models import Consultorio
from .forms import ConsultorioForm
from .views import AdminRequiredMixin, NextRedirectMixin


@method_decorator(login_required, name="dispatch")
class ConsultorioListView(AdminRequiredMixin, ListView):
    model = Consultorio
    template_name = "PAGES/consultorios/lista.html"
    context_object_name = "consultorios"
    paginate_by = 8

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(ubicacion__icontains=q))
        return qs.order_by("nombre")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["usuario"] = self.request.user
        return ctx


@method_decorator(login_required, name="dispatch")
class ConsultorioDetailView(AdminRequiredMixin, DetailView):
    model = Consultorio
    template_name = "PAGES/consultorios/detalle.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        return ctx


@method_decorator(login_required, name="dispatch")
class ConsultorioCreateView(NextRedirectMixin, AdminRequiredMixin, CreateView):
    model = Consultorio
    form_class = ConsultorioForm
    template_name = "PAGES/consultorios/form.html"
    success_url = reverse_lazy("consultorios_lista")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        ctx["next"] = self.get_next_url()
        return ctx


@method_decorator(login_required, name="dispatch")
class ConsultorioUpdateView(NextRedirectMixin, AdminRequiredMixin, UpdateView):
    model = Consultorio
    form_class = ConsultorioForm
    template_name = "PAGES/consultorios/form.html"
    success_url = reverse_lazy("consultorios_lista")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        ctx["next"] = self.get_next_url()
        return ctx


@method_decorator(login_required, name="dispatch")
class ConsultorioDeleteView(AdminRequiredMixin, DeleteView):
    model = Consultorio
    template_name = "PAGES/consultorios/confirm_delete.html"
    success_url = reverse_lazy("consultorios_lista")

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url:
            return next_url
        return super().get_success_url()

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Consultorio eliminado.")
        return super().delete(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        next_url = request.POST.get("next")
        if next_url:
            return redirect(next_url)
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        ctx["next"] = self.request.GET.get("next", self.request.META.get("HTTP_REFERER", ""))
        return ctx

