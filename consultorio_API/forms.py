from __future__ import annotations
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import *
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.utils import timezone


# ───── Python / typing ──────────────────────────────────────────────────
from collections.abc import Sequence
from datetime import datetime, timedelta, time
from typing import Any

# ───── Django ───────────────────────────────────────────────────────────
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

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
    """
    Formulario para filtrar citas - Usando solo campos que existen
    """
    
    buscar = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por paciente, número de cita o motivo...'
        })
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados')] + Cita.ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tipo_cita = forms.ChoiceField(
        choices=[('', 'Todos los tipos')] + Cita.TIPO_CITA_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    prioridad = forms.ChoiceField(
        choices=[('', 'Todas las prioridades')] + Cita.PRIORIDAD_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Filtro por estado de asignación
    estado_asignacion = forms.ChoiceField(
        choices=[
            ('', 'Todas las citas'),
            ('disponibles', 'Sin médico asignado'),
            ('asignadas', 'Con médico asignado'),
            ('preferidas', 'Con médico preferido'),
            ('vencidas', 'Vencidas sin asignar'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Filtrar por estado de asignación de médico"
    )
    
    # Filtro por médico asignado
    medico = forms.ModelChoiceField(
        queryset=Usuario.objects.none(),
        required=False,
        empty_label="Todos los médicos",
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Filtrar por médico asignado"
    )
    
    # Filtro por consultorio (solo para admin)
    consultorio = forms.ModelChoiceField(
        queryset=Consultorio.objects.all(),
        required=False,
        empty_label="Todos los consultorios",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Filtro por rango de tiempo
    rango_tiempo = forms.ChoiceField(
        choices=[
            ('', 'Cualquier fecha'),
            ('hoy', 'Hoy'),
            ('manana', 'Mañana'),
            ('esta_semana', 'Esta semana'),
            ('proximo_mes', 'Próximo mes'),
            ('vencidas', 'Citas vencidas'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Configurar queryset de médicos según usuario
        if user:
            if user.rol == 'admin':
                self.fields['medico'].queryset = Usuario.objects.filter(
                    rol='medico',
                    is_active=True
                ).order_by('first_name', 'last_name')
                # Admin puede ver filtro de consultorio
                self.fields['consultorio'].widget.attrs['style'] = ''
            elif user.consultorio:
                self.fields['medico'].queryset = Usuario.objects.filter(
                    rol='medico',
                    consultorio=user.consultorio,
                    is_active=True
                ).order_by('first_name', 'last_name')
                # Ocultar filtro de consultorio para no-admin
                self.fields['consultorio'].widget = forms.HiddenInput()
            else:
                self.fields['medico'].queryset = Usuario.objects.none()
                self.fields['consultorio'].widget = forms.HiddenInput()

    
# ═══════════════════════════════════════════════════════════════
# 👥 FORMULARIOS DE PACIENTES
# ═══════════════════════════════════════════════════════════════

class PacienteForm(forms.ModelForm):
    """Formulario para crear/editar pacientes"""
    
    class Meta:
        model = Paciente
        fields = [
            'nombre_completo', 'fecha_nacimiento', 'sexo', 'telefono',
            'correo', 'direccion', 'consultorio_asignado', 'foto'
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
            'consultorio_asignado': forms.Select(attrs={
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
            'consultorio_asignado': 'Consultorio Asignado',
            'foto': 'Foto del Paciente',
        }

    def __init__(self, *args, user: Usuario | None = None, **kwargs):
        super().__init__(*args, **kwargs)

        qs = Usuario.objects.none()
        if user:
            if user.rol == "medico":
                qs = Usuario.objects.filter(pk=user.pk)
            elif user.rol == "admin":
                qs = (
                    Usuario.objects.filter(
                        rol="medico",
                        is_active=True,
                        consultorio__isnull=False,
                    )
                    .order_by("consultorio__nombre")
                    .distinct("consultorio")
                )

        self.fields["consultorio_asignado"].queryset = qs
        self.fields["consultorio_asignado"].empty_label = "Sin asignar"
        self.fields["consultorio_asignado"].label_from_instance = (
            lambda obj: obj.consultorio.nombre if obj.consultorio else obj.get_full_name()
        )

        # Hacer la foto opcional
        self.fields['foto'].required = False
        self.fields['consultorio_asignado'].required = False

        if user and user.rol == 'medico':
            self.fields['consultorio_asignado'].widget = forms.HiddenInput()
            self.fields['consultorio_asignado'].initial = user
        elif user and user.rol != 'admin':
            self.fields['consultorio_asignado'].widget = forms.HiddenInput()



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
            'fecha_diagnostico': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'severidad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Severidad del antecedente'
            }),
            'estado_actual': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Estado actual'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas adicionales...'
            }),
        }
        labels = {
            'tipo': 'Tipo de Antecedente',
            'descripcion': 'Descripción',
            'fecha_diagnostico': 'Fecha de Diagnóstico',
            'severidad': 'Severidad',
            'estado_actual': 'Estado Actual',
            'notas': 'Notas',
        }


class MedicamentoActualForm(forms.ModelForm):
    """Formulario para medicamentos actuales"""
    
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
            'inicio': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'fin': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
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



# ───────────────────────────── helpers / constantes ────────────────
ESTADOS_ACTIVOS = ("programada", "confirmada", "en_espera", "en_atencion")
PASO_MIN = 15
DUR_CHOICES = [(str(m), f"{m} min") for m in range(PASO_MIN, 121, PASO_MIN)]


def _fecha_hora_from_fields(fecha, hh_mm: str) -> datetime:
    h, m = map(int, hh_mm.split(":"))
    return datetime.combine(fecha, datetime.min.time()).replace(hour=h, minute=m)


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

    # ---------- fecha / hora / duración ----------
    fecha = forms.DateField(
        label=_("Fecha"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
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
    def __init__(self, *args: Any, user: Usuario | None = None, **kwargs: Any):
        self._user = user
        kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

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
        
        # Configurar pacientes
        self.fields['paciente'].queryset = Paciente.objects.all().order_by('nombre_completo')
        
        # Configurar médicos según consultorio del usuario
        if self.user and self.user.consultorio:
            self.fields['medico'].queryset = Usuario.objects.filter(
                rol='medico',
                consultorio=self.user.consultorio,
                is_active=True
            ).order_by('first_name', 'last_name')
        elif self.user and self.user.rol == 'admin':
            # Admin puede seleccionar cualquier médico
            self.fields['medico'].queryset = Usuario.objects.filter(
                rol='medico',
                is_active=True
            ).order_by('first_name', 'last_name')
        else:
            self.fields['medico'].queryset = Usuario.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        programar_para = cleaned_data.get('programar_para')
        fecha_programada = cleaned_data.get('fecha_programada')
        hora_programada = cleaned_data.get('hora_programada')
        medico = cleaned_data.get('medico')
        
        # Validar horario personalizado
        if programar_para == 'personalizado':
            if not fecha_programada or not hora_programada:
                raise ValidationError("Debe especificar fecha y hora para horario personalizado.")
            
            fecha_hora_programada = timezone.make_aware(
                datetime.combine(fecha_programada, hora_programada)
            )
            
            if fecha_hora_programada < timezone.now():
                raise ValidationError("No se puede programar en el pasado.")
            
            cleaned_data['fecha_hora_programada'] = fecha_hora_programada
        
        # Validar que el médico pertenezca al consultorio del usuario
        if medico and self.user and self.user.consultorio:
            if medico.consultorio != self.user.consultorio:
                raise ValidationError(
                    f"El médico {medico.get_full_name()} no pertenece a tu consultorio."
                )
        
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
    
    class Meta:
        model = Receta
        fields = ['indicaciones_generales', 'valido_hasta', 'notas']
        widgets = {
            'indicaciones_generales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Indicaciones generales para el paciente...'
            }),
            'valido_hasta': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
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
            'via_administracion', 'duracion', 'cantidad', 'indicaciones_especificas'
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
                'placeholder': 'Cantidad total'
            }),
            'indicaciones_especificas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Indicaciones específicas...'
            }),
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
    
    class Meta:
        model = HorarioMedico
        fields = ['medico', 'consultorio', 'dia', 'hora_inicio', 'hora_fin']
        widgets = {
            'medico': forms.Select(attrs={'class': 'form-select'}),
            'consultorio': forms.Select(attrs={'class': 'form-select'}),
            'dia': forms.Select(attrs={'class': 'form-select'}),
            'hora_inicio': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'hora_fin': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
        }
        labels = {
            'medico': 'Médico',
            'consultorio': 'Consultorio',
            'dia': 'Día de la Semana',
            'hora_inicio': 'Hora de Inicio',
            'hora_fin': 'Hora de Fin',
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
            'telefono', 'cedula_profesional', 'institucion_cedula', 'consultorio'
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si es edición, hacer la contraseña opcional
        if self.instance.pk:
            self.fields['password1'].label = 'Nueva contraseña'
            self.fields['password2'].label = 'Confirmar contraseña'
            self.fields['password1'].help_text = "Dejar en blanco para mantener la contraseña actual"
            self.fields['password2'].help_text = "Dejar en blanco para mantener la contraseña actual"

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
        "indicaciones_especificas",
    ],
    extra=1,
    can_delete=True,
)
