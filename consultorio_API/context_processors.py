from __future__ import annotations

from .models import Notificacion


def notificaciones_no_leidas(request):
    if request.user.is_authenticated and request.user.rol in ("medico", "admin"):
        total = Notificacion.objects.filter(destinatario=request.user, leido=False).count()
        return {"num_notif_sin_leer": total}
    return {}


def usuario_actual(request):
    """Incluye el usuario autenticado para plantillas que esperan `usuario`.

    Evita errores en layouts base cuando alguna vista no envía explícitamente el
    contexto `usuario`.
    """

    return {"usuario": request.user}
