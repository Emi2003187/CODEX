#!/usr/bin/env python3
"""
Script para poblar la base de datos del sistema médico
con datos de prueba para el nuevo sistema de citas por consultorio
"""

import os
import sys
import django
from datetime import datetime, timedelta, time, date
from django.utils import timezone
import random

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'consultorio_medico.settings')
django.setup()

from consultorio_API.models import (
    Usuario, Paciente, Consultorio, Cita, Consulta, 
    SignosVitales, Expediente, Antecedente, MedicamentoActual,
    Receta, MedicamentoRecetado, HorarioMedico, Notificacion, Auditoria
)
from django.contrib.contenttypes.models import ContentType

def limpiar_base_datos():
    """Limpia todos los datos existentes"""
    print("🧹 Limpiando base de datos...")
    
    # Orden de eliminación para evitar problemas de FK
    modelos = [
        Auditoria, Notificacion, MedicamentoRecetado, Receta, SignosVitales,
        Consulta, Cita, MedicamentoActual, Antecedente, Expediente,
        HorarioMedico, Paciente, Usuario, Consultorio
    ]
    
    for modelo in modelos:
        count = modelo.objects.count()
        if count > 0:
            modelo.objects.all().delete()
            print(f"   🗑️ {modelo.__name__}: {count} registros eliminados")
    
    print("✅ Base de datos limpia")

def crear_administrador():
    """Crea el usuario administrador"""
    print("👨‍💼 Creando administrador...")
    
    admin = Usuario.objects.create_user(
        username='Emiliong',
        password='Shec!d1357',
        first_name='Emilio',
        last_name='González',
        email='admin@consultorio.com',
        rol='admin',
        telefono='+52-555-0001',
        is_staff=True,
        is_superuser=True
    )
    
    print("✅ Administrador creado")
    return admin

def crear_consultorios():
    """Crea los consultorios"""
    print("🏥 Creando consultorios...")
    
    consultorios_data = [
        {
            'nombre': 'Consultorio General A',
            'ubicacion': 'Planta Baja - Ala Norte',
            'capacidad_diaria': 25,
            'horario_apertura': time(8, 0),
            'horario_cierre': time(18, 0),
        },
        {
            'nombre': 'Consultorio General B',
            'ubicacion': 'Planta Baja - Ala Sur',
            'capacidad_diaria': 20,
            'horario_apertura': time(9, 0),
            'horario_cierre': time(17, 0),
        },
        {
            'nombre': 'Consultorio Pediatría',
            'ubicacion': 'Primer Piso - Zona Infantil',
            'capacidad_diaria': 30,
            'horario_apertura': time(8, 30),
            'horario_cierre': time(16, 30),
        },
        {
            'nombre': 'Consultorio Cardiología',
            'ubicacion': 'Segundo Piso - Especialidades',
            'capacidad_diaria': 15,
            'horario_apertura': time(10, 0),
            'horario_cierre': time(16, 0),
        },
        {
            'nombre': 'Consultorio Ginecología',
            'ubicacion': 'Primer Piso - Ala Este',
            'capacidad_diaria': 18,
            'horario_apertura': time(9, 0),
            'horario_cierre': time(17, 0),
        }
    ]
    
    consultorios = []
    for data in consultorios_data:
        consultorio = Consultorio.objects.create(**data)
        consultorios.append(consultorio)
        print(f"   📍 {consultorio.nombre}")
    
    print("✅ Consultorios creados")
    return consultorios

def crear_usuarios(consultorios):
    """Crea médicos y asistentes"""
    print("👨‍⚕️ Creando usuarios...")
    
    # Médicos
    medicos_data = [
        {
            'username': 'dr_martinez',
            'password': 'medico123',
            'first_name': 'Carlos',
            'last_name': 'Martínez López',
            'email': 'carlos.martinez@consultorio.com',
            'rol': 'medico',
            'telefono': '+52-555-1001',
            'cedula_profesional': '12345678',
            'institucion_cedula': 'UNAM',
            'consultorio': consultorios[0]  # General A
        },
        {
            'username': 'dra_rodriguez',
            'password': 'medico123',
            'first_name': 'Ana',
            'last_name': 'Rodríguez Pérez',
            'email': 'ana.rodriguez@consultorio.com',
            'rol': 'medico',
            'telefono': '+52-555-1002',
            'cedula_profesional': '87654321',
            'institucion_cedula': 'IPN',
            'consultorio': consultorios[1]  # General B
        },
        {
            'username': 'dr_garcia',
            'password': 'medico123',
            'first_name': 'Miguel',
            'last_name': 'García Hernández',
            'email': 'miguel.garcia@consultorio.com',
            'rol': 'medico',
            'telefono': '+52-555-1003',
            'cedula_profesional': '11223344',
            'institucion_cedula': 'UAM',
            'consultorio': consultorios[2]  # Pediatría
        },
        {
            'username': 'dra_lopez',
            'password': 'medico123',
            'first_name': 'Laura',
            'last_name': 'López Sánchez',
            'email': 'laura.lopez@consultorio.com',
            'rol': 'medico',
            'telefono': '+52-555-1004',
            'cedula_profesional': '44332211',
            'institucion_cedula': 'UNAM',
            'consultorio': consultorios[3]  # Cardiología
        },
        {
            'username': 'dr_hernandez',
            'password': 'medico123',
            'first_name': 'Roberto',
            'last_name': 'Hernández Morales',
            'email': 'roberto.hernandez@consultorio.com',
            'rol': 'medico',
            'telefono': '+52-555-1005',
            'cedula_profesional': '55667788',
            'institucion_cedula': 'IPN',
            'consultorio': consultorios[4]  # Ginecología
        },
        # Médicos adicionales para algunos consultorios
        {
            'username': 'dra_torres',
            'password': 'medico123',
            'first_name': 'Patricia',
            'last_name': 'Torres Jiménez',
            'email': 'patricia.torres@consultorio.com',
            'rol': 'medico',
            'telefono': '+52-555-1006',
            'cedula_profesional': '99887766',
            'institucion_cedula': 'UNAM',
            'consultorio': consultorios[0]  # General A (segundo médico)
        },
        {
            'username': 'dr_ramirez',
            'password': 'medico123',
            'first_name': 'Fernando',
            'last_name': 'Ramírez Castro',
            'email': 'fernando.ramirez@consultorio.com',
            'rol': 'medico',
            'telefono': '+52-555-1007',
            'cedula_profesional': '66554433',
            'institucion_cedula': 'UAM',
            'consultorio': consultorios[1]  # General B (segundo médico)
        }
    ]
    
    # Asistentes
    asistentes_data = [
        {
            'username': 'asist_maria',
            'password': 'asistente123',
            'first_name': 'María',
            'last_name': 'González Ruiz',
            'email': 'maria.gonzalez@consultorio.com',
            'rol': 'asistente',
            'telefono': '+52-555-2001',
            'consultorio': consultorios[0]  # General A
        },
        {
            'username': 'asist_carmen',
            'password': 'asistente123',
            'first_name': 'Carmen',
            'last_name': 'Díaz Flores',
            'email': 'carmen.diaz@consultorio.com',
            'rol': 'asistente',
            'telefono': '+52-555-2002',
            'consultorio': consultorios[1]  # General B
        },
        {
            'username': 'asist_sofia',
            'password': 'asistente123',
            'first_name': 'Sofía',
            'last_name': 'Moreno Vega',
            'email': 'sofia.moreno@consultorio.com',
            'rol': 'asistente',
            'telefono': '+52-555-2003',
            'consultorio': consultorios[2]  # Pediatría
        },
        {
            'username': 'asist_lucia',
            'password': 'asistente123',
            'first_name': 'Lucía',
            'last_name': 'Herrera Ortiz',
            'email': 'lucia.herrera@consultorio.com',
            'rol': 'asistente',
            'telefono': '+52-555-2004',
            'consultorio': consultorios[3]  # Cardiología
        },
        {
            'username': 'asist_elena',
            'password': 'asistente123',
            'first_name': 'Elena',
            'last_name': 'Vargas Mendoza',
            'email': 'elena.vargas@consultorio.com',
            'rol': 'asistente',
            'telefono': '+52-555-2005',
            'consultorio': consultorios[4]  # Ginecología
        }
    ]
    
    usuarios = []
    
    # Crear médicos
    for data in medicos_data:
        usuario = Usuario.objects.create_user(**data)
        usuarios.append(usuario)
        print(f"   👨‍⚕️ Dr. {usuario.get_full_name()} - {usuario.consultorio.nombre}")
    
    # Crear asistentes
    for data in asistentes_data:
        usuario = Usuario.objects.create_user(**data)
        usuarios.append(usuario)
        print(f"   👩‍💼 {usuario.get_full_name()} - {usuario.consultorio.nombre}")
    
    print("✅ Usuarios creados")
    return usuarios

def crear_pacientes(admin_user):
    """Crea pacientes de prueba"""
    print("👥 Creando pacientes...")
    
    pacientes_data = [
        {
            'nombre_completo': 'Juan Carlos Pérez Martínez',
            'fecha_nacimiento': date(1985, 3, 15),
            'sexo': 'M',
            'telefono': '+52-555-3001',
            'correo': 'juan.perez@email.com',
            'direccion': 'Av. Insurgentes Sur 1234, Col. Del Valle, CDMX',
        },
        {
            'nombre_completo': 'Ana Sofía González López',
            'fecha_nacimiento': date(1992, 7, 22),
            'sexo': 'F',
            'telefono': '+52-555-3002',
            'correo': 'ana.gonzalez@email.com',
            'direccion': 'Calle Reforma 567, Col. Centro, CDMX',
        },
        {
            'nombre_completo': 'Carlos Eduardo Ramírez Torres',
            'fecha_nacimiento': date(1978, 11, 8),
            'sexo': 'M',
            'telefono': '+52-555-3003',
            'correo': 'carlos.ramirez@email.com',
            'direccion': 'Blvd. Manuel Ávila Camacho 890, Col. Lomas, CDMX',
        },
        {
            'nombre_completo': 'María Elena Hernández Díaz',
            'fecha_nacimiento': date(1965, 4, 30),
            'sexo': 'F',
            'telefono': '+52-555-3004',
            'correo': 'maria.hernandez@email.com',
            'direccion': 'Av. Universidad 345, Col. Copilco, CDMX',
        },
        {
            'nombre_completo': 'Roberto Alejandro Morales Vega',
            'fecha_nacimiento': date(1990, 12, 12),
            'sexo': 'M',
            'telefono': '+52-555-3005',
            'correo': 'roberto.morales@email.com',
            'direccion': 'Calle Madero 678, Col. Roma Norte, CDMX',
        },
        # Pacientes pediátricos
        {
            'nombre_completo': 'Sofía Isabella Jiménez Cruz',
            'fecha_nacimiento': date(2015, 6, 18),
            'sexo': 'F',
            'telefono': '+52-555-3006',
            'correo': 'contacto.sofia@email.com',
            'direccion': 'Av. Patriotismo 234, Col. San Pedro de los Pinos, CDMX',
        },
        {
            'nombre_completo': 'Diego Mateo López Sánchez',
            'fecha_nacimiento': date(2012, 9, 5),
            'sexo': 'M',
            'telefono': '+52-555-3007',
            'correo': 'contacto.diego@email.com',
            'direccion': 'Calle Orizaba 456, Col. Roma Sur, CDMX',
        },
        # Más pacientes adultos
        {
            'nombre_completo': 'Patricia Guadalupe Torres Mendoza',
            'fecha_nacimiento': date(1988, 1, 25),
            'sexo': 'F',
            'telefono': '+52-555-3008',
            'correo': 'patricia.torres@email.com',
            'direccion': 'Av. Revolución 789, Col. Mixcoac, CDMX',
        },
        {
            'nombre_completo': 'Fernando Gabriel Castillo Ruiz',
            'fecha_nacimiento': date(1975, 8, 14),
            'sexo': 'M',
            'telefono': '+52-555-3009',
            'correo': 'fernando.castillo@email.com',
            'direccion': 'Calle Amsterdam 123, Col. Condesa, CDMX',
        },
        {
            'nombre_completo': 'Claudia Beatriz Vargas Herrera',
            'fecha_nacimiento': date(1995, 2, 28),
            'sexo': 'F',
            'telefono': '+52-555-3010',
            'correo': 'claudia.vargas@email.com',
            'direccion': 'Av. Chapultepec 456, Col. Juárez, CDMX',
        },
        {
            'nombre_completo': 'Luis Alberto Mendoza Silva',
            'fecha_nacimiento': date(1982, 10, 17),
            'sexo': 'M',
            'telefono': '+52-555-3011',
            'correo': 'luis.mendoza@email.com',
            'direccion': 'Calle Insurgentes Norte 789, Col. Guerrero, CDMX',
        },
        {
            'nombre_completo': 'Carmen Rosa Flores Jiménez',
            'fecha_nacimiento': date(1970, 5, 12),
            'sexo': 'F',
            'telefono': '+52-555-3012',
            'correo': 'carmen.flores@email.com',
            'direccion': 'Av. Cuauhtémoc 234, Col. Doctores, CDMX',
        },
        {
            'nombre_completo': 'Alejandro José Ruiz Moreno',
            'fecha_nacimiento': date(1993, 8, 3),
            'sexo': 'M',
            'telefono': '+52-555-3013',
            'correo': 'alejandro.ruiz@email.com',
            'direccion': 'Calle Álvaro Obregón 567, Col. Roma Norte, CDMX',
        },
        {
            'nombre_completo': 'Gabriela Monserrat Cruz Herrera',
            'fecha_nacimiento': date(1987, 12, 20),
            'sexo': 'F',
            'telefono': '+52-555-3014',
            'correo': 'gabriela.cruz@email.com',
            'direccion': 'Av. División del Norte 890, Col. Portales, CDMX',
        },
        {
            'nombre_completo': 'Ricardo Emilio Sánchez López',
            'fecha_nacimiento': date(1976, 3, 8),
            'sexo': 'M',
            'telefono': '+52-555-3015',
            'correo': 'ricardo.sanchez@email.com',
            'direccion': 'Calle Eje Central 123, Col. Centro Histórico, CDMX',
        },
        # Más pacientes pediátricos
        {
            'nombre_completo': 'Emilia Valentina Ortega Díaz',
            'fecha_nacimiento': date(2016, 4, 22),
            'sexo': 'F',
            'telefono': '+52-555-3016',
            'correo': 'contacto.emilia@email.com',
            'direccion': 'Av. Coyoacán 456, Col. Del Valle, CDMX',
        },
        {
            'nombre_completo': 'Santiago Matías Vega Torres',
            'fecha_nacimiento': date(2013, 11, 15),
            'sexo': 'M',
            'telefono': '+52-555-3017',
            'correo': 'contacto.santiago@email.com',
            'direccion': 'Calle Tlalpan 789, Col. Narvarte, CDMX',
        },
        {
            'nombre_completo': 'Isabella Camila Herrera Ruiz',
            'fecha_nacimiento': date(2014, 7, 9),
            'sexo': 'F',
            'telefono': '+52-555-3018',
            'correo': 'contacto.isabella@email.com',
            'direccion': 'Av. Insurgentes Centro 234, Col. Tabacalera, CDMX',
        },
        {
            'nombre_completo': 'Sebastián Alejandro Morales Cruz',
            'fecha_nacimiento': date(2011, 2, 28),
            'sexo': 'M',
            'telefono': '+52-555-3019',
            'correo': 'contacto.sebastian@email.com',
            'direccion': 'Calle Doctores 567, Col. Obrera, CDMX',
        },
        {
            'nombre_completo': 'Valeria Nicole Jiménez Sánchez',
            'fecha_nacimiento': date(2017, 9, 14),
            'sexo': 'F',
            'telefono': '+52-555-3020',
            'correo': 'contacto.valeria@email.com',
            'direccion': 'Av. Río Churubusco 890, Col. Granjas México, CDMX',
        }
    ]
    
    pacientes = []

    # Obtener cualquier médico para asignar como consultorio por defecto
    medico_asignado = Usuario.objects.filter(rol="medico", consultorio__isnull=False).first()
    if not medico_asignado:
        print("❌ No hay médicos disponibles para asignar a los pacientes.")
        return []

    for data in pacientes_data:
        try:
            paciente = Paciente(**data, consultorio=medico_asignado.consultorio)
            paciente.save()

            # Auditoría
            try:
                Auditoria.objects.create(
                    usuario=admin_user,
                    accion='CREATE',
                    descripcion=f'Paciente {paciente.nombre_completo} creado durante población de BD',
                    content_type=ContentType.objects.get_for_model(Paciente),
                    object_id=paciente.id
                )
            except Exception:
                print(f"   ⚠️ Advertencia: No se pudo crear auditoría para {paciente.nombre_completo}")

            pacientes.append(paciente)
            print(f"   👤 {paciente.nombre_completo} ({paciente.edad} años)")

        except Exception as e:
            print(f"   ❌ Error creando paciente: {e}")

    print("✅ Pacientes creados")
    return pacientes

def crear_citas(consultorios, pacientes, admin_user):
    """Crea citas de prueba para el nuevo sistema"""
    print("📅 Creando citas...")
    
    # Obtener médicos por consultorio
    medicos_por_consultorio = {}
    for consultorio in consultorios:
        medicos_por_consultorio[consultorio.id] = list(
            Usuario.objects.filter(rol='medico', consultorio=consultorio)
        )
    
    citas = []
    hoy = timezone.now().date()
    
    # Crear citas para los próximos 14 días
    for dias_adelante in range(-7, 14):  # 7 días atrás y 14 adelante
        fecha = hoy + timedelta(days=dias_adelante)
        
        # Saltar fines de semana
        if fecha.weekday() >= 5:
            continue
        
        # Crear entre 8-15 citas por día
        num_citas = random.randint(8, 15)
        
        for _ in range(num_citas):
            # Seleccionar consultorio aleatorio
            consultorio = random.choice(consultorios)
            
            # Seleccionar paciente aleatorio
            paciente = random.choice(pacientes)
            
            # Generar hora aleatoria dentro del horario del consultorio
            hora_inicio = consultorio.horario_apertura
            hora_fin = consultorio.horario_cierre
            
            # Convertir a minutos para facilitar cálculos
            minutos_inicio = hora_inicio.hour * 60 + hora_inicio.minute
            minutos_fin = hora_fin.hour * 60 + hora_fin.minute
            
            # Generar hora aleatoria
            minutos_cita = random.randint(minutos_inicio, minutos_fin - 60)
            hora_cita = time(minutos_cita // 60, (minutos_cita % 60) // 15 * 15)  # Redondear a 15 min
            
            fecha_hora = timezone.make_aware(
                datetime.combine(fecha, hora_cita)
            )
            
            # Determinar estado según la fecha
            if fecha < hoy:
                estados_pasados = ['completada', 'no_asistio', 'cancelada']
                estado = random.choice(estados_pasados)
            elif fecha == hoy:
                estados_hoy = ['en_espera', 'en_atencion', 'completada', 'programada']
                estado = random.choice(estados_hoy)
            else:
                estados_futuros = ['programada', 'confirmada']
                estado = random.choice(estados_futuros)
            
            # Seleccionar médico preferido (opcional)
            medicos_consultorio = medicos_por_consultorio.get(consultorio.id, [])
            medico_preferido = random.choice(medicos_consultorio) if medicos_consultorio and random.random() < 0.3 else None
            
            # Asignar médico si la cita está confirmada o en proceso
            medico_asignado = None
            if estado in ['confirmada', 'en_espera', 'en_atencion', 'completada']:
                if medico_preferido and random.random() < 0.7:
                    medico_asignado = medico_preferido
                elif medicos_consultorio:
                    medico_asignado = random.choice(medicos_consultorio)
            
            # Datos de la cita
            motivos = [
                'Consulta general', 'Control médico', 'Dolor abdominal',
                'Revisión de presión arterial', 'Consulta por gripe',
                'Chequeo preventivo', 'Seguimiento de tratamiento',
                'Dolor de cabeza', 'Consulta dermatológica',
                'Revisión de análisis', 'Consulta por alergias'
            ]
            
            tipos_cita = ['primera_vez', 'control', 'urgencia']
            prioridades = ['normal', 'alta', 'baja']
            
            try:
                cita = Cita.objects.create(
                    paciente=paciente,
                    consultorio=consultorio,
                    medico_preferido=medico_preferido,
                    medico_asignado=medico_asignado,
                    fecha_hora=fecha_hora,
                    duracion=random.choice([30, 45, 60]),
                    tipo_cita=random.choice(tipos_cita),
                    prioridad=random.choice(prioridades),
                    estado=estado,
                    motivo=random.choice(motivos),
                    telefono_contacto=paciente.telefono,
                    email_recordatorio=paciente.correo,
                    fecha_asignacion_medico=timezone.now() if medico_asignado else None,
                    creado_por=admin_user
                )
                citas.append(cita)
                
            except Exception as e:
                # Si hay conflicto de horario, continuar
                continue
    
    print(f"✅ {len(citas)} citas creadas")
    return citas

def crear_consultas_y_datos_medicos(citas):
    """Crea consultas y datos médicos asociados"""
    print("🏥 Creando consultas y datos médicos...")
    
    consultas_creadas = 0
    
    # Crear consultas para citas completadas y en atención
    citas_con_consulta = [c for c in citas if c.estado in ['completada', 'en_atencion']]
    
    for cita in citas_con_consulta:
        if not cita.medico_asignado:
            continue
            
        try:
            # Crear consulta
            consulta = Consulta.objects.create(
                paciente=cita.paciente,
                cita=cita,
                medico=cita.medico_asignado,
                tipo='con_cita',
                estado='finalizada' if cita.estado == 'completada' else 'en_progreso',
                motivo_consulta=cita.motivo,
                fecha_atencion=cita.fecha_hora if cita.estado == 'completada' else None,
                diagnostico='Diagnóstico de ejemplo' if cita.estado == 'completada' else '',
                tratamiento='Tratamiento recomendado' if cita.estado == 'completada' else '',
                observaciones='Observaciones médicas de ejemplo'
            )
            
            # Crear signos vitales (50% de probabilidad)
            if random.random() < 0.5:
                SignosVitales.objects.create(
                    consulta=consulta,
                    tension_arterial=f"{random.randint(110, 140)}/{random.randint(70, 90)}",
                    frecuencia_cardiaca=random.randint(60, 100),
                    frecuencia_respiratoria=random.randint(12, 20),
                    temperatura=round(random.uniform(36.0, 37.5), 1),
                    peso=round(random.uniform(50.0, 100.0), 1),
                    talla=round(random.uniform(1.50, 1.90), 2),
                    alergias='Ninguna conocida' if random.random() < 0.7 else 'Penicilina',
                    sintomas='Síntomas reportados por el paciente'
                )
            
            consultas_creadas += 1
            
        except Exception as e:
            continue
    
    print(f"✅ {consultas_creadas} consultas creadas")

def crear_expedientes_y_antecedentes(pacientes):
    """Crea expedientes y antecedentes médicos"""
    print("📋 Creando expedientes médicos...")
    
    expedientes_creados = 0
    
    for paciente in pacientes:
        try:
            # Verificar si ya existe un expediente (por el signal)
            expediente, created = Expediente.objects.get_or_create(
                paciente=paciente,
                defaults={'notas_generales': f'Expediente médico de {paciente.nombre_completo}'}
            )
            
            if created:
                expedientes_creados += 1
            
            # Crear algunos antecedentes (30% de probabilidad)
            if random.random() < 0.3:
                tipos_antecedentes = ['personal', 'familiar', 'quirurgico', 'alergico']
                
                for _ in range(random.randint(1, 3)):
                    Antecedente.objects.create(
                        expediente=expediente,
                        tipo=random.choice(tipos_antecedentes),
                        descripcion='Antecedente médico de ejemplo',
                        fecha_diagnostico=date.today() - timedelta(days=random.randint(30, 1000)),
                        severidad='Leve',
                        estado_actual='Controlado',
                        notas='Notas adicionales del antecedente'
                    )
            
            # Crear medicamentos actuales (20% de probabilidad)
            if random.random() < 0.2:
                medicamentos = ['Paracetamol', 'Ibuprofeno', 'Losartán', 'Metformina']
                
                for _ in range(random.randint(1, 2)):
                    MedicamentoActual.objects.create(
                        expediente=expediente,
                        nombre=random.choice(medicamentos),
                        principio_activo=random.choice(medicamentos),
                        dosis='500 mg',
                        frecuencia='Cada 8 horas',
                        via_administracion='Oral',
                        proposito='Tratamiento médico',
                        inicio=date.today() - timedelta(days=random.randint(1, 90)),
                        prescrito_por='Dr. Ejemplo'
                    )
            
        except Exception as e:
            continue
    
    print(f"✅ {expedientes_creados} expedientes creados")

def crear_horarios_medicos():
    """Crea horarios para los médicos"""
    print("⏰ Creando horarios médicos...")
    
    medicos = Usuario.objects.filter(rol='medico')
    horarios_creados = 0
    
    dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    
    for medico in medicos:
        # Crear horario de lunes a viernes
        for dia in dias_semana:
            try:
                HorarioMedico.objects.create(
                    medico=medico,
                    consultorio=medico.consultorio,
                    dia=dia,
                    hora_inicio=time(9, 0),
                    hora_fin=time(17, 0)
                )
                horarios_creados += 1
            except Exception as e:
                continue
    
    print(f"✅ {horarios_creados} horarios creados")

def crear_notificaciones():
    """Crea algunas notificaciones de ejemplo"""
    print("🔔 Creando notificaciones...")
    
    medicos = Usuario.objects.filter(rol='medico')
    notificaciones_creadas = 0
    
    mensajes = [
        'Nueva cita disponible para tomar',
        'Recordatorio: Cita en 30 minutos',
        'Paciente ha llegado para su cita',
        'Actualización en el sistema médico',
        'Nueva política de consultas'
    ]
    
    for medico in medicos:
        # Crear 2-4 notificaciones por médico
        for _ in range(random.randint(2, 4)):
            try:
                Notificacion.objects.create(
                    destinatario=medico,
                    mensaje=random.choice(mensajes),
                    leido=random.choice([True, False])
                )
                notificaciones_creadas += 1
            except Exception as e:
                continue
    
    print(f"✅ {notificaciones_creadas} notificaciones creadas")

def mostrar_resumen():
    """Muestra un resumen de los datos creados"""
    print("\n" + "="*60)
    print("📊 RESUMEN DE DATOS CREADOS")
    print("="*60)
    
    print(f"👨‍💼 Usuarios: {Usuario.objects.count()}")
    print(f"   - Administradores: {Usuario.objects.filter(rol='admin').count()}")
    print(f"   - Médicos: {Usuario.objects.filter(rol='medico').count()}")
    print(f"   - Asistentes: {Usuario.objects.filter(rol='asistente').count()}")
    
    print(f"🏥 Consultorios: {Consultorio.objects.count()}")
    print(f"👥 Pacientes: {Paciente.objects.count()}")
    print(f"📅 Citas: {Cita.objects.count()}")
    
    # Estadísticas de citas por estado
    for estado, nombre in Cita.ESTADO_CHOICES:
        count = Cita.objects.filter(estado=estado).count()
        if count > 0:
            print(f"   - {nombre}: {count}")
    
    print(f"🏥 Consultas: {Consulta.objects.count()}")
    print(f"📋 Expedientes: {Expediente.objects.count()}")
    print(f"⏰ Horarios médicos: {HorarioMedico.objects.count()}")
    print(f"🔔 Notificaciones: {Notificacion.objects.count()}")
    print(f"📝 Auditorías: {Auditoria.objects.count()}")
    
    print("\n" + "="*60)
    print("🎉 ¡POBLACIÓN DE BASE DE DATOS COMPLETADA!")
    print("="*60)
    
    print("\n🔐 CREDENCIALES DE ACCESO:")
    print("-" * 30)
    print("👨‍💼 Administrador:")
    print("   Usuario: Emiliong")
    print("   Contraseña: Shec!d1357")
    print("\n👨‍⚕️ Médicos:")
    print("   Usuario: dr_martinez, dra_rodriguez, dr_garcia, etc.")
    print("   Contraseña: medico123")
    print("\n👩‍💼 Asistentes:")
    print("   Usuario: asist_maria, asist_carmen, asist_sofia, etc.")
    print("   Contraseña: asistente123")

def run():
    """Función principal que ejecuta todo el proceso"""
    print("🆕 NUEVO SISTEMA: Citas asignadas a CONSULTORIO, no a médico específico")
    print("="*80)
    
    try:
        # 1. Limpiar base de datos SIEMPRE
        limpiar_base_datos()
        
        # 2. Crear administrador
        admin = crear_administrador()
        
        # 3. Crear consultorios
        consultorios = crear_consultorios()
        
        # 4. Crear usuarios (médicos y asistentes)
        usuarios = crear_usuarios(consultorios)
        
        # 5. Crear pacientes (pasando admin para auditoría)
        pacientes = crear_pacientes(admin)
        
        # 6. Crear citas
        citas = crear_citas(consultorios, pacientes, admin)
        
        # 7. Crear consultas y datos médicos
        crear_consultas_y_datos_medicos(citas)
        
        # 8. Crear expedientes y antecedentes
        crear_expedientes_y_antecedentes(pacientes)
        
        # 9. Crear horarios médicos
        crear_horarios_medicos()
        
        # 10. Crear notificaciones
        crear_notificaciones()
        
        # 11. Mostrar resumen
        mostrar_resumen()
        
    except Exception as e:
        print(f"❌ Error durante la población: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run()
