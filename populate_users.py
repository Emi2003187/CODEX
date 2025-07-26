#!/usr/bin/env python3
"""Script para crear usuarios de prueba."""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'consultorio_medico.settings')
django.setup()

from consultorio_API.models import Usuario

USUARIOS = [
    {
        'username': 'adminprueba',
        'password': 'contraseña123456',
        'rol': 'admin',
        'is_superuser': True,
        'is_staff': True,
    },
    {
        'username': 'medicoprueba',
        'password': 'contraseña123456',
        'rol': 'medico',
        'is_superuser': False,
        'is_staff': False,
    },
    {
        'username': 'asistenteprueba',
        'password': 'contraseña123456',
        'rol': 'asistente',
        'is_superuser': False,
        'is_staff': False,
    },
]


def crear_usuario(data):
    username = data['username']
    if Usuario.objects.filter(username=username).exists():
        print(f"ℹ️  El usuario '{username}' ya existe")
        return

    usuario = Usuario(
        username=username,
        rol=data['rol'],
        is_superuser=data['is_superuser'],
        is_staff=data['is_staff'],
    )
    usuario.set_password(data['password'])
    usuario.save()
    print(f"✅ Usuario '{username}' creado")


def run():
    print("👥 Creando usuarios de prueba...")
    for data in USUARIOS:
        crear_usuario(data)
    print("✔️  Proceso completado")


if __name__ == '__main__':
    run()
