from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from .models import (
    Paciente, Expediente, Auditoria, Cita, Consulta,
    SignosVitales, Usuario, Consultorio
)
from .auditoria_utils import registrar
from .notifications import NotificationManager

# ═══════════════════════════════════════════════════════════════
# 🔐 SEÑALES DE AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════

@receiver(user_logged_in)
def audit_login(sender, user, request, **kwargs):
    """Registrar login exitoso"""
    registrar(user, "login", user, "Inicio de sesión exitoso")

@receiver(user_logged_out)
def audit_logout(sender, user, request, **kwargs):
    """Registrar logout"""
    if user and user.is_authenticated:
        registrar(user, "logout", user, "Cierre de sesión")

@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request, **kwargs):
    """Registrar intento de login fallido"""
    username = credentials.get('username', 'Desconocido')
    
    # Crear registro de auditoría para login fallido
    try:
        # Intentar encontrar el usuario
        usuario = Usuario.objects.filter(username=username).first()
        if not usuario:
            # Si no existe el usuario, usar el primer admin para el registro
            usuario = Usuario.objects.filter(rol='admin').first()
        
        if usuario:
            auditoria = Auditoria.objects.create(
                usuario=usuario,
                accion="login_fallido",
                descripcion=f"Intento de login fallido para usuario: {username}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                content_type=ContentType.objects.get_for_model(Usuario),
                object_id=usuario.pk
            )
            
            # Notificar a administradores sobre login fallido
            NotificationManager.notificar_auditoria_admin(auditoria)
    except Exception:
        pass  # Evitar errores que impidan el funcionamiento normal

# ═══════════════════════════════════════════════════════════════
# 👥 SEÑALES DE PACIENTES
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Paciente)
def crear_expediente_y_auditar(sender, instance, created, **kwargs):
    """Crear expediente automáticamente y registrar en auditoría"""
    if created and not hasattr(instance, "expediente"):
        Expediente.objects.create(paciente=instance)
        
        if instance.consultorio_asignado:
            registrar(
                instance.consultorio_asignado,   
                "crear_paciente",
                instance,
                f"Alta de paciente: {instance.nombre_completo}"
            )

# ═══════════════════════════════════════════════════════════════
# 📅 SEÑALES DE CITAS
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Cita)
def procesar_cita_creada(sender, instance, created, **kwargs):
    """Procesar cita creada: auditoría y notificaciones"""
    if created:
        # Registrar en auditoría
        usuario = instance.creado_por or instance.medico_asignado
        if usuario:
            registrar(
                usuario,
                "crear_cita",
                instance,
                f"Cita {instance.numero_cita} creada para {instance.paciente.nombre_completo}"
            )
        
        # Enviar notificaciones
        NotificationManager.notificar_cita_creada(instance)

@receiver(pre_save, sender=Cita)
def auditar_cambios_cita(sender, instance, **kwargs):
    """Auditar cambios importantes en citas"""
    if not instance.pk:  # Nueva cita
        return
    
    try:
        old_cita = Cita.objects.get(pk=instance.pk)
        
        # Cambio de estado
        if old_cita.estado != instance.estado:
            usuario = instance.actualizado_por or instance.medico_asignado
            if usuario:
                registrar(
                    usuario,
                    "cambiar_estado_cita",
                    instance,
                    f"Estado de cita {instance.numero_cita} cambió de {old_cita.get_estado_display()} a {instance.get_estado_display()}"
                )
        
        # Asignación de médico
        if old_cita.medico_asignado != instance.medico_asignado:
            usuario = instance.actualizado_por
            if usuario and instance.medico_asignado:
                registrar(
                    usuario,
                    "asignar_medico_cita",
                    instance,
                    f"Médico {instance.medico_asignado.get_full_name()} asignado a cita {instance.numero_cita}"
                )
        
        # Cancelación
        if old_cita.estado != 'cancelada' and instance.estado == 'cancelada':
            usuario = instance.actualizado_por
            if usuario:
                registrar(
                    usuario,
                    "cancelar_cita",
                    instance,
                    f"Cita {instance.numero_cita} cancelada. Motivo: {instance.motivo_cancelacion}"
                )
    except Cita.DoesNotExist:
        pass

# ═══════════════════════════════════════════════════════════════
# 🩺 SEÑALES DE CONSULTAS
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Consulta)
def procesar_consulta_creada(sender, instance, created, **kwargs):
    """Procesar consulta creada: auditoría y notificaciones"""
    if created:
        # Registrar en auditoría
        usuario = instance.asistente or instance.medico
        if usuario:
            registrar(
                usuario,
                "crear_consulta",
                instance,
                f"Consulta {instance.get_tipo_display()} creada para {instance.paciente.nombre_completo}"
            )
        
        # Enviar notificaciones
        NotificationManager.notificar_consulta_creada(instance)

@receiver(pre_save, sender=Consulta)
def auditar_cambios_consulta(sender, instance, **kwargs):
    """Auditar cambios de estado en consultas"""
    if not instance.pk:  # Nueva consulta
        return

    try:
        old_consulta = Consulta.objects.get(pk=instance.pk)
        
        # Cambio de estado
        if old_consulta.estado != instance.estado:
            usuario = instance.medico or instance.asistente
            
            if usuario:
                # Inicio de consulta
                if old_consulta.estado == "espera" and instance.estado == "en_progreso":
                    registrar(
                        usuario,
                        "iniciar_consulta",
                        instance,
                        f"Consulta de {instance.paciente.nombre_completo} iniciada"
                    )
                
                # Finalización de consulta
                elif old_consulta.estado == "en_progreso" and instance.estado == "finalizada":
                    registrar(
                        usuario,
                        "finalizar_consulta",
                        instance,
                        f"Consulta de {instance.paciente.nombre_completo} finalizada"
                    )
                
                # Cancelación de consulta
                elif instance.estado == "cancelada":
                    registrar(
                        usuario,
                        "cancelar_consulta",
                        instance,
                        f"Consulta de {instance.paciente.nombre_completo} cancelada"
                    )
    except Consulta.DoesNotExist:
        pass

# ═══════════════════════════════════════════════════════════════
# 📊 SEÑALES DE SIGNOS VITALES
# ═══════════════════════════════════════════════════════════════

from .audit_generic import get_current_user, get_current_request

@receiver(post_save, sender=SignosVitales)
def procesar_signos_vitales(sender, instance, created, **kwargs):
    """Procesar signos vitales: auditoría y notificaciones"""
    
    # Obtener el usuario que registró los signos (desde el request actual)
    usuario_actual = get_current_user()
    
    if created:
        # Registrar en auditoría
        if usuario_actual:
            registrar(
                usuario_actual,
                "registrar_signos_vitales",
                instance,
                f"Signos vitales registrados para {instance.consulta.paciente.nombre_completo}"
            )
            
            # Enviar notificaciones solo si fue registrado por un asistente
            if usuario_actual.rol == 'asistente':
                NotificationManager.notificar_signos_registrados(instance, usuario_actual)
    else:
        # Actualización de signos vitales
        if usuario_actual:
            registrar(
                usuario_actual,
                "actualizar_signos_vitales",
                instance,
                f"Signos vitales actualizados para {instance.consulta.paciente.nombre_completo}"
            )

# ═══════════════════════════════════════════════════════════════
# 🏥 SEÑALES DE CONSULTORIOS
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Consultorio)
def auditar_consultorio_save(sender, instance, created, **kwargs):
    usuario_actual = get_current_user()
    request = get_current_request()
    if usuario_actual:
        accion = "CREAR" if created else "EDITAR"
        descripcion = f"{accion.capitalize()} consultorio {instance.nombre}"
        registrar(usuario_actual, accion, instance, descripcion, request)


@receiver(post_delete, sender=Consultorio)
def auditar_consultorio_delete(sender, instance, **kwargs):
    usuario_actual = get_current_user()
    request = get_current_request()
    if usuario_actual:
        registrar(usuario_actual, "ELIMINAR", instance, f"Eliminar consultorio {instance.nombre}", request)

# ═══════════════════════════════════════════════════════════════
# 👤 SEÑALES DE USUARIOS
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Usuario)
def auditar_usuario(sender, instance, created, **kwargs):
    """Auditar creación y modificación de usuarios"""
    from .audit_generic import get_current_user
    usuario_actual = get_current_user()
    
    if usuario_actual and usuario_actual != instance:
        if created:
            registrar(
                usuario_actual,
                "crear_usuario",
                instance,
                f"Usuario {instance.get_full_name()} creado con rol {instance.get_rol_display()}"
            )
        else:
            registrar(
                usuario_actual,
                "editar_usuario",
                instance,
                f"Usuario {instance.get_full_name()} modificado"
            )

# ═══════════════════════════════════════════════════════════════
# 🔔 SEÑALES DE AUDITORÍA PARA NOTIFICACIONES
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Auditoria)
def procesar_auditoria_para_notificaciones(sender, instance, created, **kwargs):
    """Procesar registros de auditoría para generar notificaciones"""
    if created:
        # Notificar a administradores sobre acciones importantes
        NotificationManager.notificar_auditoria_admin(instance)
