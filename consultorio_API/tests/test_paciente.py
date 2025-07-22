import pytest
from django.urls import reverse
from consultorio_API.models import Usuario, Paciente, Consultorio

@pytest.mark.django_db
def test_medico_crea_paciente_auto_consultorio(client):
    consultorio = Consultorio.objects.create(nombre="CMed")
    medico = Usuario.objects.create(username="med", rol="medico", first_name="Med", consultorio=consultorio)
    client.force_login(medico)
    url = reverse('pacientes_crear')
    resp = client.get(url)
    assert 'name="consultorio"' not in resp.content.decode()
    data = {
        'nombre_completo': 'Juan Perez',
        'fecha_nacimiento': '2000-01-01',
        'sexo': 'M',
        'telefono': '123',
        'correo': 'jp@example.com',
        'direccion': 'X',
    }
    client.post(url, data)
    paciente = Paciente.objects.get(nombre_completo='Juan Perez')
    assert paciente.consultorio == consultorio

@pytest.mark.django_db
def test_admin_crea_paciente_selecciona_consultorio(client):
    c1 = Consultorio.objects.create(nombre="C1")
    c2 = Consultorio.objects.create(nombre="C2")
    admin = Usuario.objects.create(username="admin", rol="admin", first_name="Admin", is_superuser=True)
    client.force_login(admin)
    url = reverse('pacientes_crear')
    resp = client.get(url)
    assert 'name="consultorio"' in resp.content.decode()
    data = {
        'nombre_completo': 'Ana',
        'fecha_nacimiento': '1999-01-01',
        'sexo': 'F',
        'telefono': '555',
        'correo': 'ana@example.com',
        'direccion': 'Y',
        'consultorio': c2.id,
    }
    client.post(url, data)
    paciente = Paciente.objects.get(nombre_completo='Ana')
    assert paciente.consultorio == c2
