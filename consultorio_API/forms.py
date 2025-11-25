from __future__ import annotations
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import *
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils import timezone
from django.conf import settings


# ───── Python / typing ──────────────────────────────────────────────────
from collections.abc import Sequence
from datetime import datetime, timedelta, time
from typing import Any
from pathlib import Path

# ───── Django ───────────────────────────────────────────────────────────
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Min, Q

# ───── Modelos / utilidades internas ───────────────────────────────────
from .models import Cita, Consultorio, Paciente, Usuario
from .utils_horarios import obtener_horarios_disponibles_para_select


# ───────────────────────────────────────────────
# USUARIOS
# ───────────────────────────────────────────────

class RegistroUsuarioForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = [
            "username", "first_name", "last_name",
            "email", "telefono", "rol",
            "cedula_profesional", "institucion_cedula",
            "consultorio", "foto"
        ]
        widgets = {
            fname: forms.TextInput(attrs={"class": "form-control"})
            for fname in [
                "username", "first_name", "last_name",
                "email", "telefono", "cedula_profesional",
                "institucion_cedula"
            ]
        } | {
            "rol": forms.Select(attrs={"class": "form-select"}),
            "consultorio": forms.Select(attrs={"class": "form-select"}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control"})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs["class"] = "form-control"
        self.fields["password2"].widget.attrs["class"] = "form-control"



class EditarUsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            "username", "first_name", "last_name",
            "email", "telefono", "rol",
            "cedula_profesional", "institucion_cedula",
            "consultorio","foto"
        ]
        widgets = {
            fname: forms.TextInput(attrs={"class": "form-control"})
            for fname in [
                "username", "first_name", "last_name",
                "email", "telefono", "cedula_profesional",
                "institucion_cedula"
            ]
        } | {
            "rol": forms.Select(attrs={"class": "form-select"}),
            "consultorio": forms.Select(attrs={"class": "form-select"}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control"})
        }


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Usuario", max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
# ═══════════════════════════════════════════════════════════════
# 📋 FORMULARIOS DE CITAS - SISTEMA POR CONSULTORIO
# ═══════════════════════════════════════════════════════════════

class CitaFiltroForm(forms.Form):
    """Formulario simplificado para filtrar citas"""

    buscar = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre, motivo, folio…"}
        ),
    )

    fecha = forms.DateField(
        required=False,
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    estado = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=[("", "Todos")] + list(Cita.ESTADO_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    medico = forms.ModelChoiceField(
        required=False,
        queryset=Usuario.objects.filter(rol="medico", is_active=True),
        label="Médico",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Usuario.objects.filter(rol="medico", is_active=True)
        if user and user.rol != "admin" and user.consultorio:
            qs = qs.filter(consultorio=user.consultorio)
        self.fields["medico"].queryset = qs.order_by("first_name", "last_name")

    
class ConsultaFiltroForm(forms.Form):
    """Formulario para filtrar consultas"""

    buscar = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre o folio…"}),
    )

    fecha = forms.DateField(
        required=False,
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    estado = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=[("", "Todos")] + list(Consulta.ESTADO_OPCIONES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    medico = forms.ModelChoiceField(
        required=False,
        queryset=Usuario.objects.filter(rol="medico", is_active=True),
        label="Médico",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Usuario.objects.filter(rol="medico", is_active=True)
        if user and user.rol != "admin" and user.consultorio:
            qs = qs.filter(consultorio=user.consultorio)
        self.fields["medico"].queryset = qs.order_by("first_name", "last_name")
# ═══════════════════════════════════════════════════════════════
# 👥 FORMULARIOS DE PACIENTES
# ═══════════════════════════════════════════════════════════════

class PacienteForm(forms.ModelForm):
    """Formulario para crear/editar pacientes"""
    
    class Meta:
        model = Paciente
        fields = [
            'nombre_completo', 'fecha_nacimiento', 'sexo', 'telefono',
            'correo', 'direccion', 'consultorio', 'foto'
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo del paciente'
            }),
            'fecha_nacimiento': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'sexo': forms.Select(attrs={'class': 'form-select'}),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+52-555-0000'
            }),
            'correo': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@ejemplo.com'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dirección completa'
            }),
            'consultorio': forms.Select(attrs={
                'class': 'form-select'
            }),
            'foto': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        labels = {
            'nombre_completo': 'Nombre Completo',
            'fecha_nacimiento': 'Fecha de Nacimiento',
            'sexo': 'Sexo',
            'telefono': 'Teléfono',
            'correo': 'Correo Electrónico',
            'direccion': 'Dirección',
            'consultorio': 'Consultorio Asignado',
            'foto': 'Foto del Paciente',
        }

    def __init__(self, *args, user: Usuario | None = None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['foto'].required = False
        self.fields['consultorio'].required = False

        if user and user.rol == 'medico':
            if user.consultorio:
                self.fields['consultorio'].queryset = Consultorio.objects.filter(pk=user.consultorio.pk)
                self.fields['consultorio'].initial = user.consultorio
                self.fields['consultorio'].widget = forms.HiddenInput()
            else:
                self.fields['consultorio'].queryset = Consultorio.objects.none()
        elif user and (user.is_superuser or user.rol == 'admin'):
            self.fields['consultorio'].queryset = Consultorio.objects.all().order_by('nombre')
        else:
            self.fields['consultorio'].queryset = Consultorio.objects.none()
            self.fields['consultorio'].widget = forms.HiddenInput()



class ExpedienteForm(forms.ModelForm):
    """Formulario para expedientes médicos"""
    
    class Meta:
        model = Expediente
        fields = ['notas_generales']
        widgets = {
            'notas_generales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Notas generales del expediente...'
            }),
        }
        labels = {
            'notas_generales': 'Notas Generales',
        }


class AntecedenteForm(forms.ModelForm):
    """Formulario para antecedentes médicos"""

    def __init__(self, *args, expediente=None, **kwargs):
        self.expediente = expediente
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.fecha_diagnostico:
            self.initial.setdefault(
                "fecha_diagnostico",
                self.instance.fecha_diagnostico.strftime("%Y-%m-%d"),
            )
    
    class Meta:
        model = Antecedente
        fields = [
            'tipo', 'descripcion', 'fecha_diagnostico', 'severidad', 
            'estado_actual', 'notas'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción del antecedente...'
            }),
            'fecha_diagnostico': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),
            'severidad': forms.Select(attrs={'class': 'form-select'}),
            'estado_actual': forms.Select(attrs={'class': 'form-select'}),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas adicionales...'
            }),
        }
        input_formats = {
            'fecha_diagnostico': ['%Y-%m-%d'],
        }
        labels = {
            'tipo': 'Tipo de Antecedente',
            'descripcion': 'Descripción',
            'fecha_diagnostico': 'Fecha de Diagnóstico',
            'severidad': 'Severidad',
            'estado_actual': 'Estado Actual',
            'notas': 'Notas',
        }

    def clean(self):
        cleaned = super().clean()
        expediente = self.expediente or getattr(self.instance, "expediente", None)
        tipo = cleaned.get("tipo")
        descripcion = cleaned.get("descripcion")
        if expediente and tipo == "alergico" and descripcion:
            qs = Antecedente.objects.filter(
                expediente=expediente,
                tipo="alergico",
                descripcion__iexact=descripcion,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("descripcion", "Esta alergia ya está registrada.")
        return cleaned


class MedicamentoActualForm(forms.ModelForm):
    """Formulario para medicamentos actuales"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.inicio:
                self.initial.setdefault('inicio', self.instance.inicio.strftime('%Y-%m-%d'))
            if self.instance.fin:
                self.initial.setdefault('fin', self.instance.fin.strftime('%Y-%m-%d'))
    
    class Meta:
        model = MedicamentoActual
        fields = [
            'nombre', 'principio_activo', 'dosis', 'frecuencia',
            'via_administracion', 'proposito', 'inicio', 'fin', 'prescrito_por', 'notas'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre comercial del medicamento'
            }),
            'principio_activo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Principio activo'
            }),
            'dosis': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 500 mg'
            }),
            'frecuencia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Cada 8 horas'
            }),
            'via_administracion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vía de administración'
            }),
            'proposito': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Para qué se toma'
            }),
            'inicio': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'fin': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'prescrito_por': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Médico que lo prescribió'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas adicionales...'
            }),
        }
        labels = {
            'nombre': 'Nombre del Medicamento',
            'principio_activo': 'Principio Activo',
            'dosis': 'Dosis',
            'frecuencia': 'Frecuencia',
            'via_administracion': 'Vía de Administración',
            'proposito': 'Propósito',
            'inicio': 'Fecha de Inicio',
            'fin': 'Fecha de Fin',
            'prescrito_por': 'Prescrito por',
            'notas': 'Notas',
        }

        input_formats = {
            'inicio': ['%Y-%m-%d'],
            'fin': ['%Y-%m-%d'],
        }



# ───────────────────────────── helpers / constantes ────────────────
ESTADOS_ACTIVOS = ("programada", "confirmada", "en_espera", "en_atencion")
PASO_MIN = 15
DUR_CHOICES = [(str(m), f"{m} min") for m in range(PASO_MIN, 121, PASO_MIN)]


def _fecha_hora_from_fields(fecha, hh_mm: str) -> datetime:
    """Construye un ``datetime`` y lo hace aware solo si ``USE_TZ``."""
    h, m = map(int, hh_mm.split(":"))
    dt = datetime.combine(fecha, time(hour=h, minute=m))
    if settings.USE_TZ and timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


# ─────────────────────────────────── CitaForm ───────────────────────
class CitaForm(forms.ModelForm):
    # ---------- selectores ----------
    consultorio = forms.ModelChoiceField(
        queryset=Consultorio.objects.all(),
        label=_("Consultorio"),
        widget=forms.Select(attrs={"class": "form-select select2"}),
    )
    paciente = forms.ModelChoiceField(
        queryset=Paciente.objects.all(),
        label=_("Paciente"),
        widget=forms.Select(attrs={"class": "form-select select2"}),
    )
    medico_preferido = forms.ModelChoiceField(
        required=False,
        queryset=Usuario.objects.filter(rol="medico", is_active=True),
        label=_("Médico preferido"),
        widget=forms.Select(attrs={"class": "form-select select2"}),
    )
    cita_anterior = forms.ModelChoiceField(
        required=False,
        queryset=Cita.objects.none(),
        label="Cita anterior",
        widget=forms.Select(attrs={"class": "form-select select2"}),
    )

    # ---------- fecha / hora / duración ----------
    fecha = forms.DateField(
        label=_("Fecha"),
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"},
            format="%Y-%m-%d",
        ),
        input_formats=["%Y-%m-%d"],
    )
    hora = forms.ChoiceField(
        label=_("Hora"),
        choices=[("", "— Seleccione una hora —")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    duracion = forms.ChoiceField(
        label=_("Duración (min)"),
        choices=DUR_CHOICES,
        initial=str(30),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # ---------- Meta ----------
    class Meta:
        model = Cita
        exclude = (
            "fecha_hora", "numero_cita", "estado", "observaciones_medicas",
            "fecha_confirmacion", "fecha_cancelacion",
            "fecha_asignacion_medico", "recordatorio_enviado",
            "fecha_recordatorio", "motivo_cancelacion",
            "fecha_creacion", "fecha_actualizacion",
            "creado_por", "actualizado_por",
        )

    # ───────────────────────── constructor ──────────────────────────
    def __init__(self, *args: Any, user: Usuario | None = None, paciente_fijo: Paciente | None = None, **kwargs: Any):
        self._user = user
        self.paciente_fijo = paciente_fijo
        kwargs.pop("user", None)
        kwargs.pop("paciente_fijo", None)
        super().__init__(*args, **kwargs)

        if paciente_fijo:
            self.fields["paciente"].initial = paciente_fijo
            self.fields["paciente"].queryset = Paciente.objects.filter(pk=paciente_fijo.pk)
            self.fields["paciente"].widget = forms.HiddenInput()
            self.paciente_nombre = paciente_fijo.nombre_completo

        # preparar opciones de cita anterior según el paciente
        try:
            paciente = self.instance.paciente
        except ObjectDoesNotExist:
            paciente = None
        if not paciente:
            paciente = paciente_fijo
        if not paciente:
            pid = self.data.get("paciente") or self.initial.get("paciente")
            try:
                paciente = Paciente.objects.get(pk=int(pid))
            except (TypeError, ValueError, Paciente.DoesNotExist):
                paciente = None

        if paciente:
            qs_prev = Cita.objects.filter(paciente=paciente).exclude(id=self.instance.id)

            limite_dt = None
            if self.instance.pk and self.instance.fecha_hora:
                limite_dt = self.instance.fecha_hora
            else:
                fecha_val = self.data.get("fecha") or self.initial.get("fecha")
                hora_val = self.data.get("hora") or self.initial.get("hora")
                if fecha_val:
                    try:
                        fecha_dt = datetime.strptime(fecha_val, "%Y-%m-%d").date()
                        if hora_val:
                            limite_dt = _fecha_hora_from_fields(fecha_dt, hora_val)
                        else:
                            limite_dt = datetime.combine(fecha_dt, time.min)
                            if settings.USE_TZ and timezone.is_naive(limite_dt):
                                limite_dt = timezone.make_aware(limite_dt)
                    except ValueError:
                        limite_dt = None

            if limite_dt:
                qs_prev = qs_prev.filter(fecha_hora__lt=limite_dt)

            qs_prev = qs_prev.order_by("fecha_hora")
            self.fields["cita_anterior"].queryset = qs_prev
            self.fields["cita_anterior"].empty_label = (
                "No hay citas anteriores" if not qs_prev.exists() else "---------"
            )
        else:
            self.fields["cita_anterior"].queryset = Cita.objects.none()
            self.fields["cita_anterior"].empty_label = "No hay citas anteriores"

        # edición
        if self.instance.pk and self.instance.consultorio_id and self.instance.fecha_hora:
            self._set_hora_choices(
                consultorio_id=self.instance.consultorio_id,
                fecha_str=self.instance.fecha_hora.date().isoformat(),
                duracion_str=self.instance.duracion or 30,
                excluir_id=self.instance.pk,
            )
            self.initial.setdefault(
                "fecha", self.instance.fecha_hora.date().isoformat()
            )
            self.initial["hora"] = self.instance.fecha_hora.strftime("%H:%M")
            self.initial["duracion"] = str(self.instance.duracion or 30)

        # creación con POST parcial
        elif self.data.get("consultorio") and self.data.get("fecha") and self.data.get("duracion"):
            self._set_hora_choices(
                consultorio_id=self.data["consultorio"],
                fecha_str=self.data["fecha"],
                duracion_str=self.data["duracion"],
            )

    # ───────────────────── helper: llena select horas ───────────────
    def _set_hora_choices(
        self, *, consultorio_id, fecha_str, duracion_str, excluir_id=None
    ):
        try:
            consultorio = Consultorio.objects.get(pk=int(consultorio_id))
            dia = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            minutos = int(duracion_str)
        except (Consultorio.DoesNotExist, ValueError):
            return

        opciones = obtener_horarios_disponibles_para_select(
            consultorio=consultorio,
            dia=dia,
            duracion_requerida=minutos,
            excluir_id=excluir_id,
        )
        self.fields["hora"].choices = [("", "— Seleccione una hora —")] + [
            (o["value"], o["text"]) for o in opciones
        ]

    # ───────────────────────── clean_hora ───────────────────────────
    def clean_hora(self) -> str:
        valor = self.cleaned_data.get("hora")
        if not valor:
            raise ValidationError(_("Debe escoger una hora."))

        con = self.cleaned_data.get("consultorio")
        dia = self.cleaned_data.get("fecha")
        dur = int(self.cleaned_data.get("duracion"))

        opciones = obtener_horarios_disponibles_para_select(
            consultorio=con,
            dia=dia,
            duracion_requerida=dur,
            excluir_id=self.instance.pk,
        )
        libres = {o["value"] for o in opciones if o["estado"] == "libre"}
        if valor not in libres:
            raise ValidationError(_("La hora seleccionada ya no está disponible."))

        return valor

    # ───────────────────────── clean global ─────────────────────────
    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()

        con = cleaned.get("consultorio")
        dia = cleaned.get("fecha")
        hora = cleaned.get("hora")
        dur = cleaned.get("duracion")

        if not (con and dia and hora and dur):
            return cleaned

        dur_int = int(dur)
        inicio = _fecha_hora_from_fields(dia, hora)
        fin = inicio + timedelta(minutes=dur_int)

        solapa = (
            Cita.objects.filter(
                consultorio=con,
                estado__in=ESTADOS_ACTIVOS,
                fecha_hora__lt=fin,
            )
            .exclude(pk=self.instance.pk)
            .filter(fecha_hora__gte=inicio - timedelta(minutes=dur_int))
            .exists()
        )
        if solapa:
            raise ValidationError(_("La hora seleccionada se solapa con otra cita."))

        cleaned["fecha_hora"] = inicio
        cleaned["duracion"] = dur_int  # guarda como int
        return cleaned

    # ─────────────────────────── save() ─────────────────────────────
    def save(self, commit: bool = True) -> Cita:
        instance: Cita = super().save(commit=False)
        instance.fecha_hora = self.cleaned_data.get("fecha_hora")
        instance.duracion = self.cleaned_data.get("duracion")  # int
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ReprogramarCitaForm(forms.Form):
    fecha = CitaForm.base_fields['fecha']
    hora = CitaForm.base_fields['hora']

    def __init__(self, *args, cita: Cita, **kwargs):
        self.cita = cita
        super().__init__(*args, **kwargs)
        self.fields['fecha'].initial = cita.fecha_hora.date()
        self.fields['hora'].initial = cita.fecha_hora.strftime('%H:%M')
        self._set_hora_choices()

    def _set_hora_choices(self):
        opciones = obtener_horarios_disponibles_para_select(
            self.cita.consultorio,
            self.fields['fecha'].initial,
            self.cita.duracion,
            self.cita.id,
        )
        self.fields['hora'].choices = [('', '— Seleccione una hora —')] + [
            (o['value'], o['text']) for o in opciones
        ]

    def clean(self):
        cd = super().clean()
        if 'fecha' in cd and 'hora' in cd:
            dt = _fecha_hora_from_fields(cd['fecha'], cd['hora'])
            if dt <= timezone.now():
                raise ValidationError('La hora debe estar en el futuro')
            cd['fecha_hora'] = dt
        return cd

    def save(self):
        self.cita.fecha_hora = self.cleaned_data['fecha_hora']
        self.cita.estado = 'reprogramada'
        self.cita.save()
        return self.cita








class ConsultaSinCitaForm(forms.ModelForm):
    """
    Formulario para crear consultas sin cita - CORREGIDO
    """
    
    # Campo para programar para más tarde
    programar_para = forms.ChoiceField(
        choices=[
            ('ahora', 'Atender ahora'),
            ('30min', 'En 30 minutos'),
            ('1hora', 'En 1 hora'),
            ('2horas', 'En 2 horas'),
            ('personalizado', 'Horario personalizado'),
        ],
        initial='ahora',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="¿Cuándo debe ser atendido?"
    )
    
    # Campos para horario personalizado
    fecha_programada = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'min': timezone.now().date().isoformat()
        })
    )
    
    hora_programada = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control'
        })
    )

    # Campos adicionales para la consulta
    sintomas_principales = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Síntomas principales del paciente...'
        }),
        help_text="Síntomas que presenta el paciente"
    )

    es_urgente = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Marcar si es una consulta urgente"
    )

    observaciones_iniciales = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Observaciones iniciales...'
        }),
        help_text="Observaciones iniciales sobre el paciente"
    )

    class Meta:
        model = Consulta
        fields = [
            'paciente', 'medico', 'motivo_consulta', 'observaciones',
            'sintomas_principales', 'es_urgente', 'observaciones_iniciales'
        ]
        widgets = {
            'paciente': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Seleccionar paciente...'
            }),
            'medico': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_medico'
            }),
            'motivo_consulta': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Motivo principal de la consulta...',
                'required': True
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones adicionales...'
            }),
            'sintomas_principales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Síntomas principales del paciente...'
            }),
            'es_urgente': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'observaciones_iniciales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones iniciales...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['paciente'].queryset = Paciente.objects.all().order_by('nombre_completo')

        qs = Usuario.objects.filter(rol='medico', is_active=True)
        if self.user:
            if self.user.consultorio:
                qs = qs.filter(consultorio=self.user.consultorio)
            elif self.user.rol != 'admin':
                qs = Usuario.objects.none()
        else:
            qs = Usuario.objects.none()

        self.fields['medico'].queryset = qs.order_by('first_name', 'last_name')

    def clean(self):
        cleaned_data = super().clean()

        # Verificar si el paciente ya tiene una consulta "sin_cita" activa
        paciente = cleaned_data.get("paciente")
        if paciente:
            conflicto = Consulta.objects.filter(
                paciente=paciente,
                tipo="sin_cita",
                estado__in=["espera", "en_progreso"],
            ).exists()

            if conflicto:
                raise ValidationError(
                    f"El paciente {paciente} ya tiene una consulta en espera o en progreso. "
                    "Finalízala antes de registrar otra."
                )

        programar_para = cleaned_data.get('programar_para')
        fecha_programada = cleaned_data.get('fecha_programada')
        hora_programada = cleaned_data.get('hora_programada')
        medico = cleaned_data.get('medico')
        
        # Validar horario personalizado
        if programar_para == 'personalizado':
            if not fecha_programada or not hora_programada:
                raise ValidationError("Debe especificar fecha y hora para horario personalizado.")
            
            fecha_hora_programada = datetime.combine(
                fecha_programada, hora_programada
            )
            if settings.USE_TZ and timezone.is_naive(fecha_hora_programada):
                fecha_hora_programada = timezone.make_aware(fecha_hora_programada)
            
            if fecha_hora_programada < timezone.now():
                raise ValidationError("No se puede programar en el pasado.")
            
            cleaned_data['fecha_hora_programada'] = fecha_hora_programada
        
        # Validar que el médico pertenezca al consultorio del usuario
        if medico and self.user and self.user.consultorio:
            if medico.consultorio != self.user.consultorio:
                raise ValidationError(
                    f"El médico {medico.get_full_name()} no pertenece a tu consultorio."
                )

        # Validar solapamientos cuando se programa para "ahora"
        if programar_para == 'ahora':
            consultorio = None
            if medico and medico.consultorio:
                consultorio = medico.consultorio
            elif self.user and self.user.consultorio:
                consultorio = self.user.consultorio

            if consultorio:
                inicio = timezone.now()
                fin = inicio + timedelta(minutes=30)

                # Revisar citas existentes
                citas = Cita.objects.filter(
                    consultorio=consultorio,
                    fecha_hora__lt=fin,
                    estado__in=[e[0] for e in Cita.ESTADO_CHOICES if e[0] != 'cancelada']
                )
                for c in citas:
                    c_fin = c.fecha_hora + timedelta(minutes=c.duracion)
                    if inicio < c_fin and fin > c.fecha_hora:
                        raise ValidationError('El horario se solapa con otra cita.')

                # Revisar consultas en espera o en progreso
                consultas = Consulta.objects.filter(
                    Q(medico__consultorio=consultorio) |
                    Q(cita__consultorio=consultorio) |
                    Q(asistente__consultorio=consultorio),
                    estado__in=['espera', 'en_progreso']
                )
                for con in consultas:
                    ini = con.fecha_atencion or (con.cita.fecha_hora if con.cita else con.fecha_creacion)
                    fin_con = ini + timedelta(minutes=30)
                    if inicio < fin_con and fin > ini:
                        raise ValidationError('El horario se solapa con otra consulta.')

        return cleaned_data

    def es_consulta_instantanea(self):
        """Determina si la consulta es instantánea (para atender ahora)"""
        programar_para = self.cleaned_data.get('programar_para', 'ahora')
        return programar_para == 'ahora'

    def save(self, commit=True):
        consulta = super().save(commit=False)
        
        # IMPORTANTE: Asegurar que se marque como sin cita
        consulta.tipo = 'sin_cita'
        consulta.cita = None  # Asegurar que no tenga cita asociada
        
        # Asignar asistente si el usuario actual es asistente
        if self.user and self.user.rol == 'asistente':
            consulta.asistente = self.user
        
        if commit:
            consulta.save()
        
        return consulta

    def get_fecha_hora_cita(self):
        """Calcular la fecha/hora para la cita automática"""
        programar_para = self.cleaned_data.get('programar_para', 'ahora')
        
        if programar_para == 'ahora':
            return timezone.now()
        elif programar_para == '30min':
            return timezone.now() + timedelta(minutes=30)
        elif programar_para == '1hora':
            return timezone.now() + timedelta(hours=1)
        elif programar_para == '2horas':
            return timezone.now() + timedelta(hours=2)
        elif programar_para == 'personalizado':
            return self.cleaned_data.get('fecha_hora_programada')

        return timezone.now()


class ConsultaMedicoForm(forms.ModelForm):
    """Formulario para que el médico registre detalles de la consulta"""

    class Meta:
        model = Consulta
        fields = [
            "motivo_consulta",
            "diagnostico",
            "tratamiento",
            "observaciones",
        ]
        widgets = {
            "motivo_consulta": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "diagnostico": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "tratamiento": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "observaciones": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }



class SignosVitalesForm(forms.ModelForm):
    """Formulario para signos vitales con ejemplos y explicaciones"""
    
    class Meta:
        model = SignosVitales
        fields = [
            'tension_arterial', 'frecuencia_cardiaca', 'frecuencia_respiratoria',
            'temperatura', 'peso', 'talla', 'circunferencia_abdominal',
            'alergias', 'sintomas'
        ]
        widgets = {
            'tension_arterial': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 120/80',
                'title': 'Presión arterial sistólica/diastólica en mmHg'
            }),
            'frecuencia_cardiaca': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 72',
                'min': '40',
                'max': '200',
                'title': 'Latidos por minuto (normal: 60-100 lpm)'
            }),
            'frecuencia_respiratoria': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 16',
                'min': '8',
                'max': '40',
                'title': 'Respiraciones por minuto (normal: 12-20 rpm)'
            }),
            'temperatura': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': 'Ej: 36.5',
                'min': '30',
                'max': '45',
                'title': 'Temperatura corporal en grados Celsius (normal: 36-37°C)'
            }),
            'peso': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': 'Ej: 70.5',
                'min': '1',
                'max': '300',
                'title': 'Peso corporal en kilogramos'
            }),
            'talla': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ej: 1.70',
                'min': '0.5',
                'max': '2.5',
                'title': 'Estatura en metros'
            }),
            'circunferencia_abdominal': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 85',
                'min': '30',
                'max': '200',
                'title': 'Perímetro abdominal en centímetros'
            }),
            'alergias': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ej: Penicilina, mariscos, polen. Escribir "NINGUNA" si no tiene alergias conocidas',
                'title': 'Alergias conocidas del paciente'
            }),
            'sintomas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ej: Dolor de cabeza, fiebre desde ayer, náuseas...',
                'title': 'Síntomas actuales que presenta el paciente'
            }),
        }
        labels = {
            'tension_arterial': 'Tensión Arterial (mmHg)',
            'frecuencia_cardiaca': 'Frecuencia Cardíaca (lpm)',
            'frecuencia_respiratoria': 'Frecuencia Respiratoria (rpm)',
            'temperatura': 'Temperatura (°C)',
            'peso': 'Peso (kg)',
            'talla': 'Talla (m)',
            'circunferencia_abdominal': 'Circunferencia Abdominal (cm)',
            'alergias': 'Alergias del Paciente',
            'sintomas': 'Síntomas o Padecimientos Actuales',
        }
        help_texts = {
            'tension_arterial': 'Formato: sistólica/diastólica (ej: 120/80)',
            'frecuencia_cardiaca': 'Latidos por minuto - Normal: 60-100 lpm',
            'frecuencia_respiratoria': 'Respiraciones por minuto - Normal: 12-20 rpm',
            'temperatura': 'Temperatura corporal - Normal: 36-37°C',
            'peso': 'Peso actual del paciente en kilogramos',
            'talla': 'Estatura del paciente en metros',
            'circunferencia_abdominal': 'Perímetro abdominal a nivel del ombligo',
            'alergias': 'Alergias conocidas o escribir "NINGUNA"',
            'sintomas': 'Síntomas actuales que presenta el paciente',
        }

    def clean_tension_arterial(self):
        """Validar formato de tensión arterial"""
        tension = self.cleaned_data.get('tension_arterial')
        if tension:
            # Validar formato sistólica/diastólica
            if '/' not in tension:
                raise ValidationError('Formato incorrecto. Use: sistólica/diastólica (ej: 120/80)')
            
            try:
                sistolica, diastolica = tension.split('/')
                sistolica = int(sistolica.strip())
                diastolica = int(diastolica.strip())
                
                if sistolica < 50 or sistolica > 250:
                    raise ValidationError('Presión sistólica fuera del rango normal (50-250)')
                if diastolica < 30 or diastolica > 150:
                    raise ValidationError('Presión diastólica fuera del rango normal (30-150)')
                if sistolica <= diastolica:
                    raise ValidationError('La presión sistólica debe ser mayor que la diastólica')
                    
            except ValueError:
                raise ValidationError('Use solo números. Formato: sistólica/diastólica (ej: 120/80)')
        
        return tension

    def clean_frecuencia_cardiaca(self):
        """Validar frecuencia cardíaca"""
        fc = self.cleaned_data.get('frecuencia_cardiaca')
        if fc and (fc < 40 or fc > 200):
            raise ValidationError('Frecuencia cardíaca fuera del rango normal (40-200 lpm)')
        return fc

    def clean_frecuencia_respiratoria(self):
        """Validar frecuencia respiratoria"""
        fr = self.cleaned_data.get('frecuencia_respiratoria')
        if fr and (fr < 8 or fr > 40):
            raise ValidationError('Frecuencia respiratoria fuera del rango normal (8-40 rpm)')
        return fr

    def clean_temperatura(self):
        """Validar temperatura"""
        temp = self.cleaned_data.get('temperatura')
        if temp and (temp < 30 or temp > 45):
            raise ValidationError('Temperatura fuera del rango normal (30-45°C)')
        return temp


# ═══════════════════════════════════════════════════════════════
# 💊 FORMULARIOS DE RECETAS
# ═══════════════════════════════════════════════════════════════

class RecetaForm(forms.ModelForm):
    """Formulario para recetas médicas"""

    valido_hasta_input_formats = ["%Y-%m-%d", "%d/%m/%Y"]

    class Meta:
        model = Receta
        fields = ['indicaciones_generales', 'valido_hasta', 'notas']
        widgets = {
            'indicaciones_generales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Indicaciones generales para el paciente...'
            }),
            'valido_hasta': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format="%Y-%m-%d",
            ),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas adicionales...'
            }),
        }
        labels = {
            'indicaciones_generales': 'Indicaciones Generales',
            'valido_hasta': 'Válido Hasta',
            'notas': 'Notas',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Mostrar fecha guardada o valor por defecto
        if self.instance and self.instance.pk and self.instance.valido_hasta:
            self.initial["valido_hasta"] = self.instance.valido_hasta.strftime("%Y-%m-%d")
        else:
            self.fields['valido_hasta'].initial = (
                self.instance.valido_hasta
                or timezone.now().date() + timedelta(days=30)
            )




class MedicamentoRecetadoForm(forms.ModelForm):
    """Formulario para medicamentos recetados"""
    
    class Meta:
        model = MedicamentoRecetado
        fields = [
            'nombre', 'principio_activo', 'dosis', 'frecuencia',
            'via_administracion', 'duracion', 'cantidad', 'indicaciones_especificas', 'codigo_barras'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre comercial'
            }),
            'principio_activo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Principio activo'
            }),
            'dosis': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 500 mg'
            }),
            'frecuencia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Cada 8 horas'
            }),
            'via_administracion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vía de administración'
            }),
            'duracion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 7 días'
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1',
                'placeholder': 'Cantidad total'
            }),
            'indicaciones_especificas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Indicaciones específicas...'
            }),
            'codigo_barras': forms.HiddenInput(),
        }
        labels = {
            'nombre': 'Nombre del Medicamento',
            'principio_activo': 'Principio Activo',
            'dosis': 'Dosis',
            'frecuencia': 'Frecuencia',
            'via_administracion': 'Vía de Administración',
            'duracion': 'Duración del Tratamiento',
            'cantidad': 'Cantidad',
            'indicaciones_especificas': 'Indicaciones Específicas',
        }


# ═══════════════════════════════════════════════════════════════
# 📦 CATÁLOGO DE MEDICAMENTOS
# ═══════════════════════════════════════════════════════════════


class MedicamentoCatalogoForm(forms.ModelForm):
    class Meta:
        model = MedicamentoCatalogo
        fields = [
            "nombre",
            "clave",
            "departamento",
            "categoria",
            "existencia",
            "precio",
            "imagen",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "clave": forms.TextInput(attrs={"class": "form-control"}),
            "departamento": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.TextInput(attrs={"class": "form-control"}),
            "existencia": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "precio": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": "0.01"}
            ),
            "imagen": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class ExcelUploadForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo de catálogo",
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".xlsx,.xls,.csv"}
        ),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data.get("archivo")
        if not archivo:
            raise ValidationError("Debe seleccionar un archivo.")
        ext = Path(archivo.name).suffix.lower()
        permitidas = {".xlsx", ".xls", ".csv"}
        if ext not in permitidas:
            raise ValidationError("Formato no soportado. Use .xlsx, .xls o .csv")
        return archivo


# ═══════════════════════════════════════════════════════════════
# 🔍 FORMULARIOS DE BÚSQUEDA Y FILTROS
# ═══════════════════════════════════════════════════════════════

class BusquedaPacienteForm(forms.Form):
    """Formulario para búsqueda de pacientes"""
    termino = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre, teléfono o correo...'
        }),
        label='Buscar Paciente'
    )


class FiltroConsultaForm(forms.Form):
    """Formulario para filtrar consultas"""
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Desde'
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Hasta'
    )
    estado = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los estados')] + Consulta.ESTADO_OPCIONES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Estado'
    )
    medico = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(rol='medico', is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Médico',
        empty_label='Todos los médicos'
    )


# ═══════════════════════════════════════════════════════════════
# ⏰ FORMULARIOS DE HORARIOS
# ═══════════════════════════════════════════════════════════════

class HorarioMedicoForm(forms.ModelForm):
    """Formulario para horarios de médicos"""

    dias = forms.MultipleChoiceField(
        choices=HorarioMedico.DIAS_SEMANA,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=False,
        label="Días de la Semana",
    )

    class Meta:
        model = HorarioMedico
        fields = ["medico", "consultorio", "hora_inicio", "hora_fin"]
        widgets = {
            "medico": forms.Select(attrs={"class": "form-select"}),
            "consultorio": forms.Select(attrs={"class": "form-select"}),
            "hora_inicio": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time", "class": "form-control"},
            ),
            "hora_fin": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time", "class": "form-control"},
            ),
        }
        labels = {
            "medico": "Médico",
            "consultorio": "Consultorio",
            "hora_inicio": "Hora de Inicio",
            "hora_fin": "Hora de Fin",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Filtrar médicos según el rol del usuario
            if user.rol == 'admin':
                self.fields['medico'].queryset = Usuario.objects.filter(rol='medico', is_active=True)
                self.fields['consultorio'].queryset = Consultorio.objects.all()
            elif user.rol == 'medico':
                self.fields['medico'].queryset = Usuario.objects.filter(id=user.id)
                self.fields['medico'].initial = user
                self.fields['medico'].widget.attrs['readonly'] = True
                if user.consultorio:
                    self.fields['consultorio'].queryset = Consultorio.objects.filter(id=user.consultorio.id)
                    self.fields['consultorio'].initial = user.consultorio

    def clean(self):
        cleaned_data = super().clean()
        hora_inicio = cleaned_data.get('hora_inicio')
        hora_fin = cleaned_data.get('hora_fin')
        
        if hora_inicio and hora_fin:
            if hora_inicio >= hora_fin:
                raise ValidationError("La hora de inicio debe ser anterior a la hora de fin.")
        
        return cleaned_data


# ═══════════════════════════════════════════════════════════════
# 🏥 FORMULARIOS DE CONSULTORIOS
# ═══════════════════════════════════════════════════════════════

class ConsultorioForm(forms.ModelForm):
    """Formulario para consultorios"""
    
    class Meta:
        model = Consultorio
        fields = ['nombre', 'ubicacion', 'capacidad_diaria', 'horario_apertura', 'horario_cierre']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del consultorio'
            }),
            'ubicacion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ubicación del consultorio'
            }),
            'capacidad_diaria': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Número de pacientes por día'
            }),
            'horario_apertura': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'horario_cierre': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
        }
        labels = {
            'nombre': 'Nombre del Consultorio',
            'ubicacion': 'Ubicación',
            'capacidad_diaria': 'Capacidad Diaria',
            'horario_apertura': 'Horario de Apertura',
            'horario_cierre': 'Horario de Cierre',
        }

    def clean(self):
        cleaned_data = super().clean()
        horario_apertura = cleaned_data.get('horario_apertura')
        horario_cierre = cleaned_data.get('horario_cierre')
        
        if horario_apertura and horario_cierre:
            if horario_apertura >= horario_cierre:
                raise ValidationError("El horario de apertura debe ser anterior al horario de cierre.")
        
        return cleaned_data


# ═══════════════════════════════════════════════════════════════
# 👤 FORMULARIOS DE USUARIOS
# ═══════════════════════════════════════════════════════════════

class UsuarioForm(forms.ModelForm):
    """Formulario para usuarios del sistema"""
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    password2 = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    
    class Meta:
        model = Usuario
        fields = [
            'username', 'first_name', 'last_name', 'email', 'rol',
            'telefono', 'cedula_profesional', 'institucion_cedula', 'consultorio', 'foto'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de usuario'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apellidos'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@ejemplo.com'
            }),
            'rol': forms.Select(attrs={'class': 'form-select'}),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'cedula_profesional': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de cédula profesional'
            }),
            'institucion_cedula': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Institución que otorgó la cédula'
            }),
            'consultorio': forms.Select(attrs={'class': 'form-select'}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'username': 'Nombre de Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo Electrónico',
            'rol': 'Rol',
            'telefono': 'Teléfono',
            'cedula_profesional': 'Cédula Profesional',
            'institucion_cedula': 'Institución de la Cédula',
            'consultorio': 'Consultorio Asignado',
            'foto': 'Foto',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si es edición, hacer la contraseña opcional
        if self.instance.pk:
            self.fields['password1'].label = 'Nueva contraseña'
            self.fields['password2'].label = 'Confirmar contraseña'
            self.fields['password1'].help_text = "Dejar en blanco para mantener la contraseña actual"
            self.fields['password2'].help_text = "Dejar en blanco para mantener la contraseña actual"

        # El campo de foto es opcional
        self.fields['foto'].required = False

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Las contraseñas no coinciden.")
        
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        
        if password:
            user.set_password(password)
        
        if commit:
            user.save()
        
        return user


class AsignarMedicoForm(forms.Form):
    """
    Formulario para asignar médicos a citas
    """
    
    medico = forms.ModelChoiceField(
        queryset=Usuario.objects.none(),
        empty_label="Seleccionar médico...",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        }),
        help_text="Médico que atenderá la cita"
    )
    
    notificar_medico = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Enviar notificación al médico"
    )
    
    observaciones = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Observaciones sobre la asignación...'
        })
    )

    def __init__(self, *args, **kwargs):
        cita = kwargs.pop('cita', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Configurar queryset de médicos según consultorio de la cita
        if cita and cita.consultorio:
            self.fields['medico'].queryset = Usuario.objects.filter(
                rol='medico',
                consultorio=cita.consultorio,
                is_active=True
            ).order_by('first_name', 'last_name')
        elif user and user.consultorio:
            self.fields['medico'].queryset = Usuario.objects.filter(
                rol='medico',
                consultorio=user.consultorio,
                is_active=True
            ).order_by('first_name', 'last_name')
        else:
            self.fields['medico'].queryset = Usuario.objects.none()
        
        # Si hay médico preferido, marcarlo como inicial
        if cita and cita.medico_preferido:
            self.fields['medico'].initial = cita.medico_preferido

    def clean_medico(self):
        medico = self.cleaned_data.get('medico')
        
        if not medico:
            raise ValidationError("Debe seleccionar un médico.")
        
        if medico.rol != 'medico':
            raise ValidationError("El usuario seleccionado no es médico.")
        
        if not medico.is_active:
            raise ValidationError("El médico seleccionado no está activo.")
        
        return medico


# ═══════════════════════════════════════════════════════════════
# 👤 FORMULARIO DE EDITAR PERFIL
# ═══════════════════════════════════════════════════════════════

class EditarPerfilForm(forms.ModelForm):
    """Formulario para que los usuarios editen su propio perfil"""
    
    # Campos opcionales para cambiar contraseña
    cambiar_password = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'cambiar_password'
        }),
        label='¿Desea cambiar su contraseña?'
    )
    
    password_actual = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese su contraseña actual'
        }),
        label='Contraseña Actual'
    )
    
    password_nueva = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nueva contraseña'
        }),
        label='Nueva Contraseña'
    )
    
    password_confirmacion = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirme la nueva contraseña'
        }),
        label='Confirmar Nueva Contraseña'
    )
    
    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'email', 'telefono', 
            'cedula_profesional', 'institucion_cedula', 'foto'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apellidos'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@ejemplo.com'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'cedula_profesional': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de cédula profesional'
            }),
            'institucion_cedula': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Institución que otorgó la cédula'
            }),
            'foto': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono',
            'cedula_profesional': 'Cédula Profesional',
            'institucion_cedula': 'Institución de la Cédula',
            'foto': 'Foto de Perfil',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        
        # Hacer campos opcionales según el rol
        if self.user and self.user.rol != 'medico':
            self.fields['cedula_profesional'].required = False
            self.fields['institucion_cedula'].required = False

    def clean(self):
        cleaned_data = super().clean()
        cambiar_password = cleaned_data.get('cambiar_password')
        password_actual = cleaned_data.get('password_actual')
        password_nueva = cleaned_data.get('password_nueva')
        password_confirmacion = cleaned_data.get('password_confirmacion')
        
        if cambiar_password:
            # Validar contraseña actual
            if not password_actual:
                raise ValidationError("Debe ingresar su contraseña actual.")
            
            if not self.user.check_password(password_actual):
                raise ValidationError("La contraseña actual es incorrecta.")
            
            # Validar nueva contraseña
            if not password_nueva:
                raise ValidationError("Debe ingresar una nueva contraseña.")
            
            if len(password_nueva) < 8:
                raise ValidationError("La nueva contraseña debe tener al menos 8 caracteres.")
            
            if password_nueva != password_confirmacion:
                raise ValidationError("Las contraseñas nuevas no coinciden.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Cambiar contraseña si se solicitó
        if self.cleaned_data.get('cambiar_password'):
            password_nueva = self.cleaned_data.get('password_nueva')
            if password_nueva:
                user.set_password(password_nueva)
        
        if commit:
            user.save()
        
        return user

MedicamentoRecetadoFormSet = inlineformset_factory(
    Receta,
    MedicamentoRecetado,
    fields=[
        "nombre", "principio_activo", "dosis", "frecuencia",
        "via_administracion", "duracion", "cantidad",
        "indicaciones_especificas", "codigo_barras",
    ],
    extra=1,
    can_delete=True,
)
