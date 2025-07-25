from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth import logout
from django.db.models import Q, Count, Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import get_template, render_to_string
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from xhtml2pdf import pisa
from datetime import datetime, timedelta, time, date
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

from consultorio_API.notifications import NotificationManager
from .serializers import UsuarioSerializer
from django.utils import timezone
from collections import OrderedDict, defaultdict
from django.utils.timezone import localtime
from django.forms import inlineformset_factory
from django.views.generic.edit import FormView
from django.core.paginator import Paginator
import json
import csv
from django.utils.deprecation import MiddlewareMixin
from django.contrib.contenttypes.models import ContentType
from .models import (
    Antecedente, Auditoria, HorarioMedico, MedicamentoActual, MedicamentoRecetado,
    Notificacion, Receta, SignosVitales, Usuario, Paciente, Cita, Consulta,
    Expediente, Consultorio
)
from .forms import *
from .utils import redirect_next
from django.utils.http import url_has_allowed_host_and_scheme


def doctor_tiene_consulta_en_progreso(medico):
    """Devuelve True si el médico tiene otra consulta en progreso."""
    return Consulta.objects.filter(medico=medico, estado="en_progreso").exists()


class NextRedirectMixin:
    """Mixin para manejar redirecciones basadas en ?next."""

    def get_next_url(self):
        return self.request.POST.get("next") or self.request.GET.get("next")

    def get_success_url(self):
        next_url = self.get_next_url()
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()}
        ):
            return next_url
        return super().get_success_url()

# ═══════════════════════════════════════════════════════════════
# 🔐 LOGIN Y DASHBOARD
# ═══════════════════════════════════════════════════════════════

class CustomLoginView(LoginView):
    template_name = "PAGES/login.html"
    authentication_form = LoginForm

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url:
            return next_url

        user = self.request.user
        if user.rol == "medico":
            return "/medico/dashboard/"
        elif user.rol == "asistente":
            return reverse("citas_lista")
        elif user.rol == "admin":
            return "/adm/dashboard/"
        return "/"

def logout_view(request):
    """Vista para cerrar sesión del usuario"""
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect_next(request, 'login')


def home_redirect(request):
    """Redirige la raíz `/` según el rol del usuario."""
    if request.user.is_authenticated:
        rol = getattr(request.user, 'rol', '')
        if rol == 'medico':
            return redirect('dashboard_medico')
        elif rol == 'asistente':
            return redirect('citas_lista')
        else:
            return redirect('dashboard_admin')
    return redirect_next(request, 'login')

# ═══════════════════════════════════════════════════════════════
# 🏠 DASHBOARDS CORREGIDOS
# ═══════════════════════════════════════════════════════════════

class BaseDashboardView(LoginRequiredMixin, View):
    """Vista base para dashboards con funcionalidad completa"""
    template_name = "PAGES/dashboard.html"
    rol_mostrado = "Usuario"

    def get_queryset_citas(self, user):
        """Filtrar citas según el rol del usuario - CORREGIDO"""
        qs = Cita.objects.select_related("paciente", "medico_asignado", "consultorio")
        if user.rol == "medico":
            qs = qs.filter(Q(consultorio=user.consultorio) | Q(medico_asignado=user))
        elif user.rol == "asistente" and user.consultorio:
            qs = qs.filter(consultorio=user.consultorio)
        return qs

    def get_queryset_consultas(self, user):
        """Filtrar consultas según el rol del usuario"""
        qs = Consulta.objects.select_related("paciente", "medico")
        if user.rol == "medico":
            qs = qs.filter(medico=user)
        elif user.rol == "asistente" and user.consultorio:
            qs = qs.filter(medico__consultorio=user.consultorio)
        return qs

    def get_estadisticas(self, user):
        hoy = timezone.now().date()
        ayer = hoy - timedelta(days=1)
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio_mes = hoy.replace(day=1)
        
        # Citas de hoy
        citas_hoy = self.get_queryset_citas(user).filter(fecha_hora__date=hoy).count()
        citas_ayer = self.get_queryset_citas(user).filter(fecha_hora__date=ayer).count()
        citas_hoy_diff = f"+{citas_hoy - citas_ayer}" if citas_hoy >= citas_ayer else f"{citas_hoy - citas_ayer}"
        
        # Consultas finalizadas esta semana
        consultas_finalizadas = self.get_queryset_consultas(user).filter(
            estado="finalizada",
            fecha_atencion__date__gte=inicio_semana
        ).count()
        
        # Consultas pendientes
        consultas_pendientes = self.get_queryset_consultas(user).filter(
            estado__in=["espera", "en_progreso"]
        ).count()
        
        # Pacientes totales y nuevos este mes
        pacientes_qs = Paciente.objects.all()
        if user.rol == "medico" and user.consultorio:
            pacientes_qs = pacientes_qs.filter(consultorio=user.consultorio)
        elif user.rol == "asistente" and user.consultorio:
            pacientes_qs = pacientes_qs.filter(consultorio=user.consultorio)
        
        pacientes_totales = pacientes_qs.count()
        
        # CORREGIDO: Usar el campo correcto o eliminar el filtro temporal
        try:
            if hasattr(Paciente, 'fecha_creacion'):
                pacientes_nuevos = pacientes_qs.filter(fecha_creacion__date__gte=inicio_mes).count()
            elif hasattr(Paciente, 'created_at'):
                pacientes_nuevos = pacientes_qs.filter(created_at__date__gte=inicio_mes).count()
            elif hasattr(Paciente, 'date_joined'):
                pacientes_nuevos = pacientes_qs.filter(date_joined__date__gte=inicio_mes).count()
            else:
                pacientes_nuevos = 0
        except:
            pacientes_nuevos = 0
        
        return {
            'citas_hoy': citas_hoy,
            'citas_hoy_diff': citas_hoy_diff,
            'consultas_finalizadas': consultas_finalizadas,
            'consultas_pendientes': consultas_pendientes,
            'pacientes_totales': pacientes_totales,
            'pacientes_nuevos': pacientes_nuevos,
        }

    def get_eventos_calendario(self, user):
        """Generar eventos para el calendario - CORREGIDO"""
        hoy = timezone.now()
        citas_futuras = self.get_queryset_citas(user).filter(
            fecha_hora__gte=hoy
        ).order_by('fecha_hora')[:50]

        eventos = []
        for cita in citas_futuras:
            color_map = {
                'programada': '#0d6efd',
                'confirmada': '#198754',
                'en_espera': '#ffc107',
                'completada': '#20c997',
                'cancelada': '#dc3545',
                'no_asistio': '#6c757d',
            }

            if user.rol == "admin":
                titulo = f"{cita.paciente.nombre_completo} • {cita.medico_asignado.get_full_name() if cita.medico_asignado else 'Sin médico'}"
            else:
                titulo = cita.paciente.nombre_completo

            eventos.append({
                "id": cita.id,
                "title": titulo,
                "start": cita.fecha_hora.isoformat(),
                "end": (cita.fecha_hora + timedelta(minutes=cita.duracion)).isoformat(),
                "color": color_map.get(cita.estado, '#0d6efd'),
                "motivo": cita.motivo or "Consulta general",
                "estado": cita.estado
            })

        return eventos

    def get_proximas_citas(self, user):
        """Obtener próximas 5 citas"""
        hoy = timezone.now()
        return self.get_queryset_citas(user).filter(
            fecha_hora__gte=hoy
        ).order_by('fecha_hora')[:5]

    def get_actividad_reciente(self, user):
        """Generar actividad reciente"""
        actividades = []
        
        # Consultas finalizadas recientes
        consultas_recientes = self.get_queryset_consultas(user).filter(
            estado="finalizada",
            fecha_atencion__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-fecha_atencion')[:3]

        for consulta in consultas_recientes:
            actividades.append({
                'tipo': 'consulta_finalizada',
                'titulo': 'Consulta finalizada',
                'descripcion': f"{consulta.paciente.nombre_completo} - {consulta.get_tipo_display()}",
                'fecha': consulta.fecha_atencion
            })

        # Citas próximas (próximas 2 horas)
        proximas = self.get_queryset_citas(user).filter(
            fecha_hora__gte=timezone.now(),
            fecha_hora__lte=timezone.now() + timedelta(hours=2)
        ).order_by('fecha_hora')[:2]

        for cita in proximas:
            actividades.append({
                'tipo': 'cita_proxima',
                'titulo': 'Cita próxima',
                'descripcion': f"{cita.paciente.nombre_completo} en {cita.fecha_hora.strftime('%H:%M')}",
                'fecha': cita.fecha_hora
            })

        # Ordenar por fecha
        actividades.sort(key=lambda x: x['fecha'], reverse=True)
        return actividades[:5]

    def get_datos_graficas(self, user):
        """Generar datos para las gráficas"""
        # Gráfica de estados
        estados_count = self.get_queryset_citas(user).values('estado').annotate(
            total=Count('id')
        )
        
        estado_map = ['programada', 'confirmada', 'en_espera', 'completada', 'cancelada', 'no_asistio']
        estado_labels = ['Programadas', 'Confirmadas', 'En Espera', 'Completadas', 'Canceladas', 'No Asistió']
        estado_data = []
        
        for estado in estado_map:
            count = next((x['total'] for x in estados_count if x['estado'] == estado), 0)
            estado_data.append(count)

        # Gráfica de consultas por día (últimos 30 días)
        hace_30 = timezone.now() - timedelta(days=30)
        consultas_por_dia = self.get_queryset_consultas(user).filter(
            estado="finalizada",
            fecha_atencion__date__gte=hace_30.date()
        ).extra(
            select={'dia': 'DATE(fecha_atencion)'}
        ).values('dia').annotate(
            total=Count('id')
        )

        # Crear lista de días
        dias = []
        data_dias = []
        for i in range(30):
            dia = (hace_30 + timedelta(days=i)).date()
            dias.append(dia.strftime('%d/%m'))
            count = next((x['total'] for x in consultas_por_dia if str(x['dia']) == str(dia)), 0)
            data_dias.append(count)

        return {
            'labels_estados': estado_labels,
            'data_estados': estado_data,
            'labels_dias': dias,
            'data_dias': data_dias
        }

    def get(self, request):
        user = request.user
        
        context = {
            'usuario': user,
            'rol': self.rol_mostrado,
            'stats': self.get_estadisticas(user),
            'eventos_json': json.dumps(self.get_eventos_calendario(user), default=str),
            'proximas_citas': self.get_proximas_citas(user),
            'actividad_reciente': self.get_actividad_reciente(user),
        }
        
        # Agregar datos de gráficas
        datos_graficas = self.get_datos_graficas(user)
        context.update({
            'labels_estados': json.dumps(datos_graficas['labels_estados']),
            'data_estados': json.dumps(datos_graficas['data_estados']),
            'labels_dias': json.dumps(datos_graficas['labels_dias']),
            'data_dias': json.dumps(datos_graficas['data_dias']),
        })
        
        return render(request, self.template_name, context)


# ─── mixin genérico por rol ──────────────────────────────────────────
from django.http import HttpResponseRedirect
from django.urls import reverse

class RoleRequiredMixin(UserPassesTestMixin):
    """Permite el acceso sólo a users con rol==required_role."""
    required_role: str | None = None  # «admin», «medico», «asistente»

    # ① Permiso
    def test_func(self) -> bool:
        return (
            self.request.user.is_authenticated
            and self.request.user.rol == self.required_role
        )

    # ② Qué hacer si no tiene permiso → redirigir a su propio dashboard
    def handle_no_permission(self):
        usr = self.request.user
        if not usr.is_authenticated:
            return HttpResponseRedirect(reverse("login"))

        destino = {
            "admin": "dashboard_admin",
            "medico": "dashboard_medico",
            "asistente": "dashboard_asistente",
        }.get(usr.rol, "login")

        return HttpResponseRedirect(reverse(destino))


@method_decorator(login_required, name="dispatch")
class DashboardAdmin(RoleRequiredMixin, BaseDashboardView):
    required_role = "admin"
    rol_mostrado = "Administrador"


@method_decorator(login_required, name="dispatch")
class DashboardMedico(RoleRequiredMixin, BaseDashboardView):
    required_role = "medico"
    rol_mostrado = "Médico"


@method_decorator(login_required, name="dispatch")
class DashboardAsistente(RoleRequiredMixin, View):
    required_role = "asistente"

    # Sólo redirige a lista de citas; igual protegemos acceso directo
    def get(self, request, *args, **kwargs):
        return redirect("citas_lista")


# ═══════════════════════════════════════════════════════════════
# 👥 USUARIOS (ADMIN)
# ═══════════════════════════════════════════════════════════════

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.rol == 'admin'

    def handle_no_permission(self):
        from .utils import redirect_next
        user = self.request.user
        if user.is_authenticated:
            if user.rol == 'medico':
                dashboard = 'dashboard_medico'
            elif user.rol == 'asistente':
                dashboard = 'dashboard_asistente'
            else:
                dashboard = 'dashboard_admin'
        else:
            dashboard = 'login'
        messages.error(self.request, 'No tienes permisos de administrador.')
        return redirect_next(self.request, dashboard)

# consultorio_API/views.py

class UsuarioListView(AdminRequiredMixin, ListView):
    """
    Vista de lista de usuarios para el panel de administración.

    • Muestra TODOS los usuarios (incluidos otros administradores),
      excepto el usuario actualmente autenticado.
    • Admite filtros por texto, rol y consultorio.
    • Paginación segura de 8 elementos por página (Django maneja automáticamente
      los casos en que la página solicitada no existe).
    """
    model               = Usuario
    template_name       = "PAGES/usuarios/lista.html"
    context_object_name = "usuarios"
    paginate_by         = 8

    # ────────────────────────────────────────────────────────────────
    #  Helpers
    # ────────────────────────────────────────────────────────────────
    def _rol_param_to_code(self, rol_param: str | None) -> str | None:
        """
        Convierte el parámetro de rol (que puede venir como código
        ─'admin', 'medico', 'asistente'─ **o** como display
        ─'Administrador', 'Médico', 'Asistente'─) al código interno.
        """
        if not rol_param:
            return None

        # Si ya es un código válido, regrésalo tal cual
        CODES = {c for c, _ in Usuario.ROLES}
        if rol_param in CODES:
            return rol_param

        # Caso contrario, mapear texto→código
        display_to_code = {display: code for code, display in Usuario.ROLES}
        return display_to_code.get(rol_param)

    # ────────────────────────────────────────────────────────────────
    #  Queryset principal
    # ────────────────────────────────────────────────────────────────
    def get_queryset(self):
        qs = Usuario.objects.all().exclude(pk=self.request.user.pk)

        # -------- filtros ----------
        q_raw       = self.request.GET.get("q", "").strip()
        rol_raw     = self.request.GET.get("rol", "").strip()
        consultorio = self.request.GET.get("consultorio", "").strip()

        if q_raw:
            qs = qs.filter(
                Q(first_name__icontains=q_raw)        |
                Q(last_name__icontains=q_raw)         |
                Q(email__icontains=q_raw)             |
                Q(consultorio__nombre__icontains=q_raw)
            )

        rol_code = self._rol_param_to_code(rol_raw)
        if rol_code:
            qs = qs.filter(rol=rol_code)

        if consultorio.isdigit():
            qs = qs.filter(consultorio_id=consultorio)

        return qs.order_by("first_name", "last_name")

    # ────────────────────────────────────────────────────────────────
    #  Contexto extra
    # ────────────────────────────────────────────────────────────────
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            usuario              = self.request.user,
            consultorios         = Consultorio.objects.all(),
            q                    = self.request.GET.get("q", ""),
            rol_selected         = self.request.GET.get("rol", ""),
            consultorio_selected = self.request.GET.get("consultorio", ""),
        )
        return ctx



class UsuarioCreateView(NextRedirectMixin, AdminRequiredMixin, CreateView):
    model = Usuario
    form_class = UsuarioForm
    template_name = 'PAGES/usuarios/crear.html'
    success_url = reverse_lazy('usuarios_lista')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        if self.request.user.rol == 'medico' and self.request.user.consultorio:
            self.object.consultorio = self.request.user.consultorio
        self.object.save()
        return redirect(self.get_success_url())


class UsuarioUpdateView(NextRedirectMixin, AdminRequiredMixin, UpdateView):
    model = Usuario
    form_class = UsuarioForm
    template_name = 'PAGES/usuarios/editar.html'
    success_url = reverse_lazy('usuarios_lista')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        return context


class UsuarioDeleteView(NextRedirectMixin, AdminRequiredMixin, DeleteView):
    model = Usuario
    template_name = 'PAGES/usuarios/eliminar.html'
    success_url = reverse_lazy('usuarios_lista')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        return context


# ═══════════════════════════════════════════════════════════════
# 👥 PACIENTES
# ═══════════════════════════════════════════════════════════════

class PacientePermisoMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.rol in ("medico", "admin")


class PacienteListView(PacientePermisoMixin, ListView):
    model = Paciente
    template_name = "PAGES/pacientes/lista.html"
    context_object_name = "pacientes"
    paginate_by = 15

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()

        if q:
            qs = qs.filter(
                Q(nombre_completo__icontains=q) |
                Q(id__iexact=q) |
                Q(telefono__icontains=q) |
                Q(correo__icontains=q) |
                Q(consultorio__nombre__icontains=q)
            )

        edad_param = self.request.GET.get("edad")
        if edad_param is not None and edad_param.isdigit():
            grupos = [
                (0, 12),
                (13, 17),
                (18, 30),
                (31, 45),
                (46, 60),
                (61, 75),
                (76, 120),
            ]
            idx = int(edad_param)
            if 0 <= idx < len(grupos):
                min_e, max_e = grupos[idx]
                hoy = date.today()
                fecha_max = hoy - timedelta(days=min_e * 365)
                fecha_min = hoy - timedelta(days=(max_e + 1) * 365)
                qs = qs.filter(fecha_nacimiento__range=(fecha_min, fecha_max))

        if self.request.user.rol == "medico" and self.request.user.consultorio:
            qs = qs.filter(consultorio=self.request.user.consultorio)

        return qs.order_by("nombre_completo")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class PacienteDetailView(LoginRequiredMixin, DetailView):
    model = Paciente
    template_name = "PAGES/pacientes/detalle.html"
    context_object_name = "paciente"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        paciente = self.get_object()
        ctx["usuario"] = self.request.user

        # antecedentes completos
        ctx["antecedentes"] = (
            paciente.expediente.antecedentes.exclude(tipo="alergico").order_by("-fecha_diagnostico")
            if hasattr(paciente, "expediente") else []
        )

        # alergias
        if hasattr(paciente, "expediente"):
            ctx["alergias"] = paciente.expediente.antecedentes.filter(tipo="alergico")
        else:
            ctx["alergias"] = []

        # medicamentos actuales
        ctx["medicamentos"] = (
            paciente.expediente.medicamentos_actuales.all().order_by("nombre")
            if hasattr(paciente, "expediente") else []
        )

        # historial de consultas
        consultas_qs = Consulta.objects.filter(paciente=paciente).order_by("-fecha_creacion")
        ctx["consultas"] = consultas_qs
        ctx["consultas_finalizadas"] = consultas_qs.filter(estado="finalizada")

        # últimos signos
        ctx["ultimos_signos"] = getattr(
            ctx["consultas"].first(), "signos_vitales", None
        ) if ctx["consultas"] else None

        return ctx


class PacienteCreateView(NextRedirectMixin, PacientePermisoMixin, CreateView):
    model = Paciente
    form_class = PacienteForm
    template_name = "PAGES/pacientes/crear.html"
    success_url = reverse_lazy("pacientes_lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        paciente = form.save(commit=False)
        user = self.request.user
        if user.rol == "medico":
            if not user.consultorio:
                messages.error(self.request, "No tienes consultorio asignado.")
                return HttpResponseRedirect(self.success_url)
            paciente.consultorio = user.consultorio
        else:
            paciente.consultorio = form.cleaned_data.get("consultorio")
        paciente.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        return ctx


class PacienteUpdateView(NextRedirectMixin, PacientePermisoMixin, UpdateView):
    model = Paciente
    form_class = PacienteForm
    template_name = "PAGES/pacientes/editar.html"
    success_url = reverse_lazy("pacientes_lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        paciente = form.save(commit=False)
        user = self.request.user
        if user.rol == "medico":
            if not user.consultorio:
                messages.error(self.request, "No tienes consultorio asignado.")
                return HttpResponseRedirect(self.success_url)
            paciente.consultorio = user.consultorio
        else:
            paciente.consultorio = form.cleaned_data.get("consultorio")
        paciente.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        return ctx


class PacienteDeleteView(NextRedirectMixin, PacientePermisoMixin, DeleteView):
    model = Paciente
    template_name = "PAGES/pacientes/eliminar.html"
    success_url = reverse_lazy("pacientes_lista")

    def delete(self, request, *args, **kwargs):
        paciente = self.get_object()
        if paciente.consulta_set.exists():
            messages.error(request, "No puedes eliminar un paciente con consultas asociadas.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        return ctx


# ═══════════════════════════════════════════════════════════════
# 📅 COLA VIRTUAL - USANDO LÓGICA DE LISTA_CITAS
# ═══════════════════════════════════════════════════════════════

def get_citas_queryset(user):
    """Función reutilizable para obtener citas según el rol del usuario"""
    if user.rol == 'admin':
        citas = Cita.objects.all()
    elif user.rol == 'medico':
        citas = Cita.objects.filter(
            Q(consultorio=user.consultorio) | Q(medico_asignado=user)
        )
    elif user.rol == 'asistente':
        if user.consultorio:
            citas = Cita.objects.filter(consultorio=user.consultorio)
        else:
            citas = Cita.objects.none()
    else:
        citas = Cita.objects.none()
    
    return citas.select_related('paciente', 'consultorio', 'medico_asignado', 'medico_preferido')


@login_required
def cola_virtual(request):
    """Vista principal de la cola virtual de citas - USANDO LÓGICA DE LISTA_CITAS"""
    user = request.user
    
    # Verificar permisos
    if user.rol not in ['medico', 'asistente', 'admin']:
        messages.error(request, 'No tienes permisos para acceder a la cola virtual.')
        return redirect_next(request, 'dashboard')
    
    # Obtener fecha (por defecto hoy)
    fecha_str = request.GET.get('fecha', timezone.now().date().strftime('%Y-%m-%d'))
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha = timezone.now().date()
    
    # Obtener consultorio
    consultorio_id = request.GET.get('consultorio')
    if user.rol == 'admin':
        if consultorio_id:
            consultorio = get_object_or_404(Consultorio, id=consultorio_id)
        else:
            consultorio = Consultorio.objects.first()
        consultorios = Consultorio.objects.all()
    else:
        consultorio = user.consultorio
        consultorios = [consultorio] if consultorio else []
    
    if not consultorio:
        messages.error(request, 'No tienes consultorio asignado.')
        return redirect_next(request, 'dashboard')
    
    # ✅ USAR LA MISMA LÓGICA QUE LISTA_CITAS
    citas = get_citas_queryset(user)
    
    # Filtrar por fecha y consultorio
    citas = citas.filter(
        fecha_hora__date=fecha,
        consultorio=consultorio
    )
    
    # Filtro por estado si se especifica
    estado_filtro = request.GET.get('estado')
    if estado_filtro:
        citas = citas.filter(estado=estado_filtro)
    
    # Ordenar por fecha
    citas = citas.order_by('fecha_hora')
    
    # ✅ ORGANIZAR POR TURNOS DE PACIENTES (no por horarios)
    turnos = {
        'sin_asignar': {
            'nombre': 'Sin Médico Asignado',
            'icono': 'person-x',
            'color': 'danger',
            'citas': citas.filter(medico_asignado__isnull=True)
        },
        'asignadas': {
            'nombre': 'Citas Asignadas',
            'icono': 'person-check',
            'color': 'primary',
            'citas': citas.filter(medico_asignado__isnull=False)
        },
        'en_espera': {
            'nombre': 'En Sala de Espera',
            'icono': 'clock',
            'color': 'warning',
            'citas': citas.filter(estado='en_espera')
        },
        'en_atencion': {
            'nombre': 'En Atención',
            'icono': 'person-gear',
            'color': 'info',
            'citas': citas.filter(estado='en_atencion')
        },
        'completadas': {
            'nombre': 'Completadas',
            'icono': 'check-circle',
            'color': 'success',
            'citas': citas.filter(estado='completada')
        }
    }
    
    # Calcular estadísticas
    stats = {
        'total': citas.count(),
        'sin_asignar': turnos['sin_asignar']['citas'].count(),
        'asignadas': turnos['asignadas']['citas'].count(),
        'en_espera': turnos['en_espera']['citas'].count(),
        'en_atencion': turnos['en_atencion']['citas'].count(),
        'completadas': turnos['completadas']['citas'].count(),
    }
    
    context = {
        'fecha': fecha,
        'consultorio': consultorio,
        'consultorios': consultorios,
        'turnos': turnos,
        'stats': stats,
        'usuario': user,
        'now': timezone.now(),
        'total_citas': citas.count(),
    }
    
    return render(request, 'PAGES/citas/cola_virtual.html', context)


@login_required
def cola_virtual_data(request):
    """Vista AJAX para actualizar datos de la cola virtual - USANDO LÓGICA DE LISTA_CITAS"""
    user = request.user
    
    try:
        # Obtener parámetros
        fecha_str = request.GET.get('fecha', timezone.now().date().strftime('%Y-%m-%d'))
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        consultorio_id = request.GET.get('consultorio')
        if user.rol == 'admin' and consultorio_id:
            consultorio = get_object_or_404(Consultorio, id=consultorio_id)
        else:
            consultorio = user.consultorio
        
        if not consultorio:
            return JsonResponse({'success': False, 'error': 'No hay consultorio asignado'})
        
        # ✅ USAR LA MISMA LÓGICA QUE LISTA_CITAS
        citas = get_citas_queryset(user)
        
        # Filtrar por fecha y consultorio
        citas = citas.filter(
            fecha_hora__date=fecha,
            consultorio=consultorio
        )
        
        # Filtro por estado
        estado_filtro = request.GET.get('estado')
        if estado_filtro:
            citas = citas.filter(estado=estado_filtro)
        
        # Ordenar por fecha
        citas = citas.order_by('fecha_hora')
        
        # ✅ ORGANIZAR POR TURNOS DE PACIENTES
        turnos = {
            'sin_asignar': {
                'nombre': 'Sin Médico Asignado',
                'icono': 'person-x',
                'color': 'danger',
                'citas': citas.filter(medico_asignado__isnull=True)
            },
            'asignadas': {
                'nombre': 'Citas Asignadas',
                'icono': 'person-check',
                'color': 'primary',
                'citas': citas.filter(medico_asignado__isnull=False)
            },
            'en_espera': {
                'nombre': 'En Sala de Espera',
                'icono': 'clock',
                'color': 'warning',
                'citas': citas.filter(estado='en_espera')
            },
            'en_atencion': {
                'nombre': 'En Atención',
                'icono': 'person-gear',
                'color': 'info',
                'citas': citas.filter(estado='en_atencion')
            },
            'completadas': {
                'nombre': 'Completadas',
                'icono': 'check-circle',
                'color': 'success',
                'citas': citas.filter(estado='completada')
            }
        }
        
        # Calcular estadísticas
        stats = {
            'total': citas.count(),
            'sin_asignar': turnos['sin_asignar']['citas'].count(),
            'asignadas': turnos['asignadas']['citas'].count(),
            'en_espera': turnos['en_espera']['citas'].count(),
            'en_atencion': turnos['en_atencion']['citas'].count(),
            'completadas': turnos['completadas']['citas'].count(),
        }
        
        # Renderizar HTML de los turnos
        html = render_to_string('PAGES/citas/partials/turnos_cola.html', {
            'turnos': turnos,
            'usuario': user,
        })
        
        return JsonResponse({
            'success': True,
            'html': html,
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ═══════════════════════════════════════════════════════════════
# 📅 CITAS - SISTEMA POR CONSULTORIO
# ═══════════════════════════════════════════════════════════════

def marcar_citas_vencidas():
    """Marca como no asistió las citas pasadas sin consulta y las cancela."""
    ahora = timezone.now()
    Cita.objects.filter(
        fecha_hora__lt=ahora,
        estado__in=["programada", "confirmada"],
        consulta__isnull=True,
    ).update(
        estado="no_asistio",
        fecha_cancelacion=ahora,
        motivo_cancelacion="No asistió",
    )

class CitaPermisoMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.rol in ('medico', 'asistente', 'admin')


@login_required
def lista_citas(request):
    """Lista de citas filtrada por consultorio del usuario"""
    marcar_citas_vencidas()
    user = request.user
    
    # ✅ USAR LA FUNCIÓN REUTILIZABLE
    citas = get_citas_queryset(user)
    
    # Aplicar filtros adicionales
    filtro_form = CitaFiltroForm(request.GET, user=user)
    if filtro_form.is_valid():
        cd = filtro_form.cleaned_data
        
        if cd.get('buscar'):
            citas = citas.filter(
                Q(paciente__nombre_completo__icontains=cd['buscar']) |
                Q(numero_cita__icontains=cd['buscar']) |
                Q(motivo__icontains=cd['buscar'])
            )
        
        if cd.get('fecha'):
            citas = citas.filter(fecha_hora__date=cd['fecha'])
        if cd.get('estado'):
            citas = citas.filter(estado=cd['estado'])
        if cd.get('medico'):
            citas = citas.filter(medico_asignado=cd['medico'])
        
    
    # Ordenar por fecha
    citas = citas.order_by('fecha_hora')
    
    # Estadísticas
    hoy = timezone.now().date()
    stats = {
        'total': citas.count(),
        'hoy': citas.filter(fecha_hora__date=hoy).count(),
        'sin_asignar': citas.filter(medico_asignado__isnull=True).count(),
        'asignadas': citas.filter(medico_asignado__isnull=False).count(),
        'completadas': citas.filter(estado='completada').count(),
        'vencidas': citas.filter(
            fecha_hora__lt=timezone.now(),
            estado__in=['programada', 'confirmada']
        ).count(),
    }
    
    # Agrupaciones para pestañas
    grupos = {
        'sin_asignar': citas.filter(
            medico_asignado__isnull=True,
            estado__in=['programada', 'confirmada', 'en_espera']
        ),
        'asignadas': citas.filter(
            medico_asignado__isnull=False,
            estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
        ),
        'completadas': citas.filter(estado='completada'),
        'canceladas': citas.filter(estado__in=['cancelada', 'no_asistio']),
    }
    
    # Paginación
    paginator = Paginator(citas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Permisos
    permisos = {
        'puede_tomar': user.rol == 'medico',
        'puede_asignar': user.rol in ['admin', 'asistente'],
        'puede_liberar': user.rol in ['admin', 'medico'],
        'puede_crear': True,
    }
    
    # Médicos disponibles para filtros
    if user.rol == 'admin':
        medicos_disponibles = Usuario.objects.filter(rol='medico', is_active=True)
    elif user.consultorio:
        medicos_disponibles = Usuario.objects.filter(
            rol='medico',
            consultorio=user.consultorio,
            is_active=True
        )
    else:
        medicos_disponibles = Usuario.objects.none()
    
    context = {
        'page_obj': page_obj,
        'filtro_form': filtro_form,
        'stats': stats,
        'grupos': grupos,
        'permisos': permisos,
        'medicos_disponibles': medicos_disponibles,
        'usuario': user,
        'hoy': hoy,
    }
    
    return render(request, 'PAGES/citas/lista.html', context)


@login_required
def crear_cita(request):
    """Crear nueva cita asignada a consultorio"""
    if request.user.rol not in ['medico', 'asistente', 'admin']:
        messages.error(request, 'No tienes permisos para crear citas.')

        return redirect_next(request, 'citas_lista')

    
    if request.method == 'POST':
        form = CitaForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                cita = form.save(commit=False)
                cita.creado_por = request.user
                
                # Asignar consultorio según el usuario
                if request.user.rol == 'asistente' and request.user.consultorio:
                    cita.consultorio = request.user.consultorio
                elif request.user.rol == 'medico' and request.user.consultorio:
                    cita.consultorio = request.user.consultorio
                
                # Validar conflictos de horario antes de guardar
                conflictos = validar_conflictos_horario(
                    cita.consultorio,
                    cita.fecha_hora,
                    cita.duracion,
                    excluir_cita_id=None
                )
                
                if conflictos:
                    form.add_error(None, f"Conflicto de horario detectado: {conflictos}")
                else:
                    cita.save()
                    messages.success(request, f'Cita {cita.numero_cita} creada exitosamente.')
                    
                    # Crear notificación para médicos del consultorio
                    crear_notificacion_nueva_cita(cita)
                    
                    return redirect_next(request, 'citas_lista')

                    
            except Exception as e:
                messages.error(request, f'Error al crear la cita: {str(e)}')
    else:
        form = CitaForm(user=request.user)
    
    context = {
        'form': form,
        'titulo': 'Nueva Cita',
        'accion': 'Crear',
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/crear.html', context)


@login_required
def detalle_cita(request, cita_id):
    """Detalle de una cita específica"""
    cita = get_object_or_404(Cita, id=cita_id)
    
    # Verificar permisos de visualización
    if not puede_ver_cita(request.user, cita):
        messages.error(request, 'No tienes permisos para ver esta cita.')

        return redirect_next(request, 'citas_lista')

    
    # Obtener médicos disponibles para asignación
    medicos_disponibles = []
    if cita.consultorio:
        medicos_disponibles = Usuario.objects.filter(
            rol='medico',
            consultorio=cita.consultorio,
            is_active=True
        ).order_by('first_name', 'last_name')
    
    # Verificar si hay consulta asociada
    consulta = None
    try:
        consulta = cita.consulta
    except Consulta.DoesNotExist:
        pass
    
    context = {
        'cita': cita,
        'consulta': consulta,
        'medicos_disponibles': medicos_disponibles,
        'puede_asignar_medico': (
            cita.puede_asignar_medico and
            request.user.rol == 'admin'
        ),
        'puede_tomar_cita': puede_tomar_cita(request.user, cita),
        'puede_editar': puede_editar_cita(request.user, cita),
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/detalle.html', context)


@login_required
def asignar_medico_cita(request, cita_id):
    """Asignar médico a una cita"""
    cita = get_object_or_404(Cita, id=cita_id)
    
    # Verificar permisos
    if request.user.rol not in ['admin', 'asistente']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'No tienes permisos para asignar médicos'}, status=403)
        messages.error(request, 'No tienes permisos para asignar médicos.')
        return redirect_next(request, 'detalle_cita', cita_id=cita.id)
    
    # Verificar que la cita puede tener médico asignado
    if not cita.puede_asignar_medico:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Esta cita ya tiene médico asignado o no se puede asignar'}, status=400)
        messages.error(request, 'Esta cita ya tiene médico asignado o no se puede asignar.')
        return redirect_next(request, 'detalle_cita', cita_id=cita.id)
    
    if request.method == 'POST':
        # Determinar si es una solicitud AJAX
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Para solicitudes AJAX desde la lista, el médico viene directamente en el POST
        if is_ajax and 'medico_id' in request.POST:
            try:
                medico_id = request.POST.get('medico_id')
                medico = get_object_or_404(Usuario, id=medico_id, rol='medico')
                observaciones = request.POST.get('observaciones', '')
                
                # Asignar médico
                cita.medico_asignado = medico
                cita.fecha_asignacion_medico = timezone.now()
                cita.estado = 'confirmada'
                cita.actualizado_por = request.user
                
                # Agregar observaciones si las hay
                if observaciones:
                    if cita.notas:
                        cita.notas += f"\n\nObservaciones de asignación: {observaciones}"
                    else:
                        cita.notas = f"Observaciones de asignación: {observaciones}"
                
                cita.save()
                
                # Si hay consulta asociada, también asignar el médico
                if hasattr(cita, 'consulta') and cita.consulta:
                    consulta = cita.consulta
                    consulta.medico = medico
                    consulta.save()
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Médico {medico.get_full_name()} asignado exitosamente.',
                    'medico_nombre': medico.get_full_name(),
                    'cita_id': str(cita.id)
                })
                
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)
        else:
            # Para solicitudes normales desde el formulario
            form = AsignarMedicoForm(request.POST, cita=cita, user=request.user)
            if form.is_valid():
                try:
                    medico = form.cleaned_data['medico']
                    observaciones = form.cleaned_data.get('observaciones', '')
                    
                    # Asignar médico
                    cita.medico_asignado = medico
                    cita.fecha_asignacion_medico = timezone.now()
                    cita.estado = 'confirmada'
                    cita.actualizado_por = request.user
                    
                    # Agregar observaciones si las hay
                    if observaciones:
                        if cita.notas:
                            cita.notas += f"\n\nObservaciones de asignación: {observaciones}"
                        else:
                            cita.notas = f"Observaciones de asignación: {observaciones}"
                    
                    cita.save()
                    
                    # Si hay consulta asociada, también asignar el médico
                    if hasattr(cita, 'consulta') and cita.consulta:
                        consulta = cita.consulta
                        consulta.medico = medico
                        consulta.save()
                    
                    messages.success(
                        request, 
                        f'Médico {medico.get_full_name()} asignado exitosamente a la cita {cita.numero_cita}.'
                    )
                    
                    return redirect_next(request, 'detalle_cita', cita_id=cita.id)
                    
                except Exception as e:
                    messages.error(request, f'Error al asignar médico: {str(e)}')
                    form.add_error(None, f'Error al asignar médico: {str(e)}')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'Error en {field}: {error}')
    else:
        form = AsignarMedicoForm(cita=cita, user=request.user)
    
    context = {
        'form': form,
        'cita': cita,
        'titulo': f'Asignar Médico - Cita {cita.numero_cita}',
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/asignar_medico.html', context)


@login_required
def tomar_cita(request, cita_id):
    """Permite a un médico tomar una cita disponible"""
    if request.user.rol != 'medico':
        messages.error(request, 'Solo los médicos pueden tomar citas.')

        return redirect_next(request, 'citas_lista')

    
    cita = get_object_or_404(Cita, id=cita_id)
    user = request.user
    
    # Verificaciones de seguridad
    if not puede_tomar_cita(user, cita):
        messages.error(request, 'No puedes tomar esta cita.')

        return redirect_next(request, 'citas_lista')

    
    # Verificar conflictos de horario del médico
    conflictos = Cita.objects.filter(
        medico_asignado=user,
        fecha_hora__date=cita.fecha_hora.date(),
        fecha_hora__time__range=[
            (cita.fecha_hora - timedelta(minutes=15)).time(),
            (cita.fecha_hora + timedelta(minutes=cita.duracion + 15)).time()
        ],
        estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
    ).exclude(id=cita.id)
    
    if conflictos.exists() and not request.POST.get('confirmar'):
        conflicto = conflictos.first()
        context = {
            'cita': cita,
            'conflicto': conflicto,
            'usuario': user,
        }
        return render(request, 'PAGES/citas/confirmar_tomar.html', context)
    
    if request.method == 'POST':
        try:
            # Asignar médico y cambiar estado
            cita.medico_asignado = user
            cita.fecha_asignacion_medico = timezone.now()
            cita.estado = 'confirmada'
            cita.actualizado_por = user
            cita.save()
            
            # Si hay consulta asociada, asignar médico también
            if hasattr(cita, 'consulta'):
                consulta = cita.consulta
                consulta.medico = user
                consulta.save()
            
            messages.success(
                request, 
                f'Has tomado exitosamente la cita de {cita.paciente.nombre_completo} '
                f'programada para {cita.fecha_hora.strftime("%d/%m/%Y a las %H:%M")}.'
            )
            
            return redirect_next(request, 'mis_citas_asignadas')
            
        except Exception as e:
            messages.error(request, f'Error al tomar la cita: {str(e)}')

            return redirect_next(request, 'citas_lista')

    
    # GET request - mostrar confirmación
    context = {
        'cita': cita,
        'usuario': user,
    }
    return render(request, 'PAGES/citas/tomar_cita.html', context)


@login_required
def liberar_cita(request, cita_id):
    """Permite liberar una cita asignada"""
    cita = get_object_or_404(Cita, id=cita_id)
    
    # Verificar permisos
    if not (request.user.rol == 'admin' or cita.medico_asignado == request.user):
        messages.error(request, 'No tienes permisos para liberar esta cita.')
        return redirect_next(request, 'detalle_cita', cita_id=cita.id)
    
    # Verificar que la cita se puede liberar
    if not cita.medico_asignado:
        messages.error(request, 'Esta cita no tiene médico asignado.')
        return redirect_next(request, 'detalle_cita', cita_id=cita.id)
    
    if cita.estado in ['completada', 'cancelada']:
        messages.error(request, 'No se puede liberar una cita completada o cancelada.')
        return redirect_next(request, 'detalle_cita', cita_id=cita.id)
    
    if request.method == 'POST':
        try:
            motivo = request.POST.get('motivo', '').strip()
            medico_anterior = cita.medico_asignado
            
            # Liberar la cita
            cita.medico_asignado = None
            cita.fecha_asignacion_medico = None
            cita.estado = 'programada'
            cita.motivo_cancelacion = motivo
            cita.actualizado_por = request.user
            cita.save()
            
            # Si hay consulta asociada, también liberarla
            if hasattr(cita, 'consulta') and cita.consulta:
                consulta = cita.consulta
                if consulta.estado in ['espera', 'en_progreso']:
                    consulta.medico = None
                    consulta.estado = 'espera'
                    consulta.save()
            
            # Crear notificación para otros médicos del consultorio
            crear_notificacion_cita_liberada(cita, medico_anterior)
            
            messages.success(
                request, 
                f'Cita {cita.numero_cita} liberada exitosamente. '
                f'Ahora está disponible para otros médicos del {cita.consultorio.nombre}.'
            )
            
            return redirect_next(request, 'detalle_cita', cita_id=cita.id)
            
        except Exception as e:
            messages.error(request, f'Error al liberar la cita: {str(e)}')
    
    context = {
        'cita': cita,
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/liberar_cita.html', context)


@login_required
def citas_disponibles(request):
    """Vista de citas disponibles para que médicos puedan tomar"""
    user = request.user
    
    # Solo médicos pueden acceder, admin puede ver todas
    if user.rol not in ['medico', 'admin']:
        messages.error(request, 'Solo los médicos pueden ver citas disponibles.')
        return redirect_next(request, 'dashboard')
    
    # Filtrar citas según rol
    if user.rol == 'admin':
        citas_base = Cita.objects.all()
    elif user.consultorio:
        citas_base = Cita.objects.filter(consultorio=user.consultorio)
    else:
        messages.error(request, 'No tienes consultorio asignado.')
        return redirect_next(request, 'dashboard')
    
    # Filtrar citas sin médico asignado
    citas_disponibles = citas_base.filter(
        medico_asignado__isnull=True,
        estado__in=['programada', 'confirmada', 'en_espera'],
        fecha_hora__gte=timezone.now() - timedelta(hours=1)
    )
    
    # Aplicar filtros
    fecha_filtro = request.GET.get('fecha')
    tipo_filtro = request.GET.get('tipo_cita')
    prioridad_filtro = request.GET.get('prioridad')
    consultorio_filtro = request.GET.get('consultorio')
    
    if fecha_filtro:
        try:
            fecha = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
            citas_disponibles = citas_disponibles.filter(fecha_hora__date=fecha)
        except ValueError:
            pass
    
    if tipo_filtro:
        citas_disponibles = citas_disponibles.filter(tipo_cita=tipo_filtro)
    
    if prioridad_filtro:
        citas_disponibles = citas_disponibles.filter(prioridad=prioridad_filtro)
    
    if consultorio_filtro and user.rol == 'admin':
        citas_disponibles = citas_disponibles.filter(consultorio_id=consultorio_filtro)
    
    # Ordenar por prioridad y fecha
    citas_disponibles = citas_disponibles.select_related(
        'paciente', 'consultorio', 'medico_preferido'
    ).order_by('fecha_hora', '-prioridad')
    
    # Agrupar por urgencia
    ahora = timezone.now()
    grupos = {
        'urgentes': citas_disponibles.filter(
            Q(prioridad='urgente') | 
            Q(fecha_hora__lte=ahora + timedelta(hours=1))
        ),
        'hoy': citas_disponibles.filter(fecha_hora__date=ahora.date()),
        'proximas': citas_disponibles.filter(fecha_hora__date__gt=ahora.date()),
    }
    
    # Estadísticas
    stats = {
        'total_disponibles': citas_disponibles.count(),
        'urgentes': grupos['urgentes'].count(),
        'hoy': grupos['hoy'].count(),
        'esta_semana': citas_disponibles.filter(
            fecha_hora__date__range=[
                ahora.date(),
                ahora.date() + timedelta(days=7)
            ]
        ).count(),
    }
    
    context = {
        'citas_disponibles': citas_disponibles,
        'grupos': grupos,
        'stats': stats,
        'filtros': {
            'fecha': fecha_filtro,
            'tipo_cita': tipo_filtro,
            'prioridad': prioridad_filtro,
            'consultorio': consultorio_filtro,
        },
        'tipos_cita': Cita.TIPO_CITA_CHOICES,
        'prioridades': Cita.PRIORIDAD_CHOICES,
        'consultorios': Consultorio.objects.all() if user.rol == 'admin' else [user.consultorio],
        'usuario': user,
        'puede_tomar': user.rol == 'medico',
    }
    
    return render(request, 'PAGES/citas/disponibles.html', context)


@login_required
def mis_citas_asignadas(request):
    """Citas asignadas al médico actual"""
    if request.user.rol != 'medico':
        messages.error(request, 'Solo los médicos pueden ver sus citas asignadas.')
        return redirect_next(request, 'dashboard')
    
    citas = Cita.objects.filter(
        medico_asignado=request.user
    ).select_related('paciente', 'consultorio').order_by('fecha_hora')
    
    # Aplicar filtros
    estado_filtro = request.GET.get('estado')
    if estado_filtro:
        citas = citas.filter(estado=estado_filtro)
    
    fecha_filtro = request.GET.get('fecha')
    if fecha_filtro:
        try:
            fecha = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
            citas = citas.filter(fecha_hora__date=fecha)
        except ValueError:
            pass
    
    # Estadísticas
    ahora = timezone.now()
    stats = {
        'total': citas.count(),
        'hoy': citas.filter(fecha_hora__date=ahora.date()).count(),
        'pendientes': citas.filter(estado__in=['programada', 'confirmada']).count(),
        'en_atencion': citas.filter(estado='en_atencion').count(),
        'completadas': citas.filter(estado='completada').count(),
        'esta_semana': citas.filter(
            fecha_hora__date__range=[
                ahora.date(),
                ahora.date() + timedelta(days=7)
            ]
        ).count(),
    }
    
    context = {
        'citas': citas,
        'stats': stats,
        'estado_filtro': estado_filtro,
        'fecha_filtro': fecha_filtro,
        'today': ahora.date(),
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/mis_citas.html', context)


@login_required
def cambiar_estado_cita(request, pk):
    """Vista AJAX para cambiar el estado de una cita"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    
    try:
        cita = get_object_or_404(Cita, id=pk)
        
        # Verificar permisos
        if not puede_editar_cita(request.user, cita):
            return JsonResponse({'success': False, 'message': 'Sin permisos para editar esta cita'}, status=403)
        
        nuevo_estado = request.POST.get('estado')
        motivo = request.POST.get('motivo', '')
        
        if nuevo_estado not in dict(Cita.ESTADO_CHOICES):
            return JsonResponse({'success': False, 'message': 'Estado inválido'}, status=400)
        
        # Cambiar estado
        estado_anterior = cita.estado
        cita.estado = nuevo_estado
        
        if motivo:
            cita.motivo_cancelacion = motivo
        
        if nuevo_estado == 'cancelada':
            cita.fecha_cancelacion = timezone.now()
        elif nuevo_estado == 'confirmada':
            cita.fecha_confirmacion = timezone.now()
        
        cita.actualizado_por = request.user
        cita.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Estado cambiado de {estado_anterior} a {nuevo_estado}',
            'nuevo_estado': cita.get_estado_display()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════
# 🔧 FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def puede_ver_cita(user, cita):
    """Verifica si el usuario puede ver la cita"""
    if user.rol == 'admin':
        return True
    elif user.rol == 'medico':
        return (cita.consultorio == user.consultorio or 
                cita.medico_asignado == user)
    elif user.rol == 'asistente':
        return cita.consultorio == user.consultorio
    return False


def puede_editar_cita(user, cita):
    """Verifica si el usuario puede editar la cita"""
    if user.rol == 'admin':
        return True
    elif user.rol == 'medico':
        return (
            cita.medico_asignado == user
            and cita.estado in ['programada', 'confirmada']
        )
    return False


def puede_tomar_cita(user, cita):
    """Verifica si el médico puede tomar la cita"""
    return (user.rol == 'medico' and 
            user.consultorio == cita.consultorio and
            not cita.medico_asignado and
            cita.estado in ['programada', 'confirmada'])


def get_color_by_estado(estado):
    """Retorna color para el calendario según el estado"""
    colors = {
        'programada': '#6c757d',      # Gris
        'confirmada': '#0d6efd',      # Azul
        'en_espera': '#ffc107',       # Amarillo
        'en_atencion': '#fd7e14',     # Naranja
        'completada': '#198754',      # Verde
        'cancelada': '#dc3545',       # Rojo
        'no_asistio': '#6f42c1',      # Púrpura
        'reprogramada': '#20c997',    # Teal
    }
    return colors.get(estado, '#6c757d')


def validar_conflictos_horario(consultorio, fecha_hora, duracion, excluir_cita_id=None):
    """Valida si hay conflictos de horario para una cita"""
    try:
        inicio_cita = fecha_hora
        fin_cita = fecha_hora + timedelta(minutes=duracion)
        
        # Buscar citas que se solapen en el mismo consultorio
        citas_existentes = Cita.objects.filter(
            consultorio=consultorio,
            fecha_hora__date=fecha_hora.date(),
            estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
        )
        
        if excluir_cita_id:
            citas_existentes = citas_existentes.exclude(id=excluir_cita_id)
        
        for cita_existente in citas_existentes:
            inicio_existente = cita_existente.fecha_hora
            fin_existente = cita_existente.fecha_hora + timedelta(minutes=cita_existente.duracion)
            
            # Verificar solapamiento
            if (inicio_cita < fin_existente and fin_cita > inicio_existente):
                return f"Se solapa con cita de {cita_existente.paciente.nombre_completo} de {inicio_existente.strftime('%H:%M')} a {fin_existente.strftime('%H:%M')}"
        
        return None
        
    except Exception as e:
        return f"Error al validar conflictos: {str(e)}"


def crear_notificacion_nueva_cita(cita):
    """Crea notificación para médicos del consultorio sobre nueva cita"""
    try:
        medicos = Usuario.objects.filter(
            rol='medico',
            consultorio=cita.consultorio,
            is_active=True
        )
        
        for medico in medicos:
            Notificacion.objects.create(
                destinatario=medico,
                titulo="Nueva cita disponible",
                mensaje=f"Nueva cita disponible: {cita.paciente.nombre_completo} - {cita.fecha_hora.strftime('%d/%m/%Y %H:%M')}",
                tipo="info",
                categoria="cita_creada",
                content_type_id=None,
                object_id=str(cita.id)
            )
    except Exception as e:
        print(f"Error al crear notificación nueva cita: {str(e)}")


def crear_notificacion_cita_liberada(cita, medico_anterior):
    """Crea notificación cuando se libera una cita"""
    try:
        medicos = Usuario.objects.filter(
            rol='medico',
            consultorio=cita.consultorio,
            is_active=True
        ).exclude(id=medico_anterior.id)
        
        for medico in medicos:
            Notificacion.objects.create(
                destinatario=medico,
                titulo="Cita liberada",
                mensaje=f"Cita liberada disponible: {cita.paciente.nombre_completo} - {cita.fecha_hora.strftime('%d/%m/%Y %H:%M')}",
                tipo="warning",
                categoria="cita_creada",
                content_type_id=None,
                object_id=str(cita.id)
            )
    except Exception as e:
        print(f"Error al crear notificación cita liberada: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# 🏥 CONSULTAS
# ═══════════════════════════════════════════════════════════════

class ConsultaPermisoMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.rol == "admin":
            return True

        if user.rol == "medico":
            consulta_id = (
                self.kwargs.get("pk")
                or self.kwargs.get("consulta_id")
                or self.request.POST.get("consulta_id")
            )
            if consulta_id:
                consulta = get_object_or_404(Consulta, pk=consulta_id)
                return consulta.medico == user
        return False


class ConsultaListView(LoginRequiredMixin, ListView):
    """Lista de consultas filtrada por consultorio con indicación de origen"""
    model = Consulta
    template_name = "PAGES/consultas/lista.html"
    context_object_name = "consultas"
    paginate_by = 50

    def get_queryset(self):
        user = self.request.user

        qs = Consulta.objects.select_related(
            "paciente", "medico", "cita", "cita__consultorio"
        ).order_by("-fecha_creacion")

        if user.rol == 'admin':
            pass
        elif user.consultorio:
            qs = qs.filter(
                Q(medico__consultorio=user.consultorio) |
                Q(cita__consultorio=user.consultorio) |
                Q(asistente__consultorio=user.consultorio)
            )
        elif user.rol == 'medico':
            qs = qs.filter(medico=user)
        else:
            qs = qs.none()

        filtro_form = ConsultaFiltroForm(self.request.GET, user=user)
        if filtro_form.is_valid():
            cd = filtro_form.cleaned_data

            if cd.get("buscar"):
                qs = qs.filter(paciente__nombre_completo__icontains=cd["buscar"])

            if cd.get("fecha"):
                qs = qs.filter(fecha_creacion__date=cd["fecha"])

            if cd.get("estado"):
                qs = qs.filter(estado=cd["estado"])

            if cd.get("medico"):
                qs = qs.filter(medico=cd["medico"])

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        usuario = self.request.user
        consultas = self.get_queryset()

        # 2. Mostrar consultas con y sin cita / 3. Indicar origen
        consultas_con_cita = consultas.filter(cita__isnull=False)
        consultas_sin_cita = consultas.filter(cita__isnull=True)

        # Estadísticas por estado
        ctx["stats"] = {
            "pendientes": consultas.filter(estado="espera").count(),
            "en_progreso": consultas.filter(estado="en_progreso").count(),
            "finalizadas": consultas.filter(estado="finalizada").count(),
            "canceladas": consultas.filter(estado="cancelada").count(),
            "total": consultas.count(),
            "con_cita": consultas_con_cita.count(),
            "sin_cita": consultas_sin_cita.count(),
        }

        # Agrupaciones para pestañas
        ctx.update({
            "consultas_pendientes": consultas.filter(estado="espera"),
            "consultas_en_progreso": consultas.filter(estado="en_progreso"),
            "consultas_finalizadas": consultas.filter(estado="finalizada"),
            "consultas_canceladas": consultas.filter(estado="cancelada"),
            "consultas_con_cita": consultas_con_cita,
            "consultas_sin_cita": consultas_sin_cita,
        })

        # Médicos con consulta en progreso para ocultar botón "Atender"
        medicos_ocupados = set(
            consultas.filter(estado="en_progreso", medico__isnull=False)
            .values_list("medico_id", flat=True)
        )
        for con in consultas:
            con.medico_en_otro_progreso = (
                con.medico_id in medicos_ocupados and con.estado != "en_progreso"
            )

        # Médicos disponibles para filtros
        if usuario.consultorio and usuario.rol != "admin":
            medicos = Usuario.objects.filter(
                rol="medico",
                consultorio=usuario.consultorio,
                is_active=True
            ).order_by("first_name", "last_name")
        else:
            medicos = Usuario.objects.filter(
                rol="medico", 
                is_active=True
            ).order_by("first_name", "last_name")

        ctx.update({
            "medicos": medicos,
            "usuario": usuario,
            "consultorio": getattr(usuario, "consultorio", None),
            "filtro_form": ConsultaFiltroForm(self.request.GET, user=usuario),
            # 4. Permitir crear consultas sin cita
            "puede_crear_sin_cita": usuario.rol in ['medico', 'asistente', 'admin'],
        })
        
        return ctx


# ═══════════════════════════════════════════════════════════════
# 📤 EXPORTACIÓN Y REPORTES
# ═══════════════════════════════════════════════════════════════

@login_required
def exportar_citas_csv(request):
    """Exportar citas a CSV"""
    try:
        user = request.user
        
        # Filtrar citas según rol
        if user.rol == 'admin':
            citas = Cita.objects.all()
        elif user.rol == 'medico':
            citas = Cita.objects.filter(
                Q(consultorio=user.consultorio) | Q(medico_asignado=user)
            )
        elif user.rol == 'asistente':
            citas = Cita.objects.filter(consultorio=user.consultorio)
        else:
            citas = Cita.objects.none()
        
        # Aplicar filtros de fecha si existen
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')
        
        if fecha_desde:
            try:
                fecha = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                citas = citas.filter(fecha_hora__date__gte=fecha)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                citas = citas.filter(fecha_hora__date__lte=fecha)
            except ValueError:
                pass
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="citas_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Número Cita', 'Paciente', 'Consultorio', 'Médico Asignado', 'Médico Preferido',
            'Fecha y Hora', 'Duración', 'Estado', 'Tipo', 'Prioridad', 'Motivo'
        ])
        
        for cita in citas.select_related('paciente', 'consultorio', 'medico_asignado', 'medico_preferido'):
            writer.writerow([
                cita.numero_cita,
                cita.paciente.nombre_completo,
                cita.consultorio.nombre if cita.consultorio else '',
                cita.medico_asignado.get_full_name() if cita.medico_asignado else 'Sin asignar',
                cita.medico_preferido.get_full_name() if cita.medico_preferido else '',
                cita.fecha_hora.strftime('%d/%m/%Y %H:%M'),
                f"{cita.duracion} min",
                cita.get_estado_display(),
                cita.get_tipo_cita_display(),
                cita.get_prioridad_display(),
                cita.motivo or ''
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al exportar: {str(e)}')

        return redirect_next(request, 'citas_lista')



# ═══════════════════════════════════════════════════════════════
# 🔔 API VIEWS
# ═══════════════════════════════════════════════════════════════

class LoginAPI(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if "token" not in response.data:
            return response       

        token = Token.objects.get(key=response.data["token"])
        user  = token.user

        if user.rol in ("medico", "asistente") and user.consultorio is None:
            token.delete()          
            return Response(
                {"error": "Cuenta aún no dada de alta; falta asignar consultorio."},
                status=403
            )

        return Response({
            "token": token.key,
            "user":  UsuarioSerializer(user).data
        })


@login_required
def ajax_cita_detalle(request, cita_id):
    """Vista AJAX para obtener detalles de una cita"""
    try:
        cita = get_object_or_404(Cita, pk=cita_id)
        
        # Verificar permisos
        if request.user.rol in ("medico", "asistente") and request.user.consultorio:
            if cita.consultorio != request.user.consultorio:
                return JsonResponse({'success': False, 'error': 'Sin permisos'})
        
        consulta = getattr(cita, 'consulta', None)
        
        data = {
            'success': True,
            'cita': {
                'id': cita.id,
                'paciente': {
                    'nombre': cita.paciente.nombre_completo,
                    'edad': cita.paciente.edad,
                    'telefono': cita.paciente.telefono,
                    'correo': cita.paciente.correo,
                },
                'fecha': cita.fecha_hora.strftime('%d/%m/%Y'),
                'hora': cita.fecha_hora.strftime('%H:%M'),
                'medico': cita.medico_asignado.get_full_name() if cita.medico_asignado else 'Sin asignar',
                'consultorio': cita.consultorio.nombre if cita.consultorio else 'Sin asignar',
                'duracion': cita.duracion,
                'motivo': cita.motivo,
                'notas': cita.notas,
                'estado': cita.estado,
                'estado_display': cita.get_estado_display(),
                'consulta': {
                    'id': consulta.id,
                    'estado': consulta.estado
                } if consulta else None,
                'puede_editar': request.user.rol in ('admin', 'medico', 'asistente')
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def generar_pdf(template_path, context):
    template = get_template(template_path)
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    return response

# ═══════════════════════════════════════════════════════════════
# 📅 COLA VIRTUAL - CITAS PRÓXIMAS CON DISEÑO PROFESIONAL
# ═══════════════════════════════════════════════════════════════

def get_citas_queryset(user):
    """Función reutilizable para obtener citas según el rol del usuario"""
    if user.rol == 'admin':
        citas = Cita.objects.all()
    elif user.rol == 'medico':
        citas = Cita.objects.filter(
            Q(consultorio=user.consultorio) | Q(medico_asignado=user)
        )
    elif user.rol == 'asistente':
        if user.consultorio:
            citas = Cita.objects.filter(consultorio=user.consultorio)
        else:
            citas = Cita.objects.none()
    else:
        citas = Cita.objects.none()
    
    return citas.select_related('paciente', 'consultorio', 'medico_asignado', 'medico_preferido')


@login_required
def cola_virtual(request):
    """Vista principal de la cola virtual - SOLO CITAS PRÓXIMAS"""
    user = request.user
    
    # Verificar permisos
    if user.rol not in ['medico', 'asistente', 'admin']:
        messages.error(request, 'No tienes permisos para acceder a la cola virtual.')
        return redirect_next(request, 'dashboard')
    
    # Obtener fecha (por defecto hoy)
    fecha_str = request.GET.get('fecha', timezone.now().date().strftime('%Y-%m-%d'))
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha = timezone.now().date()
    
    # Obtener consultorio
    consultorio_id = request.GET.get('consultorio')
    if user.rol == 'admin':
        if consultorio_id:
            consultorio = get_object_or_404(Consultorio, id=consultorio_id)
        else:
            consultorio = Consultorio.objects.first()
        consultorios = Consultorio.objects.all()
    else:
        consultorio = user.consultorio
        consultorios = [consultorio] if consultorio else []
    
    if not consultorio:
        messages.error(request, 'No tienes consultorio asignado.')
        return redirect_next(request, 'dashboard')
    
    # Consultas en espera (con y sin cita)
    consultas = (
        Consulta.objects
        .filter(estado='espera')
        .select_related('paciente', 'medico')
        .order_by('fecha_creacion')
    )

    # ✅ OBTENER SOLO CITAS PRÓXIMAS - APLICAR TODOS LOS FILTROS ANTES DEL SLICE
    ahora = timezone.now()
    citas = get_citas_queryset(user)

    # Aplicar filtros base
    citas_proximas = citas.filter(
        consultorio=consultorio,
        fecha_hora__gte=ahora,  # Solo citas futuras
        estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']  # Solo estados activos
    )
    
    # ✅ Filtro por estado ANTES del slice
    estado_filtro = request.GET.get('estado')
    if estado_filtro:
        citas_proximas = citas_proximas.filter(estado=estado_filtro)
    
    # ✅ Ordenar y aplicar slice AL FINAL
    citas_proximas = citas_proximas.order_by('fecha_hora')[:20]  # Limitar a 20 citas próximas
    
    # Calcular estadísticas (sin slice para contar correctamente)
    citas_stats = citas.filter(
        consultorio=consultorio,
        fecha_hora__gte=ahora,
        estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
    )
    
    if estado_filtro:
        citas_stats = citas_stats.filter(estado=estado_filtro)
    
    stats = {
        'total': citas_stats.count(),
        'sin_asignar': citas_stats.filter(medico_asignado__isnull=True).count(),
        'asignadas': citas_stats.filter(medico_asignado__isnull=False).count(),
        'en_espera': citas_stats.filter(estado='en_espera').count(),
        'en_atencion': citas_stats.filter(estado='en_atencion').count(),
        'completadas': citas_stats.filter(estado='completada').count(),
    }
    
    context = {
        'fecha': fecha,
        'consultorio': consultorio,
        'consultorios': consultorios,
        'consultas': consultas,
        'citas_proximas': citas_proximas,  # ✅ Solo citas próximas
        'stats': stats,
        'usuario': user,
        'now': timezone.now(),
        'total_citas': len(citas_proximas),  # Usar len() porque ya es una lista
    }
    
    return render(request, 'PAGES/citas/cola_virtual.html', context)


@login_required
def cola_virtual_data(request):
    """Vista AJAX para actualizar datos de la cola virtual"""
    user = request.user
    
    try:
        # Obtener parámetros
        fecha_str = request.GET.get('fecha', timezone.now().date().strftime('%Y-%m-%d'))
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        consultorio_id = request.GET.get('consultorio')
        if user.rol == 'admin' and consultorio_id:
            consultorio = get_object_or_404(Consultorio, id=consultorio_id)
        else:
            consultorio = user.consultorio
        
        if not consultorio:
            return JsonResponse({'success': False, 'error': 'No hay consultorio asignado'})
        
        # Consultas en espera (con y sin cita)
        consultas = (
            Consulta.objects
            .filter(estado='espera')
            .select_related('paciente', 'medico')
            .order_by('fecha_creacion')
        )

        # ✅ OBTENER SOLO CITAS PRÓXIMAS - APLICAR TODOS LOS FILTROS ANTES DEL SLICE
        ahora = timezone.now()
        citas = get_citas_queryset(user)
        
        # Aplicar filtros base
        citas_proximas = citas.filter(
            consultorio=consultorio,
            fecha_hora__gte=ahora,  # Solo citas futuras
            estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']  # Solo estados activos
        )
        
        # ✅ Filtro por estado ANTES del slice
        estado_filtro = request.GET.get('estado')
        if estado_filtro:
            citas_proximas = citas_proximas.filter(estado=estado_filtro)
        
        # ✅ Ordenar y aplicar slice AL FINAL
        citas_proximas = citas_proximas.order_by('fecha_hora')[:20]  # Limitar a 20 citas próximas
        
        # Calcular estadísticas (sin slice para contar correctamente)
        citas_stats = citas.filter(
            consultorio=consultorio,
            fecha_hora__gte=ahora,
            estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
        )
        
        if estado_filtro:
            citas_stats = citas_stats.filter(estado=estado_filtro)
        
        stats = {
            'total': citas_stats.count(),
            'sin_asignar': citas_stats.filter(medico_asignado__isnull=True).count(),
            'asignadas': citas_stats.filter(medico_asignado__isnull=False).count(),
            'en_espera': citas_stats.filter(estado='en_espera').count(),
            'en_atencion': citas_stats.filter(estado='en_atencion').count(),
            'completadas': citas_stats.filter(estado='completada').count(),
        }
        
        # Renderizar HTML de las citas próximas
        html = render_to_string('PAGES/citas/partials/turnos_cola.html', {
            'citas_proximas': citas_proximas,
            'consultas': consultas,
            'usuario': user,
        })
        
        return JsonResponse({
            'success': True,
            'html': html,
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



# ═══════════════════════════════════════════════════════════════
# 🏥 VISTAS DE CONSULTAS FALTANTES
# ═══════════════════════════════════════════════════════════════

class ConsultaDetailView(LoginRequiredMixin, DetailView):
    """Vista para mostrar el detalle de una consulta"""
    model = Consulta
    template_name = 'PAGES/consultas/detalle.html'
    context_object_name = 'consulta'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consulta = self.get_object()
        
        context.update({
            'usuario': self.request.user,
            'signos_vitales': getattr(consulta, 'signos_vitales', None),
            'receta': getattr(consulta, 'receta', None),
            'cita': consulta.cita,
            'puede_editar': self.request.user == consulta.medico or self.request.user.rol == 'admin',
        })
        
        return context


class ConsultaDeleteView(NextRedirectMixin, LoginRequiredMixin, ConsultaPermisoMixin, DeleteView):
    model = Consulta
    template_name = 'PAGES/consultas/eliminar.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol == 'asistente':
            messages.warning(request, 'No tienes permiso para eliminar consultas.')
            return redirect('consultas_lista')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        next_url = self.request.GET.get("next")
        if next_url:
            return next_url
        return reverse('paciente_detalle', args=[self.object.paciente.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['usuario'] = self.request.user
        ctx['next'] = self.request.GET.get("next", self.request.META.get("HTTP_REFERER", ""))
        return ctx
    
    
  
class ConsultaSinCitaCreateView(NextRedirectMixin, LoginRequiredMixin, CreateView):
    """Vista para crear consulta sin cita previa - CORREGIDA PARA NO ASIGNAR CITAS"""
    model = Consulta
    form_class = ConsultaSinCitaForm
    template_name = 'PAGES/consultas/crear_sin_cita.html'
    success_url = reverse_lazy('consultas_lista')

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol == 'asistente':
            messages.warning(request, 'No tienes permiso para crear consultas.')
            return redirect('consultas_lista')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        consulta = form.save(commit=False)

        paciente = form.cleaned_data.get("paciente")
        if paciente:
            estados = ["espera", "en_progreso"]
            if Consulta.objects.filter(
                paciente=paciente,
                tipo="sin_cita",
                estado__in=estados,
            ).exists():
                form.add_error(
                    None,
                    "Este paciente ya tiene una consulta activa. "
                    "No se puede crear otra hasta que finalice."
                )
                return self.form_invalid(form)
        
        # ✅ CONFIGURACIÓN BÁSICA - SIN CITA
        consulta.tipo = 'sin_cita'
        consulta.cita = None  # IMPORTANTE: Asegurar que NO tenga cita
        consulta.fecha_creacion = timezone.now()
        
        # ✅ DETERMINAR SI ES INSTANTÁNEA O PROGRAMADA
        programar_para = form.cleaned_data.get('programar_para', 'ahora')
        
        if form.es_consulta_instantanea():
            # CONSULTA INSTANTÁNEA - Sin validaciones de horario
            consulta.estado = 'espera'  # Lista para atender ahora
            consulta.fecha_atencion = None  # Se asignará cuando inicie
            mensaje_tipo = "instantánea"
            
        else:
            # CONSULTA PROGRAMADA - Con fecha/hora específica
            consulta.estado = 'espera'  # Programada para más tarde
            fecha_hora_programada = form.get_fecha_hora_cita()
            
            # Guardar la fecha/hora programada en observaciones o campo personalizado
            if consulta.observaciones:
                consulta.observaciones += f"\n\nProgramada para: {fecha_hora_programada.strftime('%d/%m/%Y a las %H:%M')}"
            else:
                consulta.observaciones = f"Consulta programada para: {fecha_hora_programada.strftime('%d/%m/%Y a las %H:%M')}"
            
            mensaje_tipo = f"programada para {fecha_hora_programada.strftime('%d/%m/%Y a las %H:%M')}"
        
        # ✅ ASIGNACIÓN DE ROLES
        if user.rol == 'asistente':
            consulta.asistente = user
        
        # ✅ ASIGNACIÓN AUTOMÁTICA DE MÉDICO SEGÚN ROL
        if user.rol == 'medico':
            # Si el usuario es médico, asignarlo automáticamente
            consulta.medico = user
            if form.es_consulta_instantanea():
                messages.success(
                    self.request, 
                    f'Te has asignado automáticamente a esta consulta {mensaje_tipo}. '
                    f'Puedes comenzar la atención inmediatamente.'
                )
            else:
                messages.success(
                    self.request, 
                    f'Te has asignado automáticamente a esta consulta {mensaje_tipo}.'
                )
        elif user.rol == 'admin':
            # Admin puede seleccionar médico en el formulario
            if consulta.medico:
                messages.success(
                    self.request, 
                    f'Médico {consulta.medico.get_full_name()} asignado a la consulta {mensaje_tipo}.'
                )
            else:
                messages.info(
                    self.request, 
                    f'Consulta {mensaje_tipo} creada sin médico asignado.'
                )
        elif user.rol == 'asistente':
            # Asistente puede seleccionar médico o dejarlo sin asignar
            if consulta.medico:
                messages.success(
                    self.request, 
                    f'Médico {consulta.medico.get_full_name()} asignado a la consulta {mensaje_tipo}.'
                )
            else:
                messages.info(
                    self.request, 
                    f'Consulta {mensaje_tipo} creada sin médico asignado. '
                    f'Podrá ser asignado posteriormente.'
                )
        
        # ✅ GUARDAR LA CONSULTA
        consulta.save()
        self.object = consulta
        
        # ✅ MENSAJE DE ÉXITO FINAL
        if form.es_consulta_instantanea():
            messages.success(
                self.request, 
                f'✅ Consulta instantánea creada exitosamente para {consulta.paciente.nombre_completo}. '
                f'Estado: {consulta.get_estado_display()}. Lista para atención inmediata.'
            )
        else:
            messages.success(
                self.request, 
                f'✅ Consulta {mensaje_tipo} creada exitosamente para {consulta.paciente.nombre_completo}. '
                f'No hay conflictos de horario.'
            )
        
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        context['titulo'] = 'Crear Consulta Sin Cita'
        context['next'] = self.request.GET.get('next') or self.request.POST.get('next', self.success_url)
        return context



class ConsultaPrecheckView(NextRedirectMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Crea o edita los signos vitales de una consulta"""
    model = SignosVitales
    form_class = SignosVitalesForm
    template_name = "PAGES/consultas/precheck.html"
    success_url = reverse_lazy("consultas_lista")

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.rol == "admin":
            return True
        if user.rol == "medico":
            consulta_id = self.kwargs.get("pk")
            if consulta_id:
                consulta = get_object_or_404(Consulta, pk=consulta_id)
                return consulta.medico == user
        return False

    def dispatch(self, request, *args, **kwargs):
        self.consulta = get_object_or_404(Consulta, pk=kwargs["pk"])

        if request.user.rol == "medico" and self.consulta.medico != request.user:
            messages.error(request, "No puedes editar esta consulta, no est\u00e1s asignado.")
            return redirect("consulta_detalle", pk=self.consulta.pk)
        if request.user.rol not in ("medico", "admin"):
            return redirect("consultas_lista")


        if hasattr(self.consulta, "signos_vitales"):
            self.object = self.consulta.signos_vitales
            self.__class__ = type(
                "ConsultaPrecheckUpdateView",
                (LoginRequiredMixin, UserPassesTestMixin, UpdateView),
                dict(self.__class__.__dict__),
            )

        consulta_pk = kwargs.get("pk")
        self.next_url = (
            request.POST.get("next")
            or request.GET.get("next")
            or reverse("consulta_detalle", args=[consulta_pk])
        )

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        ctx["consulta"] = self.consulta
        ctx["next"] = self.next_url
        return ctx

    def post(self, request, pk):
        consulta = get_object_or_404(Consulta, pk=pk)
        signos, _ = SignosVitales.objects.get_or_create(consulta=consulta)

        # asignar quién los registra
        signos.registrado_por = request.user

        form = SignosVitalesForm(request.POST, instance=signos)
        if form.is_valid():
            form.save()  # guarda también registrado_por
            messages.success(request, "Signos vitales guardados correctamente.")
            return redirect(self.get_next_url() or reverse("consulta_detalle", args=[pk]))

        return render(request, self.template_name, {
            "form": form,
            "usuario": request.user,
            "consulta": consulta,
            "next": self.get_next_url() or reverse("consulta_detalle", args=[pk]),
        })

    def form_valid(self, form):
        form.instance.consulta = self.consulta
        form.save()
        messages.success(self.request, "Signos vitales guardados correctamente.")
        return redirect(self.next_url)


class ConsultaAtencionView(LoginRequiredMixin, View):
    """El médico atiende: iniciar, guardar, finalizar y recetar"""
    template_name = "PAGES/consultas/atencion.html"

    def dispatch(self, request, *args, **kwargs):
        consulta_pk = kwargs.get("pk")
        self.consulta = get_object_or_404(Consulta, pk=consulta_pk)

        if request.user.rol == "medico" and self.consulta.medico != request.user:
            messages.error(request, "No puedes editar esta consulta, no est\u00e1s asignado.")
            return redirect("consulta_detalle", pk=consulta_pk)

        if request.user.rol not in ("medico", "admin"):
            return redirect("citas_lista")

        self.next_url = (
            request.POST.get("next")
            or request.GET.get("next")
            or reverse("consulta_detalle", args=[consulta_pk])
        )
        return super().dispatch(request, *args, **kwargs)

    def _setup_forms(self, consulta, post_data=None):
        """Construye los formularios para la atención de consulta."""
        receta = getattr(consulta, "receta", None)
        if receta is None:
            receta = Receta.objects.create(
                consulta=consulta,
                medico=self.request.user,
            )

        if post_data:
            consulta_form = ConsultaMedicoForm(post_data, instance=consulta)
            receta_form = RecetaForm(post_data, instance=receta)
            med_formset = MedicamentoRecetadoFormSet(
                post_data,
                instance=receta,
                prefix="meds",
            )

        else:
            consulta_form = ConsultaMedicoForm(instance=consulta)
            receta_form = RecetaForm(instance=receta)
            med_formset = MedicamentoRecetadoFormSet(
                instance=receta,
                prefix="meds",
            )



        return consulta_form, receta_form, med_formset

    def get(self, request, pk):
        consulta = get_object_or_404(Consulta, pk=pk)
        # Al acceder por primera vez se marca como "en progreso" si estaba en espera
        if consulta.estado == "espera":
            if consulta.medico and doctor_tiene_consulta_en_progreso(consulta.medico):
                messages.error(request, "El médico ya tiene otra consulta en progreso.")
                return redirect(self.next_url)
            consulta.estado = "en_progreso"
            consulta.fecha_atencion = timezone.now()
            consulta.save()
        consulta_form, receta_form, med_formset = self._setup_forms(consulta)
        return render(
            request,
            self.template_name,
            {
                "usuario": request.user,
                "consulta": consulta,
                "consulta_form": consulta_form,
                "receta_form": receta_form,
                "med_formset": med_formset,
                "next": self.next_url,
            },
        )

    def post(self, request, pk):
        consulta = get_object_or_404(Consulta, pk=pk)
        action = request.POST.get("action", "save")
        consulta_form, receta_form, med_formset = self._setup_forms(consulta, post_data=request.POST)

        if all([consulta_form.is_valid(), receta_form.is_valid(), med_formset.is_valid()]):
            consulta = consulta_form.save(commit=False)

            if action == "start" and consulta.estado == "espera":
                if consulta.medico and doctor_tiene_consulta_en_progreso(consulta.medico):
                    messages.error(request, "El médico ya tiene otra consulta en progreso.")
                    return redirect(self.next_url)
                consulta.estado = "en_progreso"
                consulta.fecha_atencion = timezone.now()
                messages.success(request, "Consulta iniciada.")

            elif action == "finish":
                consulta.estado = "finalizada"
                messages.success(request, "Consulta finalizada.")
                if consulta.cita:
                    consulta.cita.estado = "completada"
                    consulta.cita.save()

            consulta.save()

            receta = receta_form.save(commit=False)
            receta.medico = request.user
            receta.save()
            med_formset.instance = receta
            med_formset.save()

            if action == "finish":
                return redirect(self.next_url)

            return redirect("consultas_atencion", pk=consulta.pk)

        return render(
            request,
            self.template_name,
            {
                "usuario": request.user,
                "consulta": consulta,
                "consulta_form": consulta_form,
                "receta_form": receta_form,
                "med_formset": med_formset,
                "next": self.next_url,
            },
        )


@method_decorator(login_required, name='dispatch')
class ConsultaUpdateView(NextRedirectMixin, LoginRequiredMixin, ConsultaPermisoMixin, UpdateView):
    """Vista completa para editar consulta con signos vitales, receta y medicamentos"""
    model = Consulta
    template_name = 'PAGES/consultas/editar.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estado == "cancelada":
            messages.error(request, "No puedes editar una consulta cancelada.")
            return redirect("consulta_detalle", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        """Use the medical form for editing regardless of tipo."""
        return ConsultaMedicoForm

    def _get_return_to(self):
        return (self.request.POST.get("next") or
                self.request.GET.get("next") or
                self.request.META.get("HTTP_REFERER") or
                reverse("paciente_detalle", args=[self.get_object().paciente.pk]))

    def get_success_url(self):
        return self._get_return_to()

    def _init_extra_forms(self, consulta, post_data=None):
        """Build forms for vital signs, recipe and medications."""
        signos, _ = SignosVitales.objects.get_or_create(consulta=consulta)
        receta, _ = Receta.objects.get_or_create(
            consulta=consulta, defaults={"medico": self.request.user}
        )

        if post_data:
            signos_form = SignosVitalesForm(post_data, instance=signos)
            receta_form = RecetaForm(post_data, instance=receta)
            med_formset = MedicamentoRecetadoFormSet(
                post_data, instance=receta, prefix="meds"
            )
        else:
            signos_form = SignosVitalesForm(instance=signos)
            receta_form = RecetaForm(instance=receta)
            med_formset = MedicamentoRecetadoFormSet(
                instance=receta, prefix="meds"
            )

        return signos_form, receta_form, med_formset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        consulta = self.get_object()

        signos_form = kwargs.get("signos_form")
        receta_form = kwargs.get("receta_form")
        med_formset = kwargs.get("med_formset")

        if not all([signos_form, receta_form, med_formset]):
            signos_form, receta_form, med_formset = self._init_extra_forms(consulta)

        ctx.update(
            {
                "usuario": self.request.user,
                "signos_form": signos_form,
                "receta_form": receta_form,
                "med_formset": med_formset,
                "return_to": self._get_return_to(),
            }
        )
        return ctx

    def get_form_kwargs(self):
        """Return form kwargs without passing current user."""
        return super().get_form_kwargs()

    def form_valid(self, form):
        consulta = form.save(commit=False)
        
        # Asegurar que el médico esté asignado si el usuario es médico
        if self.request.user.rol == 'medico' and not consulta.medico:
            consulta.medico = self.request.user
        
        consulta.save()
        messages.success(self.request, 'Consulta actualizada exitosamente.')
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form_class = self.get_form_class()
        consulta_form = form_class(request.POST, instance=self.object)

        signos_form, receta_form, med_formset = self._init_extra_forms(
            self.object, post_data=request.POST
        )
        ctx = self.get_context_data(
            form=consulta_form,
            signos_form=signos_form,
            receta_form=receta_form,
            med_formset=med_formset,
        )

        if (consulta_form.is_valid() and signos_form.is_valid()
                and receta_form.is_valid() and med_formset.is_valid()):
            
            consulta = consulta_form.save()
            
            signos = signos_form.save(commit=False)
            signos.consulta = consulta
            signos.save()

            receta = receta_form.save(commit=False)
            receta.consulta = consulta
            receta.medico = request.user
            receta.save()

            med_formset.instance = receta
            med_formset.save()

            messages.success(request, 'Consulta actualizada exitosamente.')
            return redirect(self.get_success_url())

        return render(request, self.template_name, ctx)


@login_required
def consulta_cancelar(request, pk):
    """Marca la consulta como 'cancelada'"""
    if request.user.rol not in ("admin", "medico", "asistente"):
        messages.error(request, "No tienes permiso para cancelar consultas.")
        return redirect("consultas_lista")

    consulta = get_object_or_404(Consulta, pk=pk)
    if consulta.estado == "cancelada":
        messages.info(request, "La consulta ya estaba cancelada.")
    else:
        consulta.estado = "cancelada"
        consulta.save()
        messages.success(request, "Consulta cancelada correctamente.")

        if consulta.cita:
            consulta.cita.estado = "cancelada"
            consulta.cita.save()

    return redirect("consultas_lista")


# ═══════════════════════════════════════════════════════════════
# ⏰ HORARIOS
# ═══════════════════════════════════════════════════════════════

class HorarioPermisoMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.rol == "admin"


class HorarioListView(ListView):
    model = HorarioMedico
    template_name = "PAGES/horarios/lista.html"
    context_object_name = "horarios_raw"

    def get_queryset(self):
        qs = HorarioMedico.objects.select_related("medico", "consultorio")
        if self.request.user.rol == "medico":
            qs = qs.filter(medico=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        horarios_grouped = defaultdict(lambda: {"dias": [], "pk": None})

        for horario in self.object_list:
            key = (horario.medico, horario.consultorio, horario.hora_inicio, horario.hora_fin)
            horarios_grouped[key]["dias"].append(horario.dia)
            horarios_grouped[key]["pk"] = horario.pk

        context["horarios"] = [
            {
                "medico": k[0],
                "consultorio": k[1],
                "hora_inicio": k[2],
                "hora_fin": k[3],
                "dias": sorted(v["dias"]),
                "pk": v["pk"],
            }
            for k, v in horarios_grouped.items()
        ]
        context["usuario"] = self.request.user
        return context


class HorarioMedicoCreateView(NextRedirectMixin, LoginRequiredMixin, HorarioPermisoMixin, FormView):
    form_class = HorarioMedicoForm
    template_name = "PAGES/horarios/crear.html"
    success_url = reverse_lazy("horarios_lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        dias = form.cleaned_data.get("dias")
        if not dias:
            form.add_error("dias", "Debe seleccionar al menos un día.")
            return self.form_invalid(form)
        hora_inicio = form.cleaned_data["hora_inicio"]
        hora_fin = form.cleaned_data["hora_fin"]
        medico = form.cleaned_data["medico"]
        consultorio = medico.consultorio

        for dia in dias:
            HorarioMedico.objects.create(
                medico=medico,
                consultorio=consultorio,
                dia=dia,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin
            )

        messages.success(self.request, "Horarios creados correctamente.")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        return ctx


class HorarioUpdateView(NextRedirectMixin, LoginRequiredMixin, HorarioPermisoMixin, UpdateView):
    model = HorarioMedico
    form_class = HorarioMedicoForm
    template_name = "PAGES/horarios/editar.html"
    success_url = reverse_lazy("horarios_lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        grupo = HorarioMedico.objects.filter(
            medico=obj.medico,
            consultorio=obj.consultorio,
            hora_inicio=obj.hora_inicio,
            hora_fin=obj.hora_fin
        )
        initial["dias"] = [h.dia for h in grupo]
        return initial

    def form_valid(self, form):
        obj = self.get_object()
        HorarioMedico.objects.filter(
            medico=obj.medico,
            consultorio=obj.consultorio,
            hora_inicio=obj.hora_inicio,
            hora_fin=obj.hora_fin
        ).delete()

        medico = obj.medico
        consultorio = medico.consultorio
        hora_inicio = form.cleaned_data["hora_inicio"]
        hora_fin = form.cleaned_data["hora_fin"]
        nuevos_dias = form.cleaned_data.get("dias")
        if not nuevos_dias:
            form.add_error("dias", "Debe seleccionar al menos un día.")
            return self.form_invalid(form)

        for dia in nuevos_dias:
            HorarioMedico.objects.create(
                medico=medico,
                consultorio=consultorio,
                dia=dia,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin
            )

        messages.success(self.request, "Horario actualizado correctamente.")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        return ctx


class HorarioDeleteView(NextRedirectMixin, LoginRequiredMixin, HorarioPermisoMixin, DeleteView):
    model = HorarioMedico
    template_name = "PAGES/horarios/eliminar.html"
    success_url = reverse_lazy("horarios_lista")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Horario eliminado correctamente.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        return ctx


# ═══════════════════════════════════════════════════════════════
# 📋 ANTECEDENTES Y MEDICAMENTOS
# ═══════════════════════════════════════════════════════════════

def antecedente_nuevo(request, paciente_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    expediente, _ = Expediente.objects.get_or_create(paciente=paciente)

    tipo = request.GET.get('tipo')
    initial_data = {'tipo': tipo} if tipo else {}

    form = AntecedenteForm(
        request.POST or None,
        initial=initial_data,
        expediente=expediente,
    )

    if tipo:
        form.fields['tipo'].widget.attrs['disabled'] = True

    next_url = request.POST.get("next") or request.GET.get("next")
    default_url = reverse('paciente_detalle', args=[paciente.pk])

    if request.method == 'POST' and form.is_valid():
        if (
            form.cleaned_data.get("tipo") == "alergico"
            and expediente.antecedentes.filter(
                tipo="alergico",
                descripcion__iexact=form.cleaned_data.get("descripcion"),
            ).exists()
        ):
            form.add_error("descripcion", "Esta alergia ya está registrada.")
        else:
            antecedente = form.save(commit=False)
            antecedente.expediente = expediente
            antecedente.save()
            return redirect(next_url or default_url)

    return render(request, 'PAGES/antecedentes/crear.html', {
        'usuario': request.user,
        'paciente': paciente,
        'form': form,
        'tipo_selected': tipo,
        'next': next_url or default_url,
    })


def medicamento_nuevo(request, paciente_id):
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    expediente = paciente.expediente

    next_url = request.POST.get("next") or request.GET.get("next")
    default_url = reverse('paciente_detalle', args=[paciente.pk])

    if request.method == 'POST':
        form = MedicamentoActualForm(request.POST)
        if form.is_valid():
            medicamento = form.save(commit=False)
            medicamento.expediente = expediente
            medicamento.save()
            return redirect(next_url or default_url)
    else:
        form = MedicamentoActualForm()

    return render(request, 'PAGES/medicamentos/crear.html', {
        'form': form,
        'paciente': paciente,
        'usuario': request.user,
        'next': next_url or default_url,
    })


class AntecedenteUpdateView(NextRedirectMixin, PacientePermisoMixin, UpdateView):
    model = Antecedente
    form_class = AntecedenteForm
    template_name = 'PAGES/antecedentes/editar.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['expediente'] = self.get_object().expediente
        return kwargs

    def get_success_url(self):
        next_url = self.get_next_url()
        if next_url:
            return next_url
        return reverse('paciente_detalle', args=[self.object.expediente.paciente.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['usuario'] = self.request.user
        ctx['paciente'] = self.object.expediente.paciente
        ctx['next'] = self.get_next_url() or reverse('paciente_detalle', args=[ctx['paciente'].pk])
        return ctx


class AntecedenteDeleteView(NextRedirectMixin, PacientePermisoMixin, DeleteView):
    model = Antecedente
    template_name = 'PAGES/antecedentes/eliminar.html'

    def get_success_url(self):
        next_url = self.get_next_url()
        if next_url:
            return next_url
        return reverse('paciente_detalle', args=[self.object.expediente.paciente.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['usuario'] = self.request.user
        return ctx


class MedicamentoUpdateView(NextRedirectMixin, PacientePermisoMixin, UpdateView):
    model = MedicamentoActual
    form_class = MedicamentoActualForm
    template_name = 'PAGES/medicamentos/editar.html'

    def get_success_url(self):
        next_url = self.get_next_url()
        if next_url:
            return next_url
        return reverse('paciente_detalle', args=[self.object.expediente.paciente.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['usuario'] = self.request.user
        ctx['paciente'] = self.object.expediente.paciente
        ctx['next'] = self.get_next_url() or reverse('paciente_detalle', args=[ctx['paciente'].pk])
        return ctx


class MedicamentoDeleteView(NextRedirectMixin, PacientePermisoMixin, DeleteView):
    model = MedicamentoActual
    template_name = 'PAGES/medicamentos/eliminar.html'

    def get_success_url(self):
        next_url = self.get_next_url()
        if next_url:
            return next_url
        return reverse('paciente_detalle', args=[self.object.expediente.paciente.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['usuario'] = self.request.user
        return ctx


def receta_nueva(request, consulta_id):
    consulta = get_object_or_404(Consulta, pk=consulta_id)

    if request.user.rol == "medico" and consulta.medico != request.user:
        messages.error(request, "No puedes editar esta consulta, no est\u00e1s asignado.")
        return redirect("consulta_detalle", pk=consulta.pk)
    if request.user.rol not in ("medico", "admin"):
        return redirect("consultas_lista")
    receta, _ = Receta.objects.get_or_create(
        consulta=consulta,
        defaults={'medico': request.user}
    )

    if request.method == 'POST':
        receta_form = RecetaForm(request.POST, instance=receta)
        med_formset = MedicamentoRecetadoFormSet(request.POST, instance=receta)
        if receta_form.is_valid() and med_formset.is_valid():
            receta = receta_form.save(commit=False)
            receta.medico = request.user
            receta.save()
            med_formset.save()
            return redirect_next(request, 'paciente_detalle', pk=consulta.paciente.pk)
    else:
        receta_form = RecetaForm(instance=receta)
        med_formset = MedicamentoRecetadoFormSet(instance=receta)

    return render(request, 'PAGES/recetas/crear.html', {
        'usuario': request.user,
        'consulta': consulta,
        'receta_form': receta_form,
        'med_formset': med_formset,
    })


class SignosDetailView(LoginRequiredMixin, DetailView):
    model = SignosVitales
    template_name = 'PAGES/signos/detalle.html'
    context_object_name = 'signos'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        # Ensure self.object.consulta exists before accessing .paciente.pk
        # Usar la página de lista de consultas como destino predeterminado
        context['volver_a'] = self.request.GET.get('next') or reverse('consultas_lista')
        return context


# ═══════════════════════════════════════════════════════════════
# 🩺 VISTAS PARA SIGNOS VITALES (CORREGIDAS)
# ═══════════════════════════════════════════════════════════════

@login_required
def signos_nuevo(request, paciente_id):
    """Vista para crear signos vitales para un paciente"""
    paciente = get_object_or_404(Paciente, pk=paciente_id)
    
    # Verificar permisos
    if request.user.rol not in ('medico', 'asistente', 'admin'):
        messages.error(request, 'No tienes permisos para registrar signos vitales.')
        return redirect_next(request, 'paciente_detalle', pk=paciente.pk)
    
    # Obtener o crear consulta activa
    consulta = None
    consulta_id = request.GET.get('consulta_id')
    
    if consulta_id:
        try:
            consulta = get_object_or_404(Consulta, pk=consulta_id, paciente=paciente)
        except:
            pass
        else:
            if consulta.estado == "cancelada":
                messages.error(request, "No se pueden registrar signos vitales en una consulta cancelada.")
                return redirect_next(request, 'consulta_detalle', pk=consulta.pk)
    
    if not consulta:
        # Buscar consulta activa (en espera o en progreso)
        consulta = Consulta.objects.filter(
            paciente=paciente,
            estado__in=['espera', 'en_progreso']
        ).first()
    
    if not consulta:
        messages.error(request, 'No hay consulta activa para registrar signos vitales.')
        return redirect_next(request, 'paciente_detalle', pk=paciente.pk)
    
    # Verificar si ya existen signos vitales para esta consulta
    signos_existentes = None
    try:
        signos_existentes = consulta.signos_vitales
    except SignosVitales.DoesNotExist:
        pass
    
    if request.method == 'POST':
        if signos_existentes:
            form = SignosVitalesForm(request.POST, instance=signos_existentes)
        else:
            form = SignosVitalesForm(request.POST)
        
        if form.is_valid():
            signos = form.save(commit=False)
            signos.consulta = consulta
            signos.save()
            
            action = 'actualizados' if signos_existentes else 'registrados'
            messages.success(request, f'Signos vitales {action} correctamente.')
            
            # Redirigir según el parámetro next o al detalle del paciente
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect_next(request, 'paciente_detalle', pk=paciente.pk)
    else:
        if signos_existentes:
            form = SignosVitalesForm(instance=signos_existentes)
        else:
            form = SignosVitalesForm()
    
    context = {
        'form': form,
        'paciente': paciente,
        'consulta': consulta,
        'signos_existentes': signos_existentes,
        'usuario': request.user,
        'titulo': 'Actualizar Signos Vitales' if signos_existentes else 'Registrar Signos Vitales',
        'next': request.GET.get('next', reverse('paciente_detalle', args=[paciente.pk])),
    }
    
    return render(request, 'PAGES/signos/crear.html', context)


@login_required
def signos_editar(request, pk):
    """Vista para editar signos vitales de una consulta existente."""
    signos = get_object_or_404(SignosVitales, pk=pk)
    
    # Verificar permisos: solo médico/admin/asistente y si está asociado a su consultorio/es su consulta
    user = request.user
    # Check if the user has permission to edit these vital signs
    # Admin can edit any.
    # Medico can edit if it's their consultation or in their consultorio.
    # Asistente can edit if it's in their consultorio.
    can_edit = False
    if user.rol == 'admin':
        can_edit = True
    elif user.rol == 'medico' and signos.consulta.medico == user:
        can_edit = True
    elif user.rol == 'asistente' and signos.consulta.cita and signos.consulta.cita.consultorio == user.consultorio:
        can_edit = True
    elif user.rol == 'asistente' and not signos.consulta.cita and hasattr(signos.consulta, 'asistente') and signos.consulta.asistente == user:
        can_edit = True # If assistant created a consultation without a cita, they can edit its signs

    if not can_edit:
        messages.error(request, 'No tienes permisos para editar estos signos vitales.')
        return redirect_next(request, 'signos_detalle', pk=pk)

    next_url = request.POST.get('next') or request.GET.get('next')
    default_url = reverse('signos_detalle', args=[signos.pk])

    if request.method == 'POST':
        form = SignosVitalesForm(request.POST, instance=signos)
        if form.is_valid():
            form.save()
            messages.success(request, 'Signos vitales actualizados correctamente.')
            return redirect(next_url or default_url)
    else:
        form = SignosVitalesForm(instance=signos)

    context = {
        'form': form,
        'signos': signos,
        'usuario': user,
        'titulo': 'Editar Signos Vitales',
        'next': next_url or default_url,
    }
    return render(request, 'PAGES/signos/crear.html', context) # Reusing crear.html for editing


@login_required
def signos_eliminar(request, pk):
    """Vista para eliminar signos vitales de una consulta."""
    signos = get_object_or_404(SignosVitales, pk=pk)
    
    # Verificar permisos: solo admin o el médico/asistente asociado
    user = request.user
    can_delete = False
    if user.rol == 'admin':
        can_delete = True
    elif user.rol == 'medico' and signos.consulta.medico == user:
        can_delete = True
    elif user.rol == 'asistente' and signos.consulta.cita and signos.consulta.cita.consultorio == user.consultorio:
        can_delete = True
    elif user.rol == 'asistente' and not signos.consulta.cita and hasattr(signos.consulta, 'asistente') and signos.consulta.asistente == user:
        can_delete = True

    if not can_delete:
        messages.error(request, 'No tienes permisos para eliminar estos signos vitales.')
        return redirect_next(request, 'signos_detalle', pk=pk)

    if request.method == 'POST':
        try:
            paciente_pk = signos.consulta.paciente.pk if hasattr(signos.consulta, 'paciente') else None
            signos.delete()
            messages.success(request, 'Signos vitales eliminados correctamente.')
            if paciente_pk:
                return redirect_next(request, 'paciente_detalle', pk=paciente_pk)
            return redirect_next(request, 'home') # Fallback
        except Exception as e:
            messages.error(request, f'Error al eliminar signos vitales: {str(e)}')
            return redirect_next(request, 'signos_detalle', pk=pk)
    
    context = {
        'signos': signos,
        'usuario': user,
        'titulo': 'Confirmar Eliminación',
        'next': request.GET.get('next', reverse('signos_detalle', args=[signos.pk])),
    }
    return render(request, 'PAGES/signos/eliminar.html', context)


# ═══════════════════════════════════════════════════════════════
# 📊 AUDITORÍA Y NOTIFICACIONES
# ═══════════════════════════════════════════════════════════════

class AuditMiddleware(MiddlewareMixin):
    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__(get_response)

    def __call__(self, request):
        from .audit_generic import set_current_request
        set_current_request(request)
        
        try:
            response = self.get_response(request)
            return response
        finally:
            # Limpiar el request del thread local después de la respuesta
            set_current_request(None)


# ═══════════════════════════════════════════════════════════════
# 📊 AUDITORÍA MEJORADA
# ═══════════════════════════════════════════════════════════════

class AuditoriaListView(AdminRequiredMixin, ListView):
    model = Auditoria
    template_name = "PAGES/auditoria/panel.html"
    context_object_name = "registros"
    paginate_by = 25

    def get_queryset(self):
        qs = Auditoria.objects.select_related('usuario', 'content_type').order_by('-fecha')
        
        # Filtros
        usuario_id = self.request.GET.get('usuario')
        accion = self.request.GET.get('accion')
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')
        modelo = self.request.GET.get('modelo')
        ip = self.request.GET.get('ip')
        
        if usuario_id:
            qs = qs.filter(usuario_id=usuario_id)
        
        if accion:
            qs = qs.filter(accion__icontains=accion)
        
        if fecha_desde:
            try:
                from datetime import datetime
                fecha = datetime.strptime(fecha_desde, '%Y-%m-%d')
                qs = qs.filter(fecha__date__gte=fecha.date())
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                from datetime import datetime
                fecha = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                qs = qs.filter(fecha__date__lte=fecha.date())
            except ValueError:
                pass
        
        if modelo:
            qs = qs.filter(content_type__model=modelo)
        
        if ip:
            qs = qs.filter(ip_address__icontains=ip)
        
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # Estadísticas generales
        total_registros = Auditoria.objects.count()
        hoy = timezone.now().date()
        registros_hoy = Auditoria.objects.filter(fecha__date=hoy).count()
        
        # Top usuarios más activos
        from django.db.models import Count
        usuarios_activos = Auditoria.objects.values(
            'usuario__first_name', 'usuario__last_name', 'usuario__username'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        # Acciones más comunes
        acciones_comunes = Auditoria.objects.values('accion').annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        # Modelos más modificados
        modelos_modificados = Auditoria.objects.values(
            'content_type__model'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        # IPs más activas
        ips_activas = Auditoria.objects.exclude(
            ip_address__isnull=True
        ).values('ip_address').annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        # Actividad por día (últimos 7 días)
        from datetime import timedelta
        hace_7_dias = hoy - timedelta(days=7)
        actividad_diaria = []
        
        for i in range(7):
            dia = hace_7_dias + timedelta(days=i)
            count = Auditoria.objects.filter(fecha__date=dia).count()
            actividad_diaria.append({
                'fecha': dia,
                'count': count
            })
        
        # Usuarios para filtro
        usuarios_filtro = Usuario.objects.filter(
            id__in=Auditoria.objects.values_list('usuario_id', flat=True).distinct()
        ).order_by('first_name', 'last_name')
        
        # Modelos para filtro
        modelos_filtro = ContentType.objects.filter(
            id__in=Auditoria.objects.values_list('content_type_id', flat=True).distinct()
        ).order_by('model')
        
        ctx.update({
            'usuario': self.request.user,
            'stats': {
                'total_registros': total_registros,
                'registros_hoy': registros_hoy,
                'usuarios_activos': usuarios_activos,
                'acciones_comunes': acciones_comunes,
                'modelos_modificados': modelos_modificados,
                'ips_activas': ips_activas,
                'actividad_diaria': actividad_diaria,
            },
            'usuarios_filtro': usuarios_filtro,
            'modelos_filtro': modelos_filtro,
            'filtros_actuales': {
                'usuario': self.request.GET.get('usuario', ''),
                'accion': self.request.GET.get('accion', ''),
                'fecha_desde': self.request.GET.get('fecha_desde', ''),
                'fecha_hasta': self.request.GET.get('fecha_hasta', ''),
                'modelo': self.request.GET.get('modelo', ''),
                'ip': self.request.GET.get('ip', ''),
            }
        })
        
        return ctx

@login_required
def auditoria_detalle_ajax(request, auditoria_id):
    """Vista AJAX para obtener detalles de un registro de auditoría"""
    try:
        registro = get_object_or_404(Auditoria, pk=auditoria_id)
        
        # Verificar permisos
        if request.user.rol != 'admin':
            return JsonResponse({'error': 'Sin permisos'}, status=403)
        
        data = {
            'success': True,
            'registro': {
                'id': registro.id,
                'usuario': {
                    'nombre': registro.usuario.get_full_name(),
                    'username': registro.usuario.username,
                    'rol': registro.usuario.get_rol_display(),
                },
                'accion': registro.accion,
                'descripcion': registro.descripcion,
                'fecha': registro.fecha.strftime('%d/%m/%Y %H:%M:%S'),
                'ip_address': registro.ip_address,
                'user_agent': registro.user_agent,
                'objeto': {
                    'tipo': registro.content_type.model,
                    'id': registro.object_id,
                    'str': str(registro.objeto) if registro.objeto else 'Objeto eliminado',
                },
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def auditoria_exportar_csv(request):
    """Exportar registros de auditoría a CSV"""
    if request.user.rol != 'admin':
        messages.error(request, 'No tienes permisos para exportar auditoría.')
        return redirect_next(request, 'auditoria_lista')
    
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="auditoria.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Fecha', 'Usuario', 'Rol', 'Acción', 'Objeto', 'Descripción', 
        'IP', 'Navegador'
    ])
    
    registros = Auditoria.objects.select_related('usuario', 'content_type').order_by('-fecha')
    
    for registro in registros:
        writer.writerow([
            registro.fecha.strftime('%d/%m/%Y %H:%M:%S'),
            registro.usuario.get_full_name(),
            registro.usuario.get_rol_display(),
            registro.accion,
            f"{registro.content_type.model} #{registro.object_id}",
            registro.descripcion,
            registro.ip_address or '',
            registro.user_agent[:100] if registro.user_agent else '',
        ])
    
    return response



class NotificacionPermisoMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.rol not in ("medico", "admin", "asistente"):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect_next(request, 'home')
        return super().dispatch(request, *args, **kwargs)


class NotificacionListView(NotificacionPermisoMixin, ListView):
    model = Notificacion
    template_name = "PAGES/notificaciones/lista.html"
    context_object_name = "notificaciones"
    paginate_by = 20

    def get_queryset(self):
        qs = Notificacion.objects.filter(
            destinatario=self.request.user
        ).select_related('content_type').order_by('-fecha')
        
        # Filtros
        tipo = self.request.GET.get('tipo')
        categoria = self.request.GET.get('categoria')
        leido = self.request.GET.get('leido')
        
        if tipo:
            qs = qs.filter(tipo=tipo)
        
        if categoria:
            qs = qs.filter(categoria=categoria)
        
        if leido == 'true':
            qs = qs.filter(leido=True)
        elif leido == 'false':
            qs = qs.filter(leido=False)
        
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        
        # Estadísticas
        total = self.get_queryset().count()
        no_leidas = self.get_queryset().filter(leido=False).count()
        leidas = total - no_leidas
        
        ctx.update({
            'stats': {
                'total': total,
                'no_leidas': no_leidas,
                'leidas': leidas,
            }
        })
        
        return ctx



@login_required
def marcar_notificacion_leida(request, notificacion_id):
    """Marcar una notificación específica como leída"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        notificacion = get_object_or_404(Notificacion, id=notificacion_id)
        
        # Verificar permisos
        if request.user.rol != 'admin' and notificacion.usuario != request.user:
            return JsonResponse({'success': False, 'error': 'Sin permisos'})
        
        # Marcar como leída
        notificacion.leido = True
        notificacion.fecha_leido = timezone.now()  # ← CORREGIDO
        notificacion.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificación marcada como leída'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al marcar notificación: {str(e)}'
        })



@login_required
def eliminar_notificacion(request, notificacion_id):
    """Eliminar una notificación específica"""
    if request.method == 'DELETE':
        try:
            notificacion = get_object_or_404(
                Notificacion, 
                id=notificacion_id, 
                destinatario=request.user
            )
            notificacion.delete()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required
def marcar_todas_notificaciones_leidas(request):
    """Marcar todas las notificaciones del usuario como leídas"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        user = request.user
        
        # Filtrar notificaciones según el rol
        if user.rol == 'admin':
            notificaciones = Notificacion.objects.filter(leido=False)
        else:
            notificaciones = Notificacion.objects.filter(destinatario=user, leido=False) # Corrected to use destinatario
        
        # Marcar todas como leídas
        count = notificaciones.update(
            leido=True,
            fecha_leido=timezone.now()  # ← CORREGIDO
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{count} notificaciones marcadas como leídas',
            'count': count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al marcar notificaciones: {str(e)}'
        })



@login_required
def notificaciones_count_ajax(request):
    """Obtener conteo de notificaciones no leídas (para el badge)"""
    try:
        count = Notificacion.objects.filter(
            destinatario=request.user,
            leido=False
        ).count()
        
        return JsonResponse({'count': count})
    except Exception as e:
        return JsonResponse({'error': str(e)})


# ═══════════════════════════════════════════════════════════════
# 📄 PDF Y EXPORTACIÓN
# ═══════════════════════════════════════════════════════════════

class PacientePDFView(View):
    def get(self, request, pk):
        paciente = get_object_or_404(Paciente, pk=pk)
        expediente = getattr(paciente, "expediente", None)
        consultas = paciente.consulta_set.filter(estado="finalizada").order_by('-fecha_creacion')

        context = {
            "paciente": paciente,
            "antecedentes": expediente.antecedentes.all() if expediente else [],
            "alergias": expediente.antecedentes.filter(tipo="alergico") if expediente else [],
            "medicamentos": expediente.medicamentos_actuales.all() if expediente else [],
            "consultas": consultas
        }

        return generar_pdf("PAGES/pdf/paciente_historial.html", context)
    
    
    
    
# Actualización para la vista de PDF de receta
def receta_pdf_view(request, receta_id):
    """Vista mejorada para generar PDF de receta médica"""
    receta = get_object_or_404(Receta, pk=receta_id)
    consulta = receta.consulta

    if not receta.medicamentos.exists():
        messages.error(request, "La receta aún no cuenta con medicamentos.")
        return redirect("consulta_detalle", pk=consulta.pk)

    # Verificar permisos
    if request.user.rol not in ['medico', 'admin']:
        if request.user.rol == 'asistente' and consulta.medico and request.user.consultorio != consulta.medico.consultorio:
            messages.error(request, 'No tienes permisos para ver esta receta.')
            return redirect_next(request, 'consultas_lista')

    template_path = "PAGES/pdf/receta_consulta.html"
    context = {
        "consulta": consulta,
        "receta": receta,
        "fecha_actual": timezone.now(),
    }

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="receta_{consulta.paciente.nombre_completo.replace(" ", "_")}_{receta.fecha_emision.strftime("%Y%m%d")}.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("Error al generar el PDF", status=500)

    return response
# ═══════════════════════════════════════════════════════════════
# 🔧 AJAX Y FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def obtener_horarios_disponibles(request):
    fecha_str = request.GET.get("fecha")
    if not fecha_str:
        return JsonResponse({"error": "Fecha no proporcionada"}, status=400)

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Formato de fecha inválido"}, status=400)

    dias_map = {
        "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles",
        "thursday": "jueves", "friday": "viernes",
        "saturday": "sábado", "sunday": "domingo",
    }
    dia_semana = dias_map[fecha.strftime("%A").lower()]
    intervalo = timedelta(minutes=30)
    horarios = []

    for horario in HorarioMedico.objects.filter(dia=dia_semana):
        medico = horario.medico
        consultorio = horario.consultorio
        hora_actual = datetime.combine(fecha, horario.hora_inicio)
        hora_fin = datetime.combine(fecha, horario.hora_fin)

        citas = Cita.objects.filter(
            medico_asignado=medico,
            fecha_hora__date=fecha
        )

        bloques_ocupados = set()
        for cita in citas:
            inicio = cita.fecha_hora
            fin = inicio + timedelta(minutes=cita.duracion)
            bloque = inicio.replace(minute=(inicio.minute // 30) * 30, second=0, microsecond=0)
            while bloque < fin:
                bloques_ocupados.add(bloque.time().strftime("%H:%M"))
                bloque += intervalo

        bloques = []
        cursor = hora_actual
        while cursor + intervalo <= hora_fin:
            hora_str = cursor.time().strftime("%H:%M")
            ocupado = hora_str in bloques_ocupados

            paciente_nombre = None
            if ocupado:
                cita = Cita.objects.filter(
                    medico_asignado=medico,
                    fecha_hora__date=fecha,
                    fecha_hora__time__gte=cursor.time(),
                    fecha_hora__time__lt=(cursor + intervalo).time()
                ).first()
                if cita:
                    paciente_nombre = cita.paciente.nombre_completo

            bloques.append({
                "hora": hora_str,
                "ocupado": ocupado,
                "paciente": paciente_nombre
            })
            cursor += intervalo

        horarios.append({
            "medico_id": medico.id,
            "medico": medico.get_full_name(),
            "consultorio": consultorio.nombre,
            "bloques": bloques,
        })

    return JsonResponse({"horarios": horarios})


def ajax_consultorio_del_medico(request, medico_id):
    medico = Usuario.objects.filter(pk=medico_id, rol='medico').first()
    if medico and medico.consultorio:
        return JsonResponse({'consultorio_id': medico.consultorio.id})
    return JsonResponse({'consultorio_id': ''})


@login_required
def ajax_signos_vitales(request, consulta_id):
    """Vista AJAX para obtener signos vitales de una consulta"""
    try:
        consulta = get_object_or_404(Consulta, pk=consulta_id)
        
        if not hasattr(consulta, 'signos_vitales'):
            return JsonResponse({'error': 'No hay signos vitales registrados'}, status=404)
        
        signos = consulta.signos_vitales
        data = {
            'tension_arterial': signos.tension_arterial,
            'frecuencia_cardiaca': signos.frecuencia_cardiaca,
            'temperatura': str(signos.temperatura),
            'peso': str(signos.peso),
            'talla': str(signos.talla),
            'fecha_registro': signos.fecha_registro.strftime('%d/%m/%Y %H:%M') if hasattr(signos, 'fecha_registro') else '',
        }
        
        return JsonResponse(data)
        
    except Consulta.DoesNotExist:
        return JsonResponse({'error': 'Consulta no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def consultas_stats_ajax(request):
    """Vista AJAX para obtener estadísticas actualizadas del consultorio"""
    usuario = request.user
    consultorio = getattr(usuario, 'consultorio', None)
    
    if not consultorio:
        return JsonResponse({'error': 'No tienes consultorio asignado'}, status=400)
    
    consultas = Consulta.objects.filter(medico__consultorio=consultorio)
    
    stats = {
        'pendientes': consultas.filter(estado='espera').count(),
        'en_progreso': consultas.filter(estado='en_progreso').count(),
        'finalizadas': consultas.filter(estado='finalizada').count(),
        'canceladas': consultas.filter(estado='cancelada').count(),
        'total': consultas.count(),
        'hoy': consultas.filter(fecha_creacion__date=timezone.now().date()).count(),
        'esta_semana': consultas.filter(
            fecha_creacion__gte=timezone.now() - timedelta(days=7)
        ).count()
    }
    
    return JsonResponse(stats)


@login_required
def dashboard_stats(request):
    """Vista para estadísticas del dashboard filtradas por consultorio"""
    usuario = request.user
    consultorio = getattr(usuario, 'consultorio', None)
    
    if not consultorio:
        return JsonResponse({'error': 'No tienes consultorio asignado'}, status=400)
    
    consultas = Consulta.objects.filter(medico__consultorio=consultorio)
    
    stats = {
        'total_consultas': consultas.count(),
        'consultas_hoy': consultas.filter(fecha_creacion__date=timezone.now().date()).count(),
        'consultas_pendientes': consultas.filter(estado='espera').count(),
        'consultas_en_progreso': consultas.filter(estado='en_progreso').count(),
        'consultas_finalizadas': consultas.filter(estado='finalizada').count(),
        'consultas_canceladas': consultas.filter(estado='cancelada').count(),
    }
    
    medicos_stats = []
    medicos = Usuario.objects.filter(rol='medico', consultorio=consultorio, is_active=True)
    
    for medico in medicos:
        medico_consultas = consultas.filter(medico=medico)
        medicos_stats.append({
            'medico': medico.get_full_name(),
            'total': medico_consultas.count(),
            'pendientes': medico_consultas.filter(estado='espera').count(),
            'en_progreso': medico_consultas.filter(estado='en_progreso').count(),
            'finalizadas': medico_consultas.filter(estado='finalizada').count(),
        })
    
    return JsonResponse({
        'stats': stats,
        'medicos_stats': medicos_stats,
        'consultorio': {
            'nombre': consultorio.nombre if hasattr(consultorio, 'nombre') else str(consultorio),
        }
    })


@login_required
def dashboard_citas_stats(request):
    """Estadísticas específicas para citas en el dashboard"""
    user = request.user
    queryset = Cita.objects.all()
    
    if user.rol == 'medico':
        queryset = queryset.filter(medico_asignado=user)
    elif user.rol == 'asistente' and user.consultorio:
        queryset = queryset.filter(consultorio=user.consultorio)
    
    hoy = timezone.now().date()
    
    stats = {
        'total_citas': queryset.count(),
        'citas_hoy': queryset.filter(fecha_hora__date=hoy).count(),
        'citas_pendientes': queryset.filter(estado__in=['programada', 'confirmada']).count(),
        'citas_completadas': queryset.filter(estado='completada').count(),
        'citas_canceladas': queryset.filter(estado='cancelada').count(),
        'citas_en_espera': queryset.filter(estado='en_espera').count(),
        'por_estado': dict(queryset.values('estado').annotate(count=Count('id')).values_list('estado', 'count')),
        'por_tipo': dict(queryset.values('tipo_cita').annotate(count=Count('id')).values_list('tipo_cita', 'count')),
        'por_prioridad': dict(queryset.values('prioridad').annotate(count=Count('id')).values_list('prioridad', 'count')),
    }
    
    return JsonResponse(stats)


class ConsultaCancelarView(LoginRequiredMixin, View):
    """Vista para cancelar una consulta"""
    
    def dispatch(self, request, *args, **kwargs):
        # Verificar permisos
        if request.user.rol == 'asistente':
            messages.warning(request, 'No tienes permiso para cancelar consultas.')
            return redirect('consultas_lista')
        if request.user.rol not in ('admin', 'medico'):
            messages.error(request, 'No tienes permisos para cancelar consultas.')
            return redirect_next(request, 'consultas_lista')
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, pk):
        """Mostrar página de confirmación para cancelar"""
        consulta = get_object_or_404(Consulta, pk=pk)
        
        # Verificar si ya está cancelada
        if consulta.estado == 'cancelada':
            messages.info(request, 'Esta consulta ya está cancelada.')
            return redirect_next(request, 'consultas_lista')
        
        context = {
            'consulta': consulta,
            'usuario': request.user,
            'puede_cancelar': consulta.estado in ['espera', 'en_progreso'],
        }
        
        return render(request, 'PAGES/consultas/cancelar.html', context)
    
    def post(self, request, pk):
        """Procesar la cancelación de la consulta"""
        if request.user.rol == "asistente":
            return HttpResponseForbidden("No tienes permiso para cancelar consultas.")
        consulta = get_object_or_404(Consulta, pk=pk)
        
        if consulta.estado == 'cancelada':
            messages.info(request, 'Esta consulta ya estaba cancelada.')
        elif consulta.estado == 'finalizada':
            messages.error(request, 'No se puede cancelar una consulta finalizada.')
        else:
            # Cancelar la consulta
            consulta.estado = 'cancelada'
            consulta.save()
            
            # Si tiene cita asociada, también cancelarla
            if consulta.cita:
                consulta.cita.estado = 'cancelada'
                consulta.cita.save()
            
            messages.success(request, f'Consulta de {consulta.paciente.nombre_completo} cancelada exitosamente.')
        
        # Redirigir según el parámetro 'next' o a la lista de consultas
        next_url = request.POST.get('next') or request.GET.get('next') or reverse('consultas_lista')
        return redirect(next_url)




class CitaPermisoMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.rol in ('medico', 'asistente', 'admin')


class CitaListView(CitaPermisoMixin, ListView):
    """Vista de lista de citas con filtrado por consultorio y agrupación por estado"""
    model = Cita
    template_name = 'PAGES/citas/lista.html'
    context_object_name = 'citas'
    paginate_by = 20

    def get_queryset(self):
        marcar_citas_vencidas()
        user = self.request.user

        # 1. Filtrar por consultorio del usuario / 5. Admin ve todas, otros solo su consultorio
        if user.rol == 'admin':
            queryset = Cita.objects.all()
        elif user.rol in ('medico', 'asistente') and user.consultorio:
            queryset = Cita.objects.filter(consultorio=user.consultorio)
        else:
            queryset = Cita.objects.none()

        # Aplicar filtros del formulario
        filtro_form = CitaFiltroForm(self.request.GET, user=user)
        if filtro_form.is_valid():
            cd = filtro_form.cleaned_data
            
            if cd.get('buscar'):
                queryset = queryset.filter(
                    Q(paciente__nombre_completo__icontains=cd['buscar']) |
                    Q(numero_cita__icontains=cd['buscar']) |
                    Q(motivo__icontains=cd['buscar'])
                )
            
            if cd.get('fecha'):
                queryset = queryset.filter(fecha_hora__date=cd['fecha'])
            if cd.get('estado'):
                queryset = queryset.filter(estado=cd['estado'])
            if cd.get('medico'):
                queryset = queryset.filter(medico_asignado=cd['medico'])

        return queryset.select_related(
            'paciente', 'consultorio', 'medico_asignado', 'medico_preferido'
        ).order_by('fecha_hora')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        user = self.request.user
        
        # 3. Agrupar por: Sin asignar, Asignadas, Completadas
        grupos = {
            'sin_asignar': queryset.filter(
                medico_asignado__isnull=True,
                estado__in=['programada', 'confirmada', 'en_espera']
            ),
            'asignadas': queryset.filter(
                medico_asignado__isnull=False,
                estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
            ),
            'completadas': queryset.filter(estado='completada'),
            'canceladas': queryset.filter(estado__in=['cancelada', 'no_asistio']),
        }
        
        # 2. Estadísticas de estado de asignación
        hoy = timezone.now().date()
        stats = {
            'total': queryset.count(),
            'hoy': queryset.filter(fecha_hora__date=hoy).count(),
            'sin_asignar': grupos['sin_asignar'].count(),
            'asignadas': grupos['asignadas'].count(),
            'completadas': grupos['completadas'].count(),
            'vencidas': queryset.filter(
                fecha_hora__lt=timezone.now(),
                estado__in=['programada', 'confirmada']
            ).count(),
        }
        
        # Próximas citas sin asignar (alertas)
        citas_urgentes = grupos['sin_asignar'].filter(
            fecha_hora__gte=timezone.now(),
            fecha_hora__lte=timezone.now() + timedelta(hours=2)
        )[:5]
        
        # 4. Determinar permisos para botones
        permisos = {
            'puede_tomar': user.rol == 'medico',
            'puede_asignar': user.rol == 'admin',
            'puede_liberar': user.rol in ['admin', 'medico'],
            'puede_crear': True,
        }
        
        # Médicos disponibles para filtros
        if user.rol == 'admin':
            medicos_disponibles = Usuario.objects.filter(rol='medico', is_active=True)
        elif user.consultorio:
            medicos_disponibles = Usuario.objects.filter(
                rol='medico',
                consultorio=user.consultorio,
                is_active=True
            )
        else:
            medicos_disponibles = Usuario.objects.none()

        context.update({
            'filtro_form': CitaFiltroForm(self.request.GET, user=user),
            'grupos': grupos,
            'stats': stats,
            'citas_urgentes': citas_urgentes,
            'permisos': permisos,
            'medicos_disponibles': medicos_disponibles,
            'usuario': user,
            'hoy': hoy,
        })
        
        return context


@login_required
def cambiar_estado_cita(request, cita_id):
    """Vista AJAX para cambiar el estado de una cita"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    
    try:
        cita = get_object_or_404(Cita, id=cita_id)
        
        # Verificar permisos
        if not puede_editar_cita(request.user, cita):
            return JsonResponse({'success': False, 'message': 'Sin permisos para editar esta cita'})
        
        nuevo_estado = request.POST.get('estado')
        motivo = request.POST.get('motivo', '')
        
        if nuevo_estado not in dict(Cita.ESTADO_CHOICES):
            return JsonResponse({'success': False, 'message': 'Estado inválido'}, status=400)
        
        # Cambiar estado
        estado_anterior = cita.estado
        cita.estado = nuevo_estado
        
        if motivo:
            cita.motivo_cancelacion = motivo
        
        if nuevo_estado == 'cancelada':
            cita.fecha_cancelacion = timezone.now()
        elif nuevo_estado == 'confirmada':
            cita.fecha_confirmacion = timezone.now()
        
        cita.actualizado_por = request.user
        cita.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Estado cambiado de {estado_anterior} a {nuevo_estado}',
            'nuevo_estado': cita.get_estado_display()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)



@login_required
def citas_calendario_data(request):
    """Datos JSON para el calendario de citas"""
    user = request.user
    
    # Filtros
    consultorio_id = request.GET.get('consultorio')
    medico_id = request.GET.get('medico')
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    # Query base según rol
    if user.rol == 'admin':
        citas = Cita.objects.all()
    elif user.rol in ('medico', 'asistente'):
        citas = Cita.objects.filter(consultorio=user.consultorio)
    else:
        citas = Cita.objects.none()
    
    # Aplicar filtros
    if consultorio_id:
        citas = citas.filter(consultorio_id=consultorio_id)
    
    if medico_id:
        citas = citas.filter(medico_asignado_id=medico_id)
    
    if start:
        start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
        citas = citas.filter(fecha_hora__gte=start_date)
    
    if end:
        end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
        citas = citas.filter(fecha_hora__lte=end_date)
    
    # Preparar datos para FullCalendar
    events = []
    for cita in citas.select_related('paciente', 'consultorio', 'medico_asignado'):
        color = get_color_by_estado(cita.estado)
        
        events.append({
            'id': str(cita.id),
            'title': f"{cita.paciente.nombre_completo}",
            'start': cita.fecha_hora.isoformat(),
            'end': (cita.fecha_hora + timedelta(minutes=cita.duracion)).isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'numero_cita': cita.numero_cita,
                'paciente': cita.paciente.nombre_completo,
                'consultorio': cita.consultorio.nombre,
                'medico': cita.medico_asignado.get_full_name() if cita.medico_asignado else 'Sin asignar',
                'estado': cita.get_estado_display(),
                'tipo': cita.get_tipo_cita_display(),
                'motivo': cita.motivo,
                'telefono': cita.telefono_contacto,
                'duracion': cita.duracion,
                'sin_medico': not cita.medico_asignado,
            }
        })
    
    return JsonResponse(events, safe=False)


def get_color_by_estado(estado):
    """Retorna color para el calendario según el estado"""
    colors = {
        'programada': '#6c757d',      # Gris
        'confirmada': '#0d6efd',      # Azul
        'en_espera': '#ffc107',       # Amarillo
        'en_atencion': '#fd7e14',     # Naranja
        'completada': '#198754',      # Verde
        'cancelada': '#dc3545',       # Rojo
        'no_asistio': '#6f42c1',      # Púrpura
        'reprogramada': '#20c997',    # Teal
    }
    return colors.get(estado, '#6c757d')


def puede_editar_cita(user, cita):
    """Verifica si el usuario puede editar la cita"""
    if user.rol == 'admin':
        return True
    elif user.rol == 'medico':
        return (
            cita.medico_asignado == user
            and cita.estado in ['programada', 'confirmada']
        )
    return False


# ═══════════════════════════════════════════════════════════════
# 📊 VISTAS AJAX PARA ESTADÍSTICAS
# ═══════════════════════════════════════════════════════════════

@login_required
def ajax_dashboard_stats(request):
    """Vista AJAX para estadísticas del dashboard"""
    user = request.user
    
    if user.rol == 'admin':
        citas = Cita.objects.all()
    elif user.rol in ('medico', 'asistente'):
        citas = Cita.objects.filter(consultorio=user.consultorio)
    else:
        citas = Cita.objects.none()
    
    hoy = timezone.now().date()
    
    stats = {
        'total_citas': citas.count(),
        'citas_hoy': citas.filter(fecha_hora__date=hoy).count(),
        'citas_pendientes': citas.filter(estado__in=['programada', 'confirmada']).count(),
        'citas_completadas': citas.filter(estado='completada').count(),
        'citas_canceladas': citas.filter(estado='cancelada').count(),
        'citas_en_espera': citas.filter(estado='en_espera').count(),
        'por_estado': dict(citas.values('estado').annotate(count=Count('id')).values_list('estado', 'count')),
        'por_tipo': dict(citas.values('tipo_cita').annotate(count=Count('id')).values_list('tipo_cita', 'count')),
        'por_prioridad': dict(citas.values('prioridad').annotate(count=Count('id')).values_list('prioridad', 'count')),
    }
    
    return JsonResponse(stats)


class CitaPermisoMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.rol in ('medico', 'asistente', 'admin')


class CitaCreateView(NextRedirectMixin, CitaPermisoMixin, CreateView):
    """Vista para crear nueva cita asignada al consultorio"""
    model = Cita
    form_class = CitaForm
    template_name = 'PAGES/citas/crear.html'
    success_url = reverse_lazy('citas_lista')

    def get_initial(self):
        initial = super().get_initial()
        fecha_str = self.request.GET.get('fecha')
        if fecha_str:
            try:
                initial['fecha'] = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        cita = form.save(commit=False)
        user = self.request.user
        
        # 1. Asignar automáticamente el consultorio según el usuario
        if user.rol == 'asistente' and user.consultorio:
            cita.consultorio = user.consultorio
        elif user.rol == 'medico' and user.consultorio:
            cita.consultorio = user.consultorio
        elif user.rol == 'admin':
            # Admin debe seleccionar consultorio en el form
            if not cita.consultorio:
                messages.error(self.request, 'Debe seleccionar un consultorio.')
                return self.form_invalid(form)
        
        # 2. No asignar médico inicialmente (medico_asignado = None)
        cita.medico_asignado = None
        
        # 3. Validar que el consultorio tenga médicos disponibles
        medicos_disponibles = Usuario.objects.filter(
            rol='medico',
            consultorio=cita.consultorio,
            is_active=True
        ).count()
        
        if medicos_disponibles == 0:
            messages.error(
                self.request, 
                f'El consultorio {cita.consultorio.nombre} no tiene médicos disponibles.'
            )
            return self.form_invalid(form)
        
        # Validar conflictos de horario en el consultorio
        conflictos = Cita.objects.filter(
            consultorio=cita.consultorio,
            fecha_hora__date=cita.fecha_hora.date(),
            fecha_hora__time=cita.fecha_hora.time(),
            estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
        ).exclude(pk=cita.pk if cita.pk else None)
        
        if conflictos.exists():
            messages.warning(
                self.request,
                f'Ya existe una cita programada en {cita.consultorio.nombre} '
                f'para {cita.fecha_hora.strftime("%d/%m/%Y a las %H:%M")}. '
                f'Se creará como cita adicional.'
            )
        
        # Asignar usuario creador
        cita.creado_por = user
        cita.save()
        
        messages.success(
            self.request, 
            f'Cita {cita.numero_cita} creada exitosamente para {cita.consultorio.nombre}. '
            f'Los médicos del consultorio podrán tomarla.'
        )
        
        return super().form_valid(form)

    def get_success_url(self):
        if self.request.user.rol == "asistente":
            return reverse("citas_lista")
        return super().get_success_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Obtener médicos disponibles del consultorio para mostrar como referencia
        if user.consultorio:
            medicos_consultorio = Usuario.objects.filter(
                rol='medico',
                consultorio=user.consultorio,
                is_active=True
            )
            context['medicos_consultorio'] = medicos_consultorio
        
        context.update({
            'titulo': 'Nueva Cita',
            'accion': 'Crear',
            'usuario': user,
            'next': self.request.GET.get('next') or self.request.POST.get('next', self.success_url),
        })
        return context


class CitaUpdateView(NextRedirectMixin, CitaPermisoMixin, UpdateView):
    """Vista para editar cita"""
    model = Cita
    form_class = CitaForm
    template_name = 'PAGES/citas/editar.html'
    success_url = reverse_lazy('citas_lista')

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol == 'asistente':
            messages.error(request, 'No tienes permiso para editar citas.')
            return redirect('citas_lista')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        # Verificar permisos específicos para editar
        if not super().test_func():
            return False
        
        cita = self.get_object()
        user = self.request.user
        
        if user.rol == 'admin':
            return True
        elif user.rol == 'asistente':
            return (cita.consultorio == user.consultorio and 
                   cita.estado in ['programada', 'confirmada'])
        elif user.rol == 'medico':
            return (cita.medico_asignado == user and 
                   cita.estado in ['programada', 'confirmada'])
        
        return False

    def form_valid(self, form):
        messages.success(self.request, f'Cita {self.object.numero_cita} actualizada exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'titulo': f'Editar Cita {self.object.numero_cita}',
            'accion': 'Actualizar',
            'usuario': self.request.user,
        })
        return context


# views_citas.py
class CitaDeleteView(NextRedirectMixin, CitaPermisoMixin, DeleteView):
    model               = Cita
    context_object_name = "cita"          #  ←  <<=====
    template_name       = "PAGES/citas/eliminar.html"
    success_url         = reverse_lazy("citas_lista")

    def test_func(self):
        return super().test_func() and self.request.user.rol == "admin"

    def delete(self, request, *args, **kwargs):
        cita = self.get_object()
        if hasattr(cita, "consulta"):
            messages.error(request, "No se puede eliminar una cita con consulta asociada.")
            return redirect(self.success_url)

        messages.success(request, f"Cita {cita.numero_cita} eliminada.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        return ctx


class CitaDetailView(CitaPermisoMixin, DetailView):
    """Vista de detalle de cita"""
    model = Cita
    template_name = 'PAGES/citas/detalle.html'
    context_object_name = 'cita'

    def test_func(self):
        if not super().test_func():
            return False
        
        cita = self.get_object()
        user = self.request.user
        
        # Verificar permisos de visualización
        if user.rol == 'admin':
            return True
        elif user.rol == 'medico':
            return (cita.consultorio == user.consultorio or 
                   cita.medico_asignado == user)
        elif user.rol == 'asistente':
            return cita.consultorio == user.consultorio
        
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cita = self.get_object()
        user = self.request.user
        
        # Obtener médicos disponibles para asignación
        medicos_disponibles = cita.medicos_disponibles
        
        # Verificar si hay consulta asociada
        consulta = None
        try:
            consulta = cita.consulta
        except:
            pass
        
        context.update({
            'consulta': consulta,
            'medicos_disponibles': medicos_disponibles,
            'puede_asignar_medico': (cita.puede_asignar_medico and
                                   user.rol in ['admin', 'asistente']),
            'puede_tomar_cita': self._puede_tomar_cita(user, cita),
            'puede_editar': self._puede_editar_cita(user, cita),
            'usuario': user,
            'now': timezone.now(),
        })
        
        return context

    def _puede_tomar_cita(self, user, cita):
        """Verifica si el médico puede tomar la cita"""
        return (user.rol == 'medico' and 
                user.consultorio == cita.consultorio and
                not cita.medico_asignado and
                cita.estado in ['programada', 'confirmada'])

    def _puede_editar_cita(self, user, cita):
        """Verifica si el usuario puede editar la cita"""
        if user.rol == 'admin':
            return True
        elif user.rol == 'medico':
            return (
                cita.medico_asignado == user
                and cita.estado in ['programada', 'confirmada']
            )
        return False


# ═══════════════════════════════════════════════════════════════
# 🕐 VISTA AJAX PARA HORARIOS
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# 🩺 VISTA PARA SIGNOS VITALES
# ═══════════════════════════════════════════════════════════════

@login_required
def ver_perfil(request):
    """Vista para ver el perfil del usuario actual"""
    
    context = {
        'usuario': request.user,
        'title': 'Mi Perfil'
    }
    
    return render(request, 'PAGES/perfil/ver.html', context)


@login_required
def editar_perfil(request):
    """Vista para que los usuarios editen su propio perfil"""
    
    if request.method == 'POST':
        form = EditarPerfilForm(request.POST, request.FILES, instance=request.user)
        
        if form.is_valid():
            # Guardar cambios
            user = form.save()
            
            # Si cambió la contraseña, mantener la sesión activa
            if form.cleaned_data.get('cambiar_password'):
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, '✅ Perfil actualizado correctamente. Su contraseña ha sido cambiada.')
            else:
                messages.success(request, '✅ Perfil actualizado correctamente.')

            # Crear notificación
            try:
                NotificationManager.crear_notificacion(
                    usuario=user,
                    tipo='success',
                    titulo='Perfil actualizado',
                    mensaje='Tu perfil ha sido actualizado exitosamente.',
                    categoria='sistema',
                    objeto_relacionado=user
                )
            except Exception as e:
                print(f'Error al crear notificación perfil: {e}')

            return redirect_next(request, 'ver_perfil')
    else:
        form = EditarPerfilForm(instance=request.user)

    context = {
        'usuario': request.user,
        'form': form,
        'title': 'Editar Perfil'
    }
    return render(request, 'PAGES/perfil/editar.html', context)
