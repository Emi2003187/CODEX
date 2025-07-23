from datetime import datetime, time, timedelta
from django.db.models import Q

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


def horario_ocupado(consultorio, medico, inicio: datetime, duracion_min: int):
    """Return True if a Cita overlaps the given interval."""
    from .models import Cita

    fin = inicio + timedelta(minutes=duracion_min)

    citas = (
        Cita.objects.filter(
            estado__in=["programada", "confirmada", "en_espera", "en_atencion"]
        )
        .filter(Q(consultorio=consultorio) | Q(medico_asignado=medico))
        .filter(fecha_hora__lt=fin)
        .only("fecha_hora", "duracion")
    )

    for c in citas:
        c_fin = c.fecha_hora + timedelta(minutes=c.duracion)
        if c_fin > inicio:
            return True

    return False


from django.shortcuts import redirect
from django.urls import reverse


def redirect_next(request, default_url_name, *args, **kwargs):
    """Redirect honoring optional ?next= parameter."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect(reverse(default_url_name, args=args, kwargs=kwargs))
