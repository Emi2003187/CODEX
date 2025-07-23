import pytest
from django.urls import reverse
from django.utils import timezone
from consultorio_API.models import Usuario, Paciente, Consulta, Consultorio, Cita
from consultorio_API.models import Consulta


def doctor_tiene_consulta_en_progreso(medico):
    return Consulta.objects.filter(medico=medico, estado="en_progreso").exists()

@pytest.mark.django_db
def test_doctor_solo_una_en_progreso(client):
    consultorio = Consultorio.objects.create(nombre="C1")
    medico = Usuario.objects.create(username="doc", rol="medico", first_name="Doc", consultorio=consultorio)
    paciente1 = Paciente.objects.create(nombre_completo="P1", fecha_nacimiento="2000-01-01", sexo='M', telefono='1', correo='a@a.com', direccion='x', consultorio=consultorio)
    paciente2 = Paciente.objects.create(nombre_completo="P2", fecha_nacimiento="2000-01-01", sexo='M', telefono='1', correo='b@b.com', direccion='x', consultorio=consultorio)
    c1 = Consulta.objects.create(paciente=paciente1, medico=medico, tipo='sin_cita', estado='en_progreso')
    c2 = Consulta.objects.create(paciente=paciente2, medico=medico, tipo='sin_cita', estado='espera')

    assert doctor_tiene_consulta_en_progreso(medico) is True

    client.force_login(medico)
    url = reverse('consultas_atencion', args=[c2.pk])
    client.get(url)
    c2.refresh_from_db()
    assert c2.estado == 'espera'

@pytest.mark.django_db
def test_form_consulta_solapa(db, client):
    consultorio = Consultorio.objects.create(nombre="C2")
    medico = Usuario.objects.create(username="doc2", rol="medico", first_name="Doc", consultorio=consultorio)
    paciente = Paciente.objects.create(nombre_completo="P3", fecha_nacimiento="2000-01-01", sexo='M', telefono='1', correo='c@c.com', direccion='x', consultorio=consultorio)
    # Cita ocupando horario actual
    inicio = timezone.now()
    Cita.objects.create(id='11111111-1111-1111-1111-111111111111', numero_cita='1', paciente=paciente, consultorio=consultorio, medico_asignado=medico, fecha_hora=inicio, duracion=30)

    client.force_login(medico)
    url = reverse('consultas_crear_sin_cita')
    data = {
        'paciente': paciente.pk,
        'medico': medico.pk,
        'motivo_consulta': 'test',
        'programar_para': 'ahora',
    }
    before = Consulta.objects.count()
    resp = client.post(url, data)
    after = Consulta.objects.count()
    assert after == before


@pytest.mark.django_db
def test_crear_consulta_desde_paciente(client):
    consultorio = Consultorio.objects.create(nombre="C3")
    medico = Usuario.objects.create(username="med3", rol="medico", first_name="Med", consultorio=consultorio)
    paciente = Paciente.objects.create(
        nombre_completo="P4",
        fecha_nacimiento="2000-01-01",
        sexo='M',
        telefono='1',
        correo='d@d.com',
        direccion='x',
        consultorio=consultorio,
    )

    client.force_login(medico)
    url = reverse('consultas_crear_desde_paciente', args=[paciente.pk])
    resp = client.get(url)
    content = resp.content.decode()
    assert f'value="{paciente.pk}"' in content
    assert 'type="hidden"' in content

    data = {
        'paciente': paciente.pk,
        'medico': medico.pk,
        'motivo_consulta': 'test',
        'programar_para': 'ahora',
    }
    before = Consulta.objects.count()
    client.post(url, data)
    after = Consulta.objects.count()
    assert after == before + 1
    consulta = Consulta.objects.latest('id')
    assert consulta.paciente == paciente
