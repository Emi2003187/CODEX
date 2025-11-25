from .models import Notificacion

def notificaciones_no_leidas(request):
    if request.user.is_authenticated and request.user.rol in ("medico", "admin"):
        total = Notificacion.objects.filter(destinatario=request.user, leido=False).count()
        return {"num_notif_sin_leer": total}
    return {}
