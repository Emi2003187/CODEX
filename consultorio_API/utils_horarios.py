from datetime import date, datetime, time, timedelta
from typing import List, Dict

from django.utils import timezone
from .models import Cita, Consultorio

PASO = 15
ESTADOS_ACTIVOS = ("programada", "confirmada", "en_espera", "en_atencion")


def _minutos(h: time) -> int:
    return h.hour * 60 + h.minute


def _to_local(dt: datetime) -> datetime:
    return timezone.localtime(dt).replace(tzinfo=None) if timezone.is_aware(dt) else dt


def obtener_horarios_disponibles_para_select(
    consultorio: Consultorio,
    dia: date,
    duracion_requerida: int | None = 30,
    excluir_id: int | None = None,
) -> List[Dict]:
    # 1) normalizar duración solicitada
    try:
        dur_req = int(duracion_requerida or 30)
    except (TypeError, ValueError):
        dur_req = 30
    dur_req = max(PASO, (dur_req + PASO - 1) // PASO * PASO)

    # 2) horario del consultorio
    ap = consultorio.horario_apertura or time(7, 0)
    ci = consultorio.horario_cierre or time(18, 0)
    ap_min, ci_min = _minutos(ap), _minutos(ci)
    if ci_min <= ap_min:
        return []

    # 3) citas activas del día
    inicio_dia = datetime.combine(dia, time.min)
    fin_dia = inicio_dia + timedelta(days=1)

    qs = Cita.objects.filter(
        consultorio=consultorio,
        fecha_hora__gte=inicio_dia,
        fecha_hora__lt=fin_dia,
        estado__in=ESTADOS_ACTIVOS,
    )
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)

    minutos_bloqueados: set[int] = set()

    for c in qs.only("fecha_hora", "duracion"):
        inicio = _to_local(c.fecha_hora)
        m_ini = _minutos(inicio.time())
        m_fin = m_ini + c.duracion
        # 🔴  Inicios desde m_ini hasta m_fin INCLUSIVE
        for m in range(m_ini, m_fin + PASO, PASO):
            minutos_bloqueados.add(m)

    # 4) construir respuesta
    resp: list[Dict] = []
    for m_ini in range(ap_min, ci_min, PASO):
        if m_ini + dur_req > ci_min:
            break
        libre = m_ini not in minutos_bloqueados
        h24, minute = divmod(m_ini, 60)
        h12 = (h24 % 12) or 12
        ampm = "AM" if h24 < 12 else "PM"
        resp.append(
            {
                "value": f"{h24:02d}:{minute:02d}",
                "text": f"{h12}:{minute:02d} {ampm}",
                "estado": "libre" if libre else "ocupado",
            }
        )
    return resp
