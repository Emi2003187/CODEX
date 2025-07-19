from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from .auditoria_utils import registrar, registrar_login, registrar_logout
import threading

# Thread local para almacenar el request actual
_thread_locals = threading.local()

def set_current_request(request):
    """Almacena el request actual en thread local"""
    _thread_locals.request = request

def get_current_request():
    """Obtiene el request actual desde thread local"""
    return getattr(_thread_locals, 'request', None)

def get_current_user():
    """Obtiene el usuario actual desde el request almacenado en thread local"""
    request = get_current_request()
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        return request.user
    return None

AUDIT_MODELS = (
    'Cita', 'Consulta', 'Paciente', 'Receta', 'MedicamentoRecetado',
    'HorarioMedico', 'Consultorio', 'Usuario', 'SignosVitales',
    'Antecedente', 'MedicamentoActual', 'Expediente'
)

def _model(name):
    return apps.get_model('consultorio_API', name)

# --- Señales de autenticación ---
@receiver(user_logged_in)
def audit_user_logged_in(sender, request, user, **kwargs):
    registrar_login(user, request, exitoso=True)

@receiver(user_logged_out)
def audit_user_logged_out(sender, request, user, **kwargs):
    if user and user.is_authenticated:
        registrar_logout(user, request)

@receiver(user_login_failed)
def audit_user_login_failed(sender, credentials, request, **kwargs):
    # Intentar encontrar el usuario por username
    from django.contrib.auth import get_user_model
    User = get_user_model()
    username = credentials.get('username', 'desconocido')
    
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User.objects.filter(is_superuser=True).first()
    
    if user:
        descripcion = f"Intento de login fallido para usuario: {username}"
        registrar(user, 'login_fallido', user, descripcion, request)

# --- altas / actualizaciones ---
@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    if sender.__name__ not in AUDIT_MODELS:
        return
    
    # Obtener usuario del request actual
    request = get_current_request()
    usuario = None
    
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        usuario = request.user
    else:
        # Fallback: buscar usuario en la instancia
        usuario = getattr(instance, 'actualizado_por', None) or getattr(instance, 'creado_por', None)
        if not usuario and hasattr(instance, 'medico'):
            usuario = getattr(instance, 'medico', None)
        if not usuario and hasattr(instance, 'usuario'):
            usuario = getattr(instance, 'usuario', None)
    
    if not usuario:
        return
    
    accion = f'crear_{sender.__name__.lower()}' if created else f'editar_{sender.__name__.lower()}'
    descripcion = f"{'Creó' if created else 'Editó'} {sender.__name__}: {str(instance)}"
    
    registrar(usuario, accion, instance, descripcion, request)

# --- eliminaciones ---
@receiver(pre_delete)
def audit_pre_delete(sender, instance, using, **kwargs):
    if sender.__name__ not in AUDIT_MODELS:
        return
    
    request = get_current_request()
    usuario = None
    
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        usuario = request.user
    else:
        usuario = getattr(instance, 'actualizado_por', None) or getattr(instance, 'creado_por', None)
        if not usuario and hasattr(instance, 'medico'):
            usuario = getattr(instance, 'medico', None)
        if not usuario and hasattr(instance, 'usuario'):
            usuario = getattr(instance, 'usuario', None)
    
    if usuario:
        descripcion = f"Eliminó {sender.__name__}: {str(instance)}"
        registrar(usuario, f'eliminar_{sender.__name__.lower()}', instance, descripcion, request)
