from django.core.management.base import BaseCommand
from django.utils import timezone
from consultorio_API.notifications import NotificationManager

class Command(BaseCommand):
    help = 'Envía recordatorios de citas próximas y limpia notificaciones antiguas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Limpiar notificaciones antiguas',
        )
        parser.add_argument(
            '--dias',
            type=int,
            default=30,
            help='Días de antigüedad para limpiar notificaciones (default: 30)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(f'Iniciando proceso de recordatorios - {timezone.now()}')
        )
        
        # Enviar recordatorios de citas próximas
        try:
            NotificationManager.notificar_citas_proximas()
            self.stdout.write(
                self.style.SUCCESS('✅ Recordatorios de citas próximas enviados')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error enviando recordatorios: {str(e)}')
            )
        
        # Limpiar notificaciones antiguas si se solicita
        if options['limpiar']:
            try:
                count = NotificationManager.limpiar_notificaciones_antiguas(options['dias'])
                self.stdout.write(
                    self.style.SUCCESS(f'🧹 {count} notificaciones antiguas eliminadas')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error limpiando notificaciones: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('✅ Proceso completado exitosamente')
        )
