from datetime import date
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import FileExtensionValidator
from django.conf import settings
import uuid

# ───────────────────────────────────────────────
# 1️⃣  USUARIOS
# ───────────────────────────────────────────────
class Usuario(AbstractUser):
    ROLES = (
        ('admin', 'Administrador'),
        ('medico', 'Médico'),
        ('asistente', 'Asistente'),
    )

    rol = models.CharField(max_length=20, choices=ROLES)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    cedula_profesional = models.CharField(max_length=20, blank=True, null=True)
    institucion_cedula = models.CharField(max_length=100, blank=True, null=True)
    
    consultorio = models.ForeignKey(
        'Consultorio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_asignados'
    )

    foto = models.ImageField(
        upload_to='usuarios/fotos/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
    )

    def __str__(self):
        return f"{self.get_full_name()} ({self.rol})"


# ───────────────────────────────────────────────
# 2️⃣  PACIENTES
# ───────────────────────────────────────────────
class Paciente(models.Model):
    SEXO_CHOICES = (('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro'))

    nombre_completo = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField()
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    telefono = models.CharField(max_length=15)
    correo = models.EmailField()
    direccion = models.TextField()
    consultorio = models.ForeignKey(
        'Consultorio',
        on_delete=models.PROTECT,
        related_name="pacientes"
    )
    foto = models.ImageField(
    upload_to='pacientes/',
    null=True,
    blank=True
)


    @property
    def edad(self):
        hoy = date.today()
        return hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )

    def __str__(self):
        return self.nombre_completo


# ───────────────────────────────────────────────
# 3️⃣  CONSULTAS 
# ───────────────────────────────────────────────
class Consulta(models.Model):
    ESTADO_OPCIONES = [
        ('espera',      'En Espera'),
        ('en_progreso', 'En Progreso'),
        ('finalizada',  'Finalizada'),
        ('cancelada',   'Cancelada'),
    ]
    TIPO_CONSULTA = [
        ('con_cita',  'Con Cita'),
        ('sin_cita',  'Sin Cita'),
    ]

    paciente        = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    fecha_creacion  = models.DateTimeField(auto_now_add=True)
    fecha_atencion  = models.DateTimeField(null=True, blank=True)
    estado          = models.CharField(max_length=20, choices=ESTADO_OPCIONES, default='espera')
    tipo            = models.CharField(max_length=20, choices=TIPO_CONSULTA)
    cita            = models.OneToOneField('Cita', on_delete=models.SET_NULL, null=True, blank=True)
    asistente       = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='consultas_asistente')
    medico          = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='consultas_medico')
    motivo_consulta = models.TextField(blank=True, null=True)
    diagnostico     = models.TextField(blank=True, null=True)
    tratamiento     = models.TextField(blank=True, null=True)
    observaciones   = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # Solo asignar tipo automáticamente si no se ha especificado
        if not self.tipo:
            if self.cita:
                self.tipo = 'con_cita'
            else:
                self.tipo = 'sin_cita'
        
        # Si viene de una cita y no tiene médico asignado, usar el de la cita
        if self.cita and not self.medico and self.cita.medico_asignado:
            self.medico = self.cita.medico_asignado

        # Guardamos la consulta
        super().save(*args, **kwargs)

        # Sincronizar estado con la cita solo si existe cita
        if self.cita:
            new_estado = None
            if self.estado == 'en_progreso':
                new_estado = 'en_atencion'
            elif self.estado == 'finalizada':
                new_estado = 'completada'
            elif self.estado == 'cancelada':
                new_estado = 'cancelada'
            
            if new_estado and self.cita.estado != new_estado:
                self.cita.estado = new_estado
                self.cita.save()

    def __str__(self):
        return f"Consulta {self.get_tipo_display()} de {self.paciente}"
        
# ───────────────────────────────────────────────
# 4️⃣  SIGNOS VITALES (MEJORADO)
# ───────────────────────────────────────────────
class SignosVitales(models.Model):
    consulta = models.OneToOneField(
        'Consulta', on_delete=models.CASCADE, related_name='signos_vitales'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signos_registrados',
        verbose_name='Registrado por'
    )

    # T.A. (Tensión Arterial)
    tension_arterial = models.CharField(
        "T.A. (Tensión Arterial)", max_length=20, blank=True, null=True,
        help_text="Ej. 120/80"
    )

    # F.C. (Frecuencia Cardíaca)
    frecuencia_cardiaca = models.PositiveSmallIntegerField(
        "F.C. (lpm)", blank=True, null=True,
        help_text="Latidos por minuto"
    )

    # F.R. (Frecuencia Respiratoria)
    frecuencia_respiratoria = models.PositiveSmallIntegerField(
        "F.R. (rpm)", blank=True, null=True,
        help_text="Respiraciones por minuto"
    )

    # Temp. (Temperatura)
    temperatura = models.DecimalField(
        "Temp. (°C)", max_digits=4, decimal_places=1,
        blank=True, null=True
    )

    # Peso (kg)
    peso = models.DecimalField(
        "Peso (kg)", max_digits=6, decimal_places=2,
        blank=True, null=True
    )

    # Talla (m)
    talla = models.DecimalField(
        "Talla (m)", max_digits=4, decimal_places=2,
        blank=True, null=True
    )

    # Circunferencia abdominal (cm)
    circunferencia_abdominal = models.DecimalField(
        "Circ. abdominal (cm)", max_digits=6, decimal_places=2,
        blank=True, null=True
    )

    # IMC (Índice de Masa Corporal)
    imc = models.DecimalField(
        "IMC", max_digits=5, decimal_places=2,
        blank=True, null=True
    )

    # Alergias del paciente
    alergias = models.TextField(
        "Alergias del paciente", blank=True, null=True,
        help_text="Describir sustancias o marcar NEGATIVO"
    )

    # Síntomas o padecimientos actuales
    sintomas = models.TextField(
        "Síntomas o padecimientos actuales", blank=True, null=True
    )

    def save(self, *args, **kwargs):
        # Recalcula IMC si hay peso y talla
        if self.peso and self.talla:
            self.imc = float(self.peso) / (float(self.talla) ** 2)

        # Asigna automáticamente quien registra si no se proporcionó
        if not self.registrado_por:
            from .audit_generic import get_current_user
            self.registrado_por = get_current_user()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Signos Vitales de {self.consulta.paciente.nombre_completo}"


# ───────────────────────────────────────────────
# 5️⃣  HISTORIAL CLÍNICO 
# ───────────────────────────────────────────────
class Expediente(models.Model):
    paciente = models.OneToOneField("Paciente", on_delete=models.CASCADE, related_name="expediente")
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)
    notas_generales = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Expediente #{self.pk} - {self.paciente}"


class Antecedente(models.Model):
    TIPO_CHOICES = [
        ('personal', 'Personal'),
        ('familiar', 'Familiar'),
        ('quirurgico', 'Quirúrgico'),
        ('alergico', 'Alérgico'),
        ('toxicologico', 'Toxicológico'),
    ]

    SEVERIDAD_CHOICES = [
        ("baja", "Baja"),
        ("media", "Media"),
        ("alta", "Alta"),
    ]

    ESTADO_CHOICES = [
        ("estable", "Estable"),
        ("en_tratamiento", "En tratamiento"),
        ("controlado", "Controlado"),
        ("resuelto", "Resuelto"),
    ]

    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE, related_name="antecedentes"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField()
    fecha_diagnostico = models.DateField(blank=True, null=True)
    severidad = models.CharField(
        max_length=10,
        choices=SEVERIDAD_CHOICES,
        default="media",
    )
    estado_actual = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="estable",
    )
    notas = models.TextField(blank=True, null=True)

    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_diagnostico']

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.descripcion[:50]}..."


class MedicamentoActual(models.Model):
    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="medicamentos_actuales")
    nombre = models.CharField(max_length=100)
    principio_activo = models.CharField(max_length=100, blank=True, null=True)
    dosis = models.CharField(max_length=50)
    frecuencia = models.CharField(max_length=100)
    via_administracion = models.CharField(max_length=50, blank=True, null=True)
    proposito = models.CharField(max_length=100, blank=True, null=True)
    inicio = models.DateField(blank=True, null=True)
    fin = models.DateField(blank=True, null=True)
    prescrito_por = models.CharField(max_length=100, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)

    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.dosis})"


# ───────────────────────────────────────────────
# 6️⃣  RECETAS 
# ───────────────────────────────────────────────
class Receta(models.Model):
    consulta = models.OneToOneField("Consulta", on_delete=models.CASCADE, related_name="receta")
    medico = models.ForeignKey("Usuario", on_delete=models.SET_NULL, null=True, related_name="recetas_emitidas")
    fecha_emision = models.DateField(auto_now_add=True)
    valido_hasta = models.DateField(blank=True, null=True)
    indicaciones_generales = models.TextField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Receta #{self.pk} - {self.consulta.paciente}"


class MedicamentoRecetado(models.Model):
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name="medicamentos")
    nombre = models.CharField(max_length=100)
    principio_activo = models.CharField(max_length=100, blank=True, null=True)
    dosis = models.CharField(max_length=50)
    frecuencia = models.CharField(max_length=100)
    via_administracion = models.CharField(max_length=50, blank=True, null=True)
    duracion = models.CharField(max_length=50)
    cantidad = models.PositiveSmallIntegerField(blank=True, null=True)
    codigo_barras = models.CharField(max_length=32, blank=True, null=True)
    indicaciones_especificas = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} ({self.dosis})"


# ───────────────────────────────────────────────
# 7️⃣  CITAS MÉDICAS 
# ────────────────────────────────────────────────

class Cita(models.Model):
    ESTADO_CHOICES = [
        ('programada', 'Programada'),
        ('confirmada', 'Confirmada'),
        ('en_espera', 'En Espera'),
        ('en_atencion', 'En Atención'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
        ('no_asistio', 'No Asistió'),
        ('reprogramada', 'Reprogramada'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    TIPO_CITA_CHOICES = [
        ('primera_vez', 'Primera Vez'),
        ('cita_normal', 'Cita Normal'),
    ]

    # Identificación
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_cita = models.CharField(max_length=50, unique=True)
    
    # Relaciones principales - CAMBIO IMPORTANTE
    paciente = models.ForeignKey('Paciente', on_delete=models.CASCADE, related_name='citas')
    consultorio = models.ForeignKey('Consultorio', on_delete=models.CASCADE, related_name='citas')
    
    # Médico asignado (opcional - se asigna cuando se toma la consulta)
    medico_asignado = models.ForeignKey(
        'Usuario', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='citas_asignadas',
        limit_choices_to={'rol': 'medico'},
        help_text="Médico que tomará/tomó la consulta"
    )
    
    # Médico preferido (opcional - sugerencia del paciente)
    medico_preferido = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='citas_preferidas',
        limit_choices_to={'rol': 'medico'},
        help_text="Médico preferido por el paciente (opcional)"
    )
    
    # Información de la cita
    fecha_hora = models.DateTimeField()
    duracion = models.PositiveIntegerField(default=30, help_text="Duración en minutos")
    tipo_cita = models.CharField(max_length=20, choices=TIPO_CITA_CHOICES, default='cita_normal')
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='normal')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='programada')
    
    # Detalles
    motivo = models.TextField(blank=True, help_text="Motivo de la consulta")
    notas = models.TextField(blank=True, help_text="Notas adicionales")
    observaciones_medicas = models.TextField(blank=True)
    
    # Información de contacto
    telefono_contacto = models.CharField(max_length=15, blank=True)
    email_recordatorio = models.EmailField(blank=True)
    
    # Control de tiempo
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    fecha_asignacion_medico = models.DateTimeField(null=True, blank=True)
    
    # Usuarios de control
    creado_por = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True, related_name='citas_creadas')
    actualizado_por = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True, related_name='citas_actualizadas')
    
    # Recordatorios
    recordatorio_enviado = models.BooleanField(default=False)
    fecha_recordatorio = models.DateTimeField(null=True, blank=True)
    
    # Cita anterior (para reprogramaciones)
    cita_anterior = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    motivo_cancelacion = models.TextField(blank=True)

    class Meta:
        ordering = ['fecha_hora']
        indexes = [
            models.Index(fields=['fecha_hora']),
            models.Index(fields=['estado']),
            models.Index(fields=['consultorio', 'fecha_hora']),
            models.Index(fields=['paciente', 'fecha_hora']),
            models.Index(fields=['medico_asignado', 'fecha_hora']),
        ]

    def save(self, *args, **kwargs):
        if not self.numero_cita:
            self.numero_cita = self.generar_numero_cita()
        
        # Si se asigna un médico, registrar la fecha
        if self.medico_asignado and not self.fecha_asignacion_medico:
            self.fecha_asignacion_medico = timezone.now()
            
        super().save(*args, **kwargs)

    def generar_numero_cita(self):
        from datetime import datetime
        import random
        fecha = datetime.now()
        # Usar timestamp y número aleatorio para evitar conflictos con UUID
        timestamp = int(fecha.timestamp())
        random_num = random.randint(1000, 9999)
        return f"C{fecha.strftime('%Y%m%d')}{random_num}"

    @property
    def puede_cancelar(self):
        return self.estado in ['programada', 'confirmada', 'en_espera']

    @property
    def puede_asignar_medico(self):
        return self.estado in ['programada', 'confirmada', 'en_espera'] and not self.medico_asignado

    @property
    def medicos_disponibles(self):
        """Retorna médicos disponibles del consultorio para esta cita"""
        return Usuario.objects.filter(
            rol='medico',
            consultorio=self.consultorio,
            is_active=True
        )

    def asignar_medico(self, medico, usuario_asignador=None):
        """Asigna un médico a la cita"""
        if not self.puede_asignar_medico:
            raise ValueError("No se puede asignar médico a esta cita")
        
        if medico.consultorio != self.consultorio:
            raise ValueError("El médico debe pertenecer al mismo consultorio")
        
        self.medico_asignado = medico
        self.fecha_asignacion_medico = timezone.now()
        self.estado = 'confirmada'
        
        if usuario_asignador:
            self.actualizado_por = usuario_asignador
            
        self.save()

    def __str__(self):
        medico_info = f" - Dr. {self.medico_asignado.get_full_name()}" if self.medico_asignado else " - Sin asignar"
        return f"Cita {self.numero_cita} - {self.paciente}{medico_info} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"

# ───────────────────────────────────────────────
# 8️⃣  CONSULTORIOS
# ───────────────────────────────────────────────
class Consultorio(models.Model):
    nombre             = models.CharField(max_length=100, unique=True)
    ubicacion          = models.TextField(blank=True, null=True)
    capacidad_diaria   = models.PositiveSmallIntegerField(default=20)
    horario_apertura   = models.TimeField(default="09:00")
    horario_cierre     = models.TimeField(default="17:00")

    def __str__(self):
        return self.nombre


# ───────────────────────────────────────────────
# 9️⃣  AUDITORÍA CORREGIDA
# ───────────────────────────────────────────────
class Auditoria(models.Model):
    usuario       = models.ForeignKey("Usuario", on_delete=models.CASCADE)
    accion        = models.CharField(max_length=50)
    descripcion   = models.TextField(blank=True)

    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    user_agent    = models.CharField(max_length=255, blank=True)

    content_type  = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    # Cambiar a CharField para soportar tanto enteros como UUIDs
    object_id     = models.CharField(max_length=255)
    objeto        = GenericForeignKey("content_type", "object_id")

    fecha         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.usuario} - {self.accion} ({self.fecha:%d/%m/%Y %H:%M})"



class HorarioMedico(models.Model):
    DIAS_SEMANA = [
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miércoles', 'Miércoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sábado', 'Sábado'),
        ('domingo', 'Domingo'),
    ]

    medico = models.ForeignKey("Usuario", on_delete=models.CASCADE, limit_choices_to={'rol': 'medico'}, related_name="horarios")
    consultorio = models.ForeignKey("Consultorio", on_delete=models.CASCADE)
    dia = models.CharField(max_length=10, choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        unique_together = ('medico', 'dia', 'consultorio')
        ordering = ['medico', 'dia', 'hora_inicio']

    def __str__(self):
        return f"{self.medico} - {self.dia} ({self.hora_inicio} - {self.hora_fin})"


# ───────────────────────────────────────────────
# 🔔 NOTIFICACIONES MEJORADAS
# ───────────────────────────────────────────────
class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('info', 'Información'),
        ('warning', 'Advertencia'),
        ('success', 'Éxito'),
        ('error', 'Error'),
        ('urgent', 'Urgente'),
    ]
    
    CATEGORIA_CHOICES = [
        ('auditoria', 'Auditoría'),
        ('cita_proxima', 'Cita Próxima'),
        ('cita_creada', 'Cita Creada'),
        ('consulta_creada', 'Consulta Creada'),
        ('signos_registrados', 'Signos Vitales'),
        ('sistema', 'Sistema'),
        ('recordatorio', 'Recordatorio'),
    ]

    destinatario = models.ForeignKey(
        "Usuario", 
        on_delete=models.CASCADE, 
        related_name="notificaciones"
    )
    
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='info')
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='sistema')
    
    # Relación genérica al objeto relacionado - CORREGIDA
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)  # Cambiado a CharField
    objeto_relacionado = GenericForeignKey('content_type', 'object_id')
    
    # URL de acción (opcional)
    url_accion = models.URLField(blank=True, help_text="URL para redirigir al hacer clic")
    texto_accion = models.CharField(max_length=50, blank=True, help_text="Texto del botón de acción")
    
    # Control
    leido = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_leido = models.DateTimeField(null=True, blank=True)
    
    # Metadatos
    datos_extra = models.JSONField(default=dict, blank=True, help_text="Datos adicionales en formato JSON")

    class Meta:
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=['destinatario', 'leido']),
            models.Index(fields=['categoria', 'fecha']),
            models.Index(fields=['tipo', 'fecha']),
        ]

    def marcar_como_leido(self):
        """Marca la notificación como leída"""
        if not self.leido:
            self.leido = True
            self.fecha_leido = timezone.now()
            self.save(update_fields=['leido', 'fecha_leido'])

    def __str__(self):
        return f"{self.titulo} → {self.destinatario}"
