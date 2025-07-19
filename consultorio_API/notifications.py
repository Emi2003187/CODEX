from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from .models import Notificacion, Usuario, Cita, Consulta, Auditoria
from .models import Notificacion    
from django.contrib.contenttypes.models import ContentType  

class NotificationManager:
    @staticmethod
    def crear_notificacion(
        usuario, tipo, titulo, mensaje,
        categoria="general",
        objeto_relacionado=None, url_accion=None
    ):
        datos = {
            "destinatario": usuario,      # ← nombre de campo real en el modelo
            "tipo": tipo,
            "titulo": titulo,
            "mensaje": mensaje,
            "categoria": categoria,
            "url_accion": url_accion,
        }
        if objeto_relacionado:
            datos["content_type"] = ContentType.objects.get_for_model(objeto_relacionado)
            datos["object_id"] = objeto_relacionado.pk

        return Notificacion.objects.create(**datos)
    
    
    @staticmethod
    def notificar_cita_creada(cita):
        """Notificar sobre nueva cita creada"""
        # Notificar a administradores
        admins = Usuario.objects.filter(rol='admin', is_active=True)
        for admin in admins:
            NotificationManager.crear_notificacion(
                usuario=admin,
                tipo='info',
                titulo='Nueva Cita Creada',
                mensaje=f'Cita #{cita.numero_cita} creada para {cita.paciente.nombre_completo}',
                categoria='citas',
                objeto_relacionado=cita,
                url_accion=f'/citas/{cita.pk}/'
            )
        
        # Notificar al médico asignado (si existe)
        if cita.medico_asignado:
            NotificationManager.crear_notificacion(
                usuario=cita.medico_asignado,
                tipo='info',
                titulo='Cita Asignada',
                mensaje=f'Se te ha asignado la cita #{cita.numero_cita} con {cita.paciente.nombre_completo}',
                categoria='citas',
                objeto_relacionado=cita,
                url_accion=f'/citas/{cita.pk}/'
            )
        
        # Notificar a asistentes del consultorio
        asistentes = Usuario.objects.filter(
            rol='asistente', 
            is_active=True,
            consultorio=cita.consultorio
        )
        for asistente in asistentes:
            NotificationManager.crear_notificacion(
                usuario=asistente,
                tipo='info',
                titulo='Nueva Cita en Consultorio',
                mensaje=f'Nueva cita #{cita.numero_cita} para {cita.paciente.nombre_completo}',
                categoria='citas',
                objeto_relacionado=cita,
                url_accion=f'/citas/{cita.pk}/'
            )
    
    @staticmethod
    def notificar_consulta_creada(consulta):
        """Notificar sobre nueva consulta creada"""
        # Notificar a administradores
        admins = Usuario.objects.filter(rol='admin', is_active=True)
        for admin in admins:
            NotificationManager.crear_notificacion(
                usuario=admin,
                tipo='info',
                titulo='Nueva Consulta Creada',
                mensaje=f'Consulta {consulta.get_tipo_display()} creada para {consulta.paciente.nombre_completo}',
                categoria='consultas',
                objeto_relacionado=consulta,
                url_accion=f'/consultas/{consulta.pk}/'
            )
        
        # Notificar al médico asignado
        if consulta.medico:
            NotificationManager.crear_notificacion(
                usuario=consulta.medico,
                tipo='info',
                titulo='Nueva Consulta Asignada',
                mensaje=f'Consulta {consulta.get_tipo_display()} con {consulta.paciente.nombre_completo}',
                categoria='consultas',
                objeto_relacionado=consulta,
                url_accion=f'/consultas/{consulta.pk}/'
            )
        
        # Notificar a asistentes si fue creada por médico
        if consulta.medico and consulta.asistente != consulta.medico:
            asistentes = Usuario.objects.filter(
                rol='asistente',
                is_active=True,
                consultorio=consulta.medico.consultorio
            )
            for asistente in asistentes:
                NotificationManager.crear_notificacion(
                    usuario=asistente,
                    tipo='info',
                    titulo='Nueva Consulta en Consultorio',
                    mensaje=f'Consulta {consulta.get_tipo_display()} para {consulta.paciente.nombre_completo}',
                    categoria='consultas',
                    objeto_relacionado=consulta,
                    url_accion=f'/consultas/{consulta.pk}/'
                )
    
    @staticmethod
    def notificar_signos_registrados(signos_vitales, asistente):
        """Notificar al médico cuando asistente registra signos vitales"""
        consulta = signos_vitales.consulta
        
        if consulta.medico and consulta.medico != asistente:
            NotificationManager.crear_notificacion(
                usuario=consulta.medico,
                tipo='success',
                titulo='Signos Vitales Registrados',
                mensaje=f'{asistente.get_full_name()} registró signos vitales para {consulta.paciente.nombre_completo}',
                categoria='signos_vitales',
                objeto_relacionado=signos_vitales,
                url_accion=f'/signos/{signos_vitales.pk}/'
            )
    
    @staticmethod
    def notificar_auditoria_admin(auditoria):
        """Notificar a administradores sobre acciones importantes de auditoría"""
        # Solo notificar sobre acciones críticas
        acciones_criticas = [
            'login_fallido', 'eliminar_paciente', 'eliminar_usuario',
            'cancelar_cita', 'eliminar_consulta', 'crear_usuario'
        ]
        
        if auditoria.accion in acciones_criticas:
            admins = Usuario.objects.filter(rol='admin', is_active=True)
            
            # Determinar tipo de notificación según la acción
            tipo_notif = 'warning' if 'eliminar' in auditoria.accion or 'login_fallido' in auditoria.accion else 'info'
            
            for admin in admins:
                NotificationManager.crear_notificacion(
                    usuario=admin,
                    tipo=tipo_notif,
                    titulo='Acción de Auditoría',
                    mensaje=f'{auditoria.usuario.get_full_name()}: {auditoria.descripcion}',
                    categoria='auditoria',
                    objeto_relacionado=auditoria,
                    url_accion='/auditoria/'
                )
    
    @staticmethod
    def notificar_citas_proximas():
        """Notificar sobre citas próximas (para ejecutar con cron)"""
        # Buscar citas en las próximas 2 horas
        ahora = timezone.now()
        limite = ahora + timedelta(hours=2)
        
        citas_proximas = Cita.objects.filter(
            fecha_hora__gte=ahora,
            fecha_hora__lte=limite,
            estado='confirmada'
        ).select_related('paciente', 'medico_asignado', 'consultorio')
        
        for cita in citas_proximas:
            # Verificar si ya se notificó (evitar spam)
            ya_notificado = Notificacion.objects.filter(
                categoria='recordatorio',
                object_id=cita.pk,
                fecha_creacion__gte=ahora - timedelta(hours=3)
            ).exists()
            
            if not ya_notificado:
                # Notificar a administradores
                admins = Usuario.objects.filter(rol='admin', is_active=True)
                for admin in admins:
                    NotificationManager.crear_notificacion(
                        usuario=admin,
                        tipo='warning',
                        titulo='Cita Próxima',
                        mensaje=f'Cita #{cita.numero_cita} con {cita.paciente.nombre_completo} en {cita.fecha_hora.strftime("%H:%M")}',
                        categoria='recordatorio',
                        objeto_relacionado=cita,
                        url_accion=f'/citas/{cita.pk}/'
                    )
                
                # Notificar al médico asignado
                if cita.medico_asignado:
                    NotificationManager.crear_notificacion(
                        usuario=cita.medico_asignado,
                        tipo='warning',
                        titulo='Cita Próxima',
                        mensaje=f'Tienes cita con {cita.paciente.nombre_completo} en {cita.fecha_hora.strftime("%H:%M")}',
                        categoria='recordatorio',
                        objeto_relacionado=cita,
                        url_accion=f'/citas/{cita.pk}/'
                    )
    
    @staticmethod
    def limpiar_notificaciones_antiguas(dias=30):
        """Limpiar notificaciones antiguas"""
        fecha_limite = timezone.now() - timedelta(days=dias)
        
        # Eliminar notificaciones leídas antiguas
        eliminadas = Notificacion.objects.filter(
            fecha_creacion__lt=fecha_limite,
            leida=True
        ).delete()
        
        return eliminadas[0] if eliminadas else 0
    
    @staticmethod
    def marcar_como_leidas(usuario, ids_notificaciones=None):
        """Marcar notificaciones como leídas"""
        queryset = Notificacion.objects.filter(usuario=usuario, leida=False)
        
        if ids_notificaciones:
            queryset = queryset.filter(id__in=ids_notificaciones)
        
        return queryset.update(leida=True, fecha_lectura=timezone.now())
    
    @staticmethod
    def obtener_estadisticas_usuario(usuario):
        """Obtener estadísticas de notificaciones para un usuario"""
        total = Notificacion.objects.filter(usuario=usuario).count()
        no_leidas = Notificacion.objects.filter(usuario=usuario, leida=False).count()
        
        por_categoria = {}
        categorias = Notificacion.objects.filter(usuario=usuario).values_list('categoria', flat=True).distinct()
        
        for categoria in categorias:
            por_categoria[categoria] = {
                'total': Notificacion.objects.filter(usuario=usuario, categoria=categoria).count(),
                'no_leidas': Notificacion.objects.filter(usuario=usuario, categoria=categoria, leida=False).count()
            }
        
        return {
            'total': total,
            'no_leidas': no_leidas,
            'por_categoria': por_categoria
        }
