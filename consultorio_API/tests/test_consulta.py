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
    assert 'disabled' in content

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


@pytest.mark.django_db
def test_no_crear_consulta_antes_de_cita(client):
    consultorio = Consultorio.objects.create(nombre="CF")
    medico = Usuario.objects.create(
        username="medf", rol="medico", first_name="Med", consultorio=consultorio
    )
    paciente = Paciente.objects.create(
        nombre_completo="PF",
        fecha_nacimiento="2000-01-01",
        sexo="M",
        telefono="1",
        correo="pf@example.com",
        direccion="X",
        consultorio=consultorio,
    )
    cita = Cita.objects.create(
        id="22222222-2222-2222-2222-222222222222",
        numero_cita="10",
        paciente=paciente,
        consultorio=consultorio,
        medico_asignado=medico,
        fecha_hora=timezone.now() + timezone.timedelta(hours=1),
        duracion=30,
        estado="programada",
    )

    client.force_login(medico)
    url = reverse("citas_crear_desde_cita", args=[cita.id])
    before = Consulta.objects.count()
    resp = client.post(url, follow=True)
    after = Consulta.objects.count()
    assert after == before + 1
    assert "Consulta creada" in resp.content.decode() or resp.status_code == 302


@pytest.mark.django_db
def test_bloqueo_registrar_signos_cancelada(client):
    consultorio = Consultorio.objects.create(nombre="BC")
    medico = Usuario.objects.create(username="medb", rol="medico", first_name="Med", consultorio=consultorio)
    paciente = Paciente.objects.create(
        nombre_completo="PB",
        fecha_nacimiento="2000-01-01",
        sexo="M",
        telefono="1",
        correo="pb@example.com",
        direccion="X",
        consultorio=consultorio,
    )
    consulta = Consulta.objects.create(paciente=paciente, medico=medico, tipo="sin_cita", estado="cancelada")

    client.force_login(medico)
    url = reverse("consultas_precheck", args=[consulta.pk])
    resp = client.get(url, follow=True)
    assert resp.redirect_chain
    assert "No se pueden registrar signos vitales" in resp.content.decode()


@pytest.mark.django_db
def test_bloqueo_editar_consulta_cancelada(client):
    consultorio = Consultorio.objects.create(nombre="BE")
    medico = Usuario.objects.create(username="mede", rol="medico", first_name="Med", consultorio=consultorio)
    paciente = Paciente.objects.create(
        nombre_completo="PE",
        fecha_nacimiento="2000-01-01",
        sexo="M",
        telefono="1",
        correo="pe@example.com",
        direccion="X",
        consultorio=consultorio,
    )
    consulta = Consulta.objects.create(paciente=paciente, medico=medico, tipo="sin_cita", estado="cancelada")

    client.force_login(medico)
    url = reverse("consulta_editar", args=[consulta.pk])
    resp = client.get(url, follow=True)
    assert resp.redirect_chain
    assert "No puedes editar una consulta cancelada" in resp.content.decode()
