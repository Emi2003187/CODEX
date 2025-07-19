from django.contrib.contenttypes.models import ContentType
from .models import Auditoria

def get_client_ip(request):
    """Obtiene la IP real del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def registrar(usuario, accion, objeto, descripcion="", request=None):
    """
    Crea un registro en Auditoria con información completa.
    - usuario:     instancia Usuario que ejecuta la acción
    - accion:      str corta (≤ 50 char) p. ej. 'login'
    - objeto:      instancia sobre la que se actúa
    - descripcion: texto opcional
    - request:     objeto request para capturar IP y user agent
    """
    ip_address = None
    user_agent = ""
    
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
    
    Auditoria.objects.create(
        usuario=usuario,
        accion=accion,
        descripcion=descripcion[:500],   # por si te pasas
        ip_address=ip_address,
        user_agent=user_agent,
        content_type=ContentType.objects.get_for_model(objeto),
        object_id=objeto.pk,
    )

def registrar_login(usuario, request, exitoso=True):
    """Registra intentos de login"""
    accion = 'login_exitoso' if exitoso else 'login_fallido'
    descripcion = f"Login {'exitoso' if exitoso else 'fallido'} desde {get_client_ip(request)}"
    
    # Para login fallido, crear un objeto dummy si no tenemos usuario
    if not exitoso and not usuario:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        usuario = User.objects.filter(is_superuser=True).first()
        if not usuario:
            return  # No podemos registrar sin usuario
    
    registrar(usuario, accion, usuario, descripcion, request)

def registrar_logout(usuario, request):
    """Registra logout de usuarios"""
    descripcion = f"Logout desde {get_client_ip(request)}"
    registrar(usuario, 'logout', usuario, descripcion, request)

def registrar_accion_personalizada(usuario, accion, objeto, descripcion, request=None):
    """Registra acciones personalizadas"""
    registrar(usuario, accion, objeto, descripcion, request)
