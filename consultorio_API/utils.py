from datetime import datetime, time, timedelta

def obtener_horarios_disponibles(
    consultorio,
    fecha,
    duracion_minutos: int = 30,
    paso_minutos: int = 15,
):
    """
    Devuelve una lista de objetos `datetime.time` con los inicios de turno
    libres para *consultorio* en la *fecha* dada.

    • Jornada fija 08:00 – 18:00.  
    • Paso de 15 min (ajústalo con `paso_minutos`).  
    • Revisa las citas con estado programada / confirmada / atendida y evita
      solapamientos:   [ini < ocup_fin and fin > ocup_ini].
    """
    # Import local para no romper migraciones ni tests
    from .models import Cita

    # --- 1) Citas ya ocupadas ese día -----------------------------
    qs = Cita.objects.filter(
        consultorio=consultorio,
        fecha_hora__date=fecha,
        estado__in=["programada", "confirmada", "atendida"],
    ).only("fecha_hora", "duracion")

    ocupados = []
    for cita in qs:
        ini = datetime.combine(fecha, cita.fecha_hora.time())
        fin = ini + timedelta(minutes=cita.duracion)
        ocupados.append((ini, fin))

    # --- 2) Barrido de todo el horario de atención -----------------
    hora_ini = datetime.combine(fecha, time(8, 0))
    hora_fin = datetime.combine(fecha, time(18, 0))
    delta_paso = timedelta(minutes=paso_minutos)
    delta_dur  = timedelta(minutes=duracion_minutos)

    libres = []
    cursor = hora_ini
    while cursor + delta_dur <= hora_fin:
        candidato_ini = cursor
        candidato_fin = cursor + delta_dur

        # ¿Se solapa con algún ocupado?
        solapado = any(
            candidato_ini < o_fin and candidato_fin > o_ini
            for o_ini, o_fin in ocupados
        )

        if not solapado:
            libres.append(candidato_ini.time())

        cursor += delta_paso

    return libres




from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def redirect_next(request, default_url_name, *args, **kwargs):
    """Redirect honoring optional ?next= parameter."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    return redirect(reverse(default_url_name, args=args, kwargs=kwargs))
