import pytest
from django.urls import reverse
from django.utils import timezone
from consultorio_API.models import Paciente, Cita, Consultorio, Usuario

@pytest.mark.django_db
def test_ajax_citas_previas_filtra_fecha_hora(client):
    consultorio = Consultorio.objects.create(nombre="CF")
    admin = Usuario.objects.create(username="u", rol="admin", is_superuser=True)
    client.force_login(admin)
    paciente = Paciente.objects.create(nombre_completo="P", fecha_nacimiento="2000-01-01", sexo="M", telefono="1", correo="p@p.com", direccion="x", consultorio=consultorio)
    antes = timezone.now() - timezone.timedelta(days=3)
    middle = timezone.now() - timezone.timedelta(days=1)
    despues = timezone.now() + timezone.timedelta(days=2)
    c1 = Cita.objects.create(numero_cita="1", paciente=paciente, consultorio=consultorio, fecha_hora=antes, duracion=30)
    c2 = Cita.objects.create(numero_cita="2", paciente=paciente, consultorio=consultorio, fecha_hora=middle, duracion=30)
    Cita.objects.create(numero_cita="3", paciente=paciente, consultorio=consultorio, fecha_hora=despues, duracion=30)

    fecha = (timezone.now() + timezone.timedelta(hours=1)).date().isoformat()
    url = reverse("ajax_citas_previas")
    resp = client.get(url, {"paciente_id": paciente.id, "fecha": fecha, "hora": "00:00"})
    data = resp.json()["citas"]
    ids = [c["id"] for c in data]
    assert ids == [str(c1.id), str(c2.id)]

@pytest.mark.django_db
def test_ajax_citas_previas_solo_fecha(client):
    consultorio = Consultorio.objects.create(nombre="CF2")
    admin = Usuario.objects.create(username="u2", rol="admin", is_superuser=True)
    client.force_login(admin)
    paciente = Paciente.objects.create(nombre_completo="P2", fecha_nacimiento="2000-01-01", sexo="M", telefono="1", correo="p2@p.com", direccion="x", consultorio=consultorio)
    antes = timezone.now() - timezone.timedelta(days=5)
    despues = timezone.now() + timezone.timedelta(days=1)
    c1 = Cita.objects.create(numero_cita="10", paciente=paciente, consultorio=consultorio, fecha_hora=antes, duracion=30)
    Cita.objects.create(numero_cita="11", paciente=paciente, consultorio=consultorio, fecha_hora=despues, duracion=30)

    fecha = timezone.now().date().isoformat()
    url = reverse("ajax_citas_previas")
    resp = client.get(url, {"paciente_id": paciente.id, "fecha": fecha})
    data = resp.json()["citas"]
    assert len(data) == 1
    assert data[0]["id"] == str(c1.id)
