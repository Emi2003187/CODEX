from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from datetime import datetime, timedelta, time
import json
import csv
from consultorio_API.utils_horarios import obtener_horarios_disponibles_para_select
from django.urls import reverse_lazy
from .utils import redirect_next
from django.views.decorators.http import require_POST

# Importaciones de modelos
from .models import (
    Cita, Consulta, Paciente, Usuario, Consultorio, 
    SignosVitales, Receta, MedicamentoRecetado,
    Expediente, Antecedente, MedicamentoActual, HorarioMedico,
    Notificacion
)

# Importaciones de formularios
from .forms import (
    CitaForm, CitaFiltroForm, AsignarMedicoForm,
    ConsultaSinCitaForm, SignosVitalesForm, RecetaForm,
    PacienteForm, ExpedienteForm, AntecedenteForm, MedicamentoActualForm
)

# ═══════════════════════════════════════════════════════════════
# 🔐 MIXINS DE PERMISOS
# ═══════════════════════════════════════════════════════════════

class CitaPermisoMixin(UserPassesTestMixin):
    """Mixin para verificar permisos de citas"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.rol in ('medico', 'asistente', 'admin')


class MedicoRequiredMixin(UserPassesTestMixin):
    """Mixin que requiere rol de médico"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.rol == 'medico'


# ═══════════════════════════════════════════════════════════════
# 📅 VISTAS PRINCIPALES DE CITAS
# ═══════════════════════════════════════════════════════════════

@login_required
def lista_citas(request):
    """Lista de citas filtrada por consultorio del usuario - CORREGIDA"""
    user = request.user
    
    # Filtro base según el rol del usuario
    if user.rol == 'admin':
        citas = Cita.objects.all()
    elif user.rol == 'medico':
        # Médico ve: citas de su consultorio + citas asignadas a él
        citas = Cita.objects.filter(
            Q(consultorio=user.consultorio) | Q(medico_asignado=user)
        )
    elif user.rol == 'asistente':
        # Asistente ve solo citas de su consultorio
        if user.consultorio:
            citas = Cita.objects.filter(consultorio=user.consultorio)
        else:
            citas = Cita.objects.none()
    else:
        citas = Cita.objects.none()
    
    # Aplicar filtros adicionales
    filtro_form = CitaFiltroForm(request.GET, user=user)
    if filtro_form.is_valid():
        cd = filtro_form.cleaned_data
        
        if cd.get('buscar'):
            citas = citas.filter(
                Q(paciente__nombre_completo__icontains=cd['buscar']) |
                Q(numero_cita__icontains=cd['buscar']) |
                Q(motivo__icontains=cd['buscar'])
            )
        
        if cd.get('fecha_desde'):
            citas = citas.filter(fecha_hora__date__gte=cd['fecha_desde'])
        if cd.get('fecha_hasta'):
            citas = citas.filter(fecha_hora__date__lte=cd['fecha_hasta'])
        if cd.get('estado'):
            citas = citas.filter(estado=cd['estado'])
        if cd.get('tipo_cita'):
            citas = citas.filter(tipo_cita=cd['tipo_cita'])
        if cd.get('prioridad'):
            citas = citas.filter(prioridad=cd['prioridad'])
        if cd.get('consultorio') and user.rol == 'admin':
            citas = citas.filter(consultorio=cd['consultorio'])
        if cd.get('medico'):
            citas = citas.filter(medico_asignado=cd['medico'])
        if cd.get('estado_asignacion'):
            if cd['estado_asignacion'] == 'disponibles':
                citas = citas.filter(medico_asignado__isnull=True)
            elif cd['estado_asignacion'] == 'asignadas':
                citas = citas.filter(medico_asignado__isnull=False)
            elif cd['estado_asignacion'] == 'preferidas':
                citas = citas.filter(medico_preferido__isnull=False)
            elif cd['estado_asignacion'] == 'vencidas':
                citas = citas.filter(
                    medico_asignado__isnull=True,
                    fecha_hora__lt=timezone.now()
                )
        
        if cd.get('rango_tiempo'):
            hoy = timezone.now().date()
            if cd['rango_tiempo'] == 'hoy':
                citas = citas.filter(fecha_hora__date=hoy)
            elif cd['rango_tiempo'] == 'manana':
                citas = citas.filter(fecha_hora__date=hoy + timedelta(days=1))
            elif cd['rango_tiempo'] == 'esta_semana':
                inicio_semana = hoy - timedelta(days=hoy.weekday())
                fin_semana = inicio_semana + timedelta(days=6)
                citas = citas.filter(fecha_hora__date__range=[inicio_semana, fin_semana])
            elif cd['rango_tiempo'] == 'proximo_mes':
                inicio_mes = hoy.replace(day=1)
                if inicio_mes.month == 12:
                    fin_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1) - timedelta(days=1)
                else:
                    fin_mes = inicio_mes.replace(month=inicio_mes.month + 1) - timedelta(days=1)
                citas = citas.filter(fecha_hora__date__range=[inicio_mes, fin_mes])
            elif cd['rango_tiempo'] == 'vencidas':
                citas = citas.filter(fecha_hora__lt=timezone.now())
    
    # Ordenar por fecha
    citas = citas.select_related(
        'paciente', 'consultorio', 'medico_asignado', 'medico_preferido'
    ).prefetch_related('consulta').order_by('fecha_hora')
    
    # Estadísticas
    hoy = timezone.now().date()
    stats = {
        'total': citas.count(),
        'hoy': citas.filter(fecha_hora__date=hoy).count(),
        'sin_asignar': citas.filter(medico_asignado__isnull=True).count(),
        'asignadas': citas.filter(medico_asignado__isnull=False).count(),
        'completadas': citas.filter(estado='completada').count(),
        'vencidas': citas.filter(
            fecha_hora__lt=timezone.now(),
            estado__in=['programada', 'confirmada']
        ).count(),
    }
    
    # Agrupaciones para pestañas
    grupos = {
        'sin_asignar': citas.filter(
            medico_asignado__isnull=True,
            estado__in=['programada', 'confirmada', 'en_espera']
        ),
        'asignadas': citas.filter(
            medico_asignado__isnull=False,
            estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
        ),
        'completadas': citas.filter(estado='completada'),
        'canceladas': citas.filter(estado__in=['cancelada', 'no_asistio']),
    }
    
    # Paginación
    paginator = Paginator(citas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Permisos
    permisos = {
        'puede_tomar': user.rol == 'medico',
        'puede_asignar': user.rol in ['admin', 'asistente'],
        'puede_liberar': user.rol in ['admin', 'medico'],
        'puede_crear': True,
    }
    
    # Médicos disponibles para filtros
    if user.rol == 'admin':
        medicos_disponibles = Usuario.objects.filter(rol='medico', is_active=True)
    elif user.consultorio:
        medicos_disponibles = Usuario.objects.filter(
            rol='medico',
            consultorio=user.consultorio,
            is_active=True
        )
    else:
        medicos_disponibles = Usuario.objects.none()
    
    context = {
        'page_obj': page_obj,
        'filtro_form': filtro_form,
        'stats': stats,
        'grupos': grupos,
        'permisos': permisos,
        'medicos_disponibles': medicos_disponibles,
        'usuario': user,
        'hoy': hoy,
    }
    
    return render(request, 'PAGES/citas/lista.html', context)


@login_required
def crear_cita(request):
    """Crear nueva cita con validaciones de horario - CORREGIDA"""
    if request.user.rol not in ['medico', 'asistente', 'admin']:
        messages.error(request, 'No tienes permisos para crear citas.')

        return redirect_next(request, 'citas_lista')

    
    if request.method == 'POST':
        form = CitaForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                cita = form.save(commit=False)
                cita.creado_por = request.user
                
                # Asignar consultorio según el usuario
                if request.user.rol == 'asistente' and request.user.consultorio:
                    cita.consultorio = request.user.consultorio
                elif request.user.rol == 'medico' and request.user.consultorio:
                    cita.consultorio = request.user.consultorio
                
                # Validar conflictos de horario antes de guardar
                conflictos = validar_conflictos_horario(
                    cita.consultorio,
                    cita.fecha_hora,
                    cita.duracion,
                    excluir_cita_id=None
                )
                
                if conflictos:
                    form.add_error(None, f"Conflicto de horario detectado: {conflictos}")
                else:
                    cita.save()
                    messages.success(request, f'Cita {cita.numero_cita} creada exitosamente.')
                    
                    # Crear notificación para médicos del consultorio
                    crear_notificacion_nueva_cita(cita)
                    
                    return redirect_next(request, 'citas_lista')
 
            except Exception as e:
                messages.error(request, f'Error al crear la cita: {str(e)}')
    else:
        form = CitaForm(user=request.user)
    
    context = {
        'form': form,
        'titulo': 'Nueva Cita',
        'accion': 'Crear',
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/crear.html', context)


@login_required
def editar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)

    if not puede_editar_cita(request.user, cita):
        messages.error(request, "No tienes permisos para editar esta cita.")
        return redirect("citas_lista")

    # ───────── helper para construir los initial ──────────
    def _build_initial(cita_obj):
        fh_local = timezone.localtime(cita_obj.fecha_hora)
        return {
            "fecha":    fh_local.date().isoformat(),
            "hora":     fh_local.strftime("%H:%M"),
            "duracion": str(cita_obj.duracion),
        }

    # ───────── POST ─────────
    if request.method == "POST":
        form = CitaForm(
            request.POST,
            instance=cita,
            user=request.user,
            initial=_build_initial(cita),
        )
        if form.is_valid():
            cita_editada = form.save(commit=False)
            cita_editada.actualizado_por = request.user

            conflictos = validar_conflictos_horario(
                cita_editada.consultorio,
                cita_editada.fecha_hora,
                cita_editada.duracion,
                excluir_cita_id=cita.id,
            )
            if conflictos:
                form.add_error(
                    None,
                    f"Conflicto de horario detectado: {conflictos}",
                )
            else:
                cita_editada.save()
                messages.success(
                    request,
                    f"Cita {cita.numero_cita} actualizada correctamente.",
                )
                return redirect("detalle_cita", cita_id=cita.id)

    # ───────── GET (o POST inválido) ─────────
    else:
        form = CitaForm(
            instance=cita,
            user=request.user,
            initial=_build_initial(cita),
        )

    return render(
        request,
        "PAGES/citas/editar.html",
        {
            "form": form,
            "cita": cita,
            "titulo": f"Editar Cita {cita.numero_cita}",
            "accion": "Actualizar",
            "usuario": request.user,
        },
    )

@login_required
def detalle_cita(request, cita_id):
    """Detalle de una cita específica - CORREGIDA"""
    cita = get_object_or_404(Cita, id=cita_id)
    
    # Verificar permisos de visualización
    if not puede_ver_cita(request.user, cita):
        messages.error(request, 'No tienes permisos para ver esta cita.')

        return redirect_next(request, 'citas_lista')

    
    # Obtener médicos disponibles para asignación
    medicos_disponibles = []
    if request.user.rol == 'admin' and cita.consultorio:
        medicos_disponibles = Usuario.objects.filter(
            rol='medico',
            consultorio=cita.consultorio,
            is_active=True,
        ).order_by('first_name', 'last_name')
    
    # Verificar si hay consulta asociada
    consulta = None
    try:
        consulta = cita.consulta
    except Consulta.DoesNotExist:
        pass
    
    context = {
        'cita': cita,
        'consulta': consulta,
        'medicos_disponibles': medicos_disponibles,
        'puede_asignar_medico': (
            cita.puede_asignar_medico and 
            request.user.rol in ['admin', 'asistente']
        ),
        'puede_tomar_cita': puede_tomar_cita(request.user, cita),
        'puede_editar': puede_editar_cita(request.user, cita),
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/detalle.html', context)

@login_required
def asignar_medico_cita(request, cita_id):
    """Asignar médico a una cita - CORREGIDA"""
    cita = get_object_or_404(Cita, id=cita_id)

    # Verificar permisos
    if request.user.rol == 'asistente':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Acción no permitida para asistentes.'}, status=403)
        return HttpResponseForbidden('Acción no permitida para asistentes.')
    if request.user.rol not in ['admin', 'medico']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'No tienes permisos para asignar médicos'}, status=403)
        messages.error(request, 'No tienes permisos para asignar médicos.')
        return redirect_next(request, 'citas_detalle', pk=cita.id)
    
    # Verificar que la cita puede tener médico asignado
    if not cita.puede_asignar_medico:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Esta cita ya tiene médico asignado o no se puede asignar'}, status=400)
        messages.error(request, 'Esta cita ya tiene médico asignado o no se puede asignar.')
        return redirect_next(request, 'citas_detalle', pk=cita.id)
    
    if request.method == 'POST':
        # Determinar si es una solicitud AJAX
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Para solicitudes AJAX desde la lista, el médico viene directamente en el POST
        if is_ajax and 'medico_id' in request.POST:
            try:
                medico_id = request.POST.get('medico_id')
                medico = get_object_or_404(Usuario, id=medico_id, rol='medico')
                observaciones = request.POST.get('observaciones', '')
                
                # Asignar médico
                cita.medico_asignado = medico
                cita.fecha_asignacion_medico = timezone.now()
                cita.estado = 'confirmada'
                cita.actualizado_por = request.user
                
                # Agregar observaciones si las hay
                if observaciones:
                    if cita.notas:
                        cita.notas += f"\n\nObservaciones de asignación: {observaciones}"
                    else:
                        cita.notas = f"Observaciones de asignación: {observaciones}"
                
                cita.save()
                
                # Si hay consulta asociada, también asignar el médico
                if hasattr(cita, 'consulta') and cita.consulta:
                    consulta = cita.consulta
                    consulta.medico = medico
                    consulta.save()
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Médico {medico.get_full_name()} asignado exitosamente.',
                    'medico_nombre': medico.get_full_name(),
                    'cita_id': str(cita.id)
                })
                
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)
        else:
            # Para solicitudes normales desde el formulario
            form = AsignarMedicoForm(request.POST, cita=cita, user=request.user)
            if form.is_valid():
                try:
                    medico = form.cleaned_data['medico']
                    observaciones = form.cleaned_data.get('observaciones', '')
                    
                    # Asignar médico
                    cita.medico_asignado = medico
                    cita.fecha_asignacion_medico = timezone.now()
                    cita.estado = 'confirmada'
                    cita.actualizado_por = request.user
                    
                    # Agregar observaciones si las hay
                    if observaciones:
                        if cita.notas:
                            cita.notas += f"\n\nObservaciones de asignación: {observaciones}"
                        else:
                            cita.notas = f"Observaciones de asignación: {observaciones}"
                    
                    cita.save()
                    
                    # Si hay consulta asociada, también asignar el médico
                    if hasattr(cita, 'consulta') and cita.consulta:
                        consulta = cita.consulta
                        consulta.medico = medico
                        consulta.save()
                    
                    messages.success(
                        request, 
                        f'Médico {medico.get_full_name()} asignado exitosamente a la cita {cita.numero_cita}.'
                    )
                    
                    return redirect_next(request, 'citas_detalle', pk=cita.id)
                    
                except Exception as e:
                    messages.error(request, f'Error al asignar médico: {str(e)}')
                    form.add_error(None, f'Error al asignar médico: {str(e)}')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'Error en {field}: {error}')
    else:
        form = AsignarMedicoForm(cita=cita, user=request.user)
    
    context = {
        'form': form,
        'cita': cita,
        'titulo': f'Asignar Médico - Cita {cita.numero_cita}',
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/asignar_medico.html', context)


@login_required
def tomar_cita(request, cita_id):
    """Permite a un médico tomar una cita disponible - CORREGIDA"""
    if request.user.rol != 'medico':
        messages.error(request, 'Solo los médicos pueden tomar citas.')
        return redirect_next(request, 'citas_lista')

    
    cita = get_object_or_404(Cita, id=cita_id)
    user = request.user
    
    # Verificaciones de seguridad
    if not puede_tomar_cita(user, cita):
        messages.error(request, 'No puedes tomar esta cita.')
        return redirect_next(request, 'citas_disponibles')
    
    # Verificar conflictos de horario del médico
    conflictos = Cita.objects.filter(
        medico_asignado=user,
        fecha_hora__date=cita.fecha_hora.date(),
        fecha_hora__time__range=[
            (cita.fecha_hora - timedelta(minutes=15)).time(),
            (cita.fecha_hora + timedelta(minutes=cita.duracion + 15)).time()
        ],
        estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
    ).exclude(id=cita.id)
    
    if conflictos.exists() and not request.POST.get('confirmar'):
        conflicto = conflictos.first()
        context = {
            'cita': cita,
            'conflicto': conflicto,
            'usuario': user,
        }
        return render(request, 'PAGES/citas/confirmar_tomar.html', context)
    
    if request.method == 'POST':
        try:
            # Asignar médico y cambiar estado
            cita.medico_asignado = user
            cita.fecha_asignacion_medico = timezone.now()
            cita.estado = 'confirmada'
            cita.actualizado_por = user
            cita.save()
            
            # Si hay consulta asociada, asignar médico también
            if hasattr(cita, 'consulta'):
                consulta = cita.consulta
                consulta.medico = user
                consulta.save()
            
            messages.success(
                request, 
                f'Has tomado exitosamente la cita de {cita.paciente.nombre_completo} '
                f'programada para {cita.fecha_hora.strftime("%d/%m/%Y a las %H:%M")}.'
            )
            
            return redirect_next(request, 'mis_citas_asignadas')
            
        except Exception as e:
            messages.error(request, f'Error al tomar la cita: {str(e)}')
            return redirect_next(request, 'citas_disponibles')
    
    # GET request - mostrar confirmación
    context = {
        'cita': cita,
        'usuario': user,
    }
    return render(request, 'PAGES/citas/tomar_cita.html', context)


@login_required
def liberar_cita(request, cita_id):
    """Permite liberar una cita asignada - CORREGIDA"""
    cita = get_object_or_404(Cita, id=cita_id)
    
    # Verificar permisos
    if not (request.user.rol == 'admin' or cita.medico_asignado == request.user):
        messages.error(request, 'No tienes permisos para liberar esta cita.')
        return redirect_next(request, 'citas_detalle', pk=cita.id)
    
    # Verificar que la cita se puede liberar
    if not cita.medico_asignado:
        messages.error(request, 'Esta cita no tiene médico asignado.')
        return redirect_next(request, 'citas_detalle', pk=cita.id)
    
    if cita.estado in ['completada', 'cancelada']:
        messages.error(request, 'No se puede liberar una cita completada o cancelada.')
        return redirect_next(request, 'citas_detalle', pk=cita.id)
    
    if request.method == 'POST':
        try:
            motivo = request.POST.get('motivo', '').strip()
            medico_anterior = cita.medico_asignado
            
            # Liberar la cita
            cita.medico_asignado = None
            cita.fecha_asignacion_medico = None
            cita.estado = 'programada'
            cita.motivo_cancelacion = motivo
            cita.actualizado_por = request.user
            cita.save()
            
            # Si hay consulta asociada, también liberarla
            if hasattr(cita, 'consulta') and cita.consulta:
                consulta = cita.consulta
                if consulta.estado in ['espera', 'en_progreso']:
                    consulta.medico = None
                    consulta.estado = 'espera'
                    consulta.save()
            
            # Crear notificación para otros médicos del consultorio
            crear_notificacion_cita_liberada(cita, medico_anterior)
            
            messages.success(
                request, 
                f'Cita {cita.numero_cita} liberada exitosamente. '
                f'Ahora está disponible para otros médicos del {cita.consultorio.nombre}.'
            )
            
            return redirect_next(request, 'citas_detalle', pk=cita.id)
            
        except Exception as e:
            messages.error(request, f'Error al liberar la cita: {str(e)}')
    
    context = {
        'cita': cita,
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/liberar_cita.html', context)
    
@login_required
def citas_disponibles(request):
    """Vista de citas disponibles para que médicos puedan tomar - CORREGIDA"""
    user = request.user
    
    # Solo médicos pueden acceder, admin puede ver todas
    if user.rol not in ['medico', 'admin']:
        messages.error(request, 'Solo los médicos pueden ver citas disponibles.')
        return redirect_next(request, 'dashboard')
    
    # Filtrar citas según rol
    if user.rol == 'admin':
        citas_base = Cita.objects.all()
    elif user.consultorio:
        citas_base = Cita.objects.filter(consultorio=user.consultorio)
    else:
        messages.error(request, 'No tienes consultorio asignado.')
        return redirect_next(request, 'dashboard')
    
    # Filtrar citas sin médico asignado
    citas_disponibles = citas_base.filter(
        medico_asignado__isnull=True,
        estado__in=['programada', 'confirmada', 'en_espera'],
        fecha_hora__gte=timezone.now() - timedelta(hours=1)
    )
    
    # Aplicar filtros
    fecha_filtro = request.GET.get('fecha')
    tipo_filtro = request.GET.get('tipo_cita')
    prioridad_filtro = request.GET.get('prioridad')
    consultorio_filtro = request.GET.get('consultorio')
    
    if fecha_filtro:
        try:
            fecha = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
            citas_disponibles = citas_disponibles.filter(fecha_hora__date=fecha)
        except ValueError:
            pass
    
    if tipo_filtro:
        citas_disponibles = citas_disponibles.filter(tipo_cita=tipo_filtro)
    
    if prioridad_filtro:
        citas_disponibles = citas_disponibles.filter(prioridad=prioridad_filtro)
    
    if consultorio_filtro and user.rol == 'admin':
        citas_disponibles = citas_disponibles.filter(consultorio_id=consultorio_filtro)
    
    # Ordenar por prioridad y fecha
    citas_disponibles = citas_disponibles.select_related(
        'paciente', 'consultorio', 'medico_preferido'
    ).order_by('fecha_hora', '-prioridad')
    
    # Agrupar por urgencia
    ahora = timezone.now()
    grupos = {
        'urgentes': citas_disponibles.filter(
            Q(prioridad='urgente') | 
            Q(fecha_hora__lte=ahora + timedelta(hours=1))
        ),
        'hoy': citas_disponibles.filter(fecha_hora__date=ahora.date()),
        'proximas': citas_disponibles.filter(fecha_hora__date__gt=ahora.date()),
    }
    
    # Estadísticas
    stats = {
        'total_disponibles': citas_disponibles.count(),
        'urgentes': grupos['urgentes'].count(),
        'hoy': grupos['hoy'].count(),
        'esta_semana': citas_disponibles.filter(
            fecha_hora__date__range=[
                ahora.date(),
                ahora.date() + timedelta(days=7)
            ]
        ).count(),
    }
    
    context = {
        'citas_disponibles': citas_disponibles,
        'grupos': grupos,
        'stats': stats,
        'filtros': {
            'fecha': fecha_filtro,
            'tipo_cita': tipo_filtro,
            'prioridad': prioridad_filtro,
            'consultorio': consultorio_filtro,
        },
        'tipos_cita': Cita.TIPO_CITA_CHOICES,
        'prioridades': Cita.PRIORIDAD_CHOICES,
        'consultorios': Consultorio.objects.all() if user.rol == 'admin' else [user.consultorio],
        'usuario': user,
        'puede_tomar': user.rol == 'medico',
    }
    
    return render(request, 'PAGES/citas/disponibles.html', context)


@login_required
def mis_citas_asignadas(request):
    """Citas asignadas al médico actual - CORREGIDA"""
    if request.user.rol != 'medico':
        messages.error(request, 'Solo los médicos pueden ver sus citas asignadas.')
        return redirect_next(request, 'dashboard')
    
    citas = Cita.objects.filter(
        medico_asignado=request.user
    ).select_related('paciente', 'consultorio').order_by('fecha_hora')
    
    # Aplicar filtros
    estado_filtro = request.GET.get('estado')
    if estado_filtro:
        citas = citas.filter(estado=estado_filtro)
    
    fecha_filtro = request.GET.get('fecha')
    if fecha_filtro:
        try:
            fecha = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
            citas = citas.filter(fecha_hora__date=fecha)
        except ValueError:
            pass
    
    # Estadísticas
    ahora = timezone.now()
    stats = {
        'total': citas.count(),
        'hoy': citas.filter(fecha_hora__date=ahora.date()).count(),
        'pendientes': citas.filter(estado__in=['programada', 'confirmada']).count(),
        'en_atencion': citas.filter(estado='en_atencion').count(),
        'completadas': citas.filter(estado='completada').count(),
        'esta_semana': citas.filter(
            fecha_hora__date__range=[
                ahora.date(),
                ahora.date() + timedelta(days=7)
            ]
        ).count(),
    }
    
    context = {
        'citas': citas,
        'stats': stats,
        'estado_filtro': estado_filtro,
        'fecha_filtro': fecha_filtro,
        'today': ahora.date(),
        'usuario': request.user,
    }
    return render(request, 'PAGES/citas/mis_citas.html', context)


# ───────────────────────────────────────────
# CANCELAR (estado = cancelada) – NO borra
# ───────────────────────────────────────────
@login_required
def cancelar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)

    if request.user.rol == "asistente":
        return HttpResponseForbidden("Acción no permitida para asistentes.")
    if request.user.rol != "admin":
        messages.error(request, "No tienes permisos para cancelar citas.")
        return redirect("citas_detalle", pk=cita.id)

    if cita.estado in ("cancelada", "completada"):
        messages.warning(request, "La cita ya está cancelada o completada.")
        return redirect("citas_detalle", pk=cita.id)

    if request.method == "POST":
        motivo = request.POST.get("motivo_cancelacion", "").strip()
        cita.estado = "cancelada"
        cita.motivo_cancelacion = motivo
        cita.fecha_cancelacion = timezone.now()
        cita.actualizado_por = request.user
        cita.save(
            update_fields=[
                "estado",
                "motivo_cancelacion",
                "fecha_cancelacion",
                "actualizado_por",
                "fecha_actualizacion",
            ]
        )
        if hasattr(cita, "consulta"):
            consulta = cita.consulta
            consulta.estado = "cancelada"
            consulta.save(update_fields=["estado"])
        messages.success(request, f"Cita {cita.numero_cita} cancelada correctamente.")
        return redirect("citas_detalle", pk=cita.id)

    return render(
        request,
        "PAGES/citas/eliminar.html",
        {"cita": cita, "titulo": "Cancelar Cita", "usuario": request.user},
    )


@login_required
def marcar_no_asistio(request, cita_id):
    """Marca una cita como no asistió."""
    cita = get_object_or_404(Cita, id=cita_id)

    if request.user.rol not in ["admin", "medico"]:
        messages.error(request, "No tienes permisos para marcar esta cita.")
        return redirect("citas_detalle", pk=cita.id)

    if request.method == "POST":
        cita.estado = "no_asistio"
        cita.actualizado_por = request.user
        cita.save(update_fields=["estado", "actualizado_por", "fecha_actualizacion"])
        messages.success(
            request,
            f"Cita {cita.numero_cita} marcada como 'No asistió'.",
        )

    return redirect("citas_detalle", pk=cita.id)


# ───────────────────────────────────────────
# ELIMINAR (borrado real) – sólo admin
# ───────────────────────────────────────────
class CitaDeleteView(CitaPermisoMixin, DeleteView):
    model            = Cita
    pk_url_kwarg     = 'cita_id'                  
    template_name    = "PAGES/citas/eliminar.html"
    success_url      = reverse_lazy("citas_lista")

    def test_func(self):
        return super().test_func() and self.request.user.rol == "admin"

    def delete(self, request, *args, **kwargs):
        self.object: Cita = self.get_object()
        consulta = getattr(self.object, "consulta", None)
        numero = self.object.numero_cita

        response = super().delete(request, *args, **kwargs)

        if consulta:
            consulta.delete()

        messages.success(request, f"Cita {numero} eliminada definitivamente.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["usuario"] = self.request.user
        ctx["titulo"]  = "Eliminar Cita"
        return ctx


# ═══════════════════════════════════════════════════════════════
# 📅 VISTAS DE CALENDARIO
# ═══════════════════════════════════════════════════════════════

@login_required
def citas_calendario(request):
    """Vista del calendario de citas - CORREGIDA"""
    user = request.user
    
    # Obtener consultorios disponibles según el rol
    if user.rol == 'admin':
        consultorios = Consultorio.objects.all()
    elif user.consultorio:
        consultorios = Consultorio.objects.filter(id=user.consultorio.id)
    else:
        consultorios = Consultorio.objects.none()
    
    context = {
        'consultorios': consultorios,
        'user_consultorio': user.consultorio.id if user.consultorio else None,
        'usuario': user,
    }
    return render(request, 'PAGES/citas/calendario.html', context)


@login_required
def citas_calendario_data(request):
    """Datos JSON para el calendario de citas - CORREGIDA"""
    user = request.user
    
    try:
        # Filtros
        consultorio_id = request.GET.get('consultorio')
        medico_id = request.GET.get('medico')
        start = request.GET.get('start')
        end = request.GET.get('end')
        
        # Query base según rol
        if user.rol == 'admin':
            citas = Cita.objects.all()
        elif user.rol == 'medico':
            citas = Cita.objects.filter(
                Q(consultorio=user.consultorio) | Q(medico_asignado=user)
            )
        elif user.rol == 'asistente':
            citas = Cita.objects.filter(consultorio=user.consultorio)
        else:
            citas = Cita.objects.none()
        
        # Aplicar filtros
        if consultorio_id:
            citas = citas.filter(consultorio_id=consultorio_id)
        
        if medico_id:
            citas = citas.filter(medico_asignado_id=medico_id)
        
        if start:
            try:
                start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
                citas = citas.filter(fecha_hora__gte=start_date)
            except ValueError:
                pass
        
        if end:
            try:
                end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
                citas = citas.filter(fecha_hora__lte=end_date)
            except ValueError:
                pass
        
        # Preparar datos para FullCalendar
        events = []
        for cita in citas.select_related('paciente', 'consultorio', 'medico_asignado'):
            color = get_color_by_estado(cita.estado)
            
            events.append({
                'id': str(cita.id),
                'title': f"{cita.paciente.nombre_completo}",
                'start': cita.fecha_hora.isoformat(),
                'end': (cita.fecha_hora + timedelta(minutes=cita.duracion)).isoformat(),
                'backgroundColor': color,
                'borderColor': color,
                'extendedProps': {
                    'numero_cita': cita.numero_cita,
                    'paciente': cita.paciente.nombre_completo,
                    'consultorio': cita.consultorio.nombre,
                    'medico': cita.medico_asignado.get_full_name() if cita.medico_asignado else 'Sin asignar',
                    'estado': cita.get_estado_display(),
                    'motivo': cita.motivo or '',
                    'telefono': cita.telefono_contacto or '',
                    'duracion': cita.duracion,
                    'sin_medico': not cita.medico_asignado,
                }
            })
        
        return JsonResponse(events, safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════
# 🔧 VISTAS AJAX
# ═══════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def ajax_horarios_disponibles(request):
    """
    Devuelve:
      {success: True,
       total:   42,
       horarios:[{value, text, estado}, …]}
    """
    try:
        cid      = request.GET.get("consultorio_id")
        fecha    = request.GET.get("fecha")
        duracion = int(request.GET.get("duracion", 30))
        cita_id  = request.GET.get("cita_id")

        if not (cid and fecha):
            return JsonResponse({"error": "Faltan parámetros"}, status=400)

        try:
            consultorio = Consultorio.objects.get(pk=int(cid))
        except (Consultorio.DoesNotExist, ValueError):
            return JsonResponse({"error": "Consultorio no encontrado"}, status=404)

        try:
            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"error": "Formato de fecha inválido"}, status=400)

        horarios = obtener_horarios_disponibles_para_select(
            consultorio, fecha_obj, duracion, cita_id
        )

        return JsonResponse(
            {"success": True, "total": len(horarios), "horarios": horarios}
        )

    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_http_methods(["GET"])
def ajax_consultorio_medico(request, consultorio_id):
    """Vista AJAX para obtener médicos de un consultorio - CORREGIDA"""
    try:
        consultorio = get_object_or_404(Consultorio, id=consultorio_id)
        medicos = Usuario.objects.filter(
            rol='medico',
            consultorio=consultorio,
            is_active=True
        ).order_by('first_name', 'last_name')
        
        medicos_data = [
            {
                'id': medico.id,
                'nombre': medico.get_full_name()
            }
            for medico in medicos
        ]
        
        return JsonResponse({'medicos': medicos_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def ajax_cita_detalle(request, cita_id):
    """Vista AJAX para obtener detalles de una cita - CORREGIDA"""
    try:
        cita = get_object_or_404(Cita, pk=cita_id)
        
        # Verificar permisos
        if not puede_ver_cita(request.user, cita):
            return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
        
        consulta = getattr(cita, 'consulta', None)
        
        data = {
            'success': True,
            'cita': {
                'id': str(cita.id),
                'numero_cita': cita.numero_cita,
                'paciente': {
                    'nombre': cita.paciente.nombre_completo,
                    'edad': cita.paciente.edad,
                    'telefono': cita.paciente.telefono,
                    'correo': cita.paciente.correo,
                },
                'fecha': cita.fecha_hora.strftime('%d/%m/%Y'),
                'hora': cita.fecha_hora.strftime('%H:%M'),
                'medico': cita.medico_asignado.get_full_name() if cita.medico_asignado else 'Sin asignar',
                'consultorio': cita.consultorio.nombre if cita.consultorio else 'Sin asignar',
                'duracion': cita.duracion,
                'motivo': cita.motivo or '',
                'notas': cita.notas or '',
                'estado': cita.estado,
                'estado_display': cita.get_estado_display(),
                'tipo_cita': cita.get_tipo_cita_display(),
                'prioridad': cita.get_prioridad_display(),
                'consulta': {
                    'id': consulta.id,
                    'estado': consulta.estado
                } if consulta else None,
                'puede_editar': puede_editar_cita(request.user, cita)
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def cambiar_estado_cita(request, cita_id):
    """Vista AJAX para cambiar el estado de una cita - CORREGIDA"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    
    try:
        cita = get_object_or_404(Cita, id=cita_id)
        
        # Verificar permisos
        if not puede_editar_cita(request.user, cita):
            return JsonResponse({'success': False, 'message': 'Sin permisos para editar esta cita'}, status=403)
        
        nuevo_estado = request.POST.get('estado')
        motivo = request.POST.get('motivo', '')
        
        if nuevo_estado not in dict(Cita.ESTADO_CHOICES):
            return JsonResponse({'success': False, 'message': 'Estado inválido'}, status=400)
        
        # Cambiar estado
        estado_anterior = cita.estado
        cita.estado = nuevo_estado
        
        if motivo:
            cita.motivo_cancelacion = motivo
        
        if nuevo_estado == 'cancelada':
            cita.fecha_cancelacion = timezone.now()
        elif nuevo_estado == 'confirmada':
            cita.fecha_confirmacion = timezone.now()
        
        cita.actualizado_por = request.user
        cita.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Estado cambiado de {estado_anterior} a {nuevo_estado}',
            'nuevo_estado': cita.get_estado_display()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════
# 📤 EXPORTACIÓN Y REPORTES
# ═══════════════════════════════════════════════════════════════

@login_required
def exportar_citas_csv(request):
    """Exportar citas a CSV - CORREGIDA"""
    try:
        user = request.user
        
        # Filtrar citas según rol
        if user.rol == 'admin':
            citas = Cita.objects.all()
        elif user.rol == 'medico':
            citas = Cita.objects.filter(
                Q(consultorio=user.consultorio) | Q(medico_asignado=user)
            )
        elif user.rol == 'asistente':
            citas = Cita.objects.filter(consultorio=user.consultorio)
        else:
            citas = Cita.objects.none()
        
        # Aplicar filtros de fecha si existen
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')
        
        if fecha_desde:
            try:
                fecha = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                citas = citas.filter(fecha_hora__date__gte=fecha)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                citas = citas.filter(fecha_hora__date__lte=fecha)
            except ValueError:
                pass
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="citas_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Número Cita', 'Paciente', 'Consultorio', 'Médico Asignado', 'Médico Preferido',
            'Fecha y Hora', 'Duración', 'Estado', 'Tipo', 'Prioridad', 'Motivo'
        ])
        
        for cita in citas.select_related('paciente', 'consultorio', 'medico_asignado', 'medico_preferido'):
            writer.writerow([
                cita.numero_cita,
                cita.paciente.nombre_completo,
                cita.consultorio.nombre if cita.consultorio else '',
                cita.medico_asignado.get_full_name() if cita.medico_asignado else 'Sin asignar',
                cita.medico_preferido.get_full_name() if cita.medico_preferido else '',
                cita.fecha_hora.strftime('%d/%m/%Y %H:%M'),
                f"{cita.duracion} min",
                cita.get_estado_display(),
                cita.get_tipo_cita_display(),
                cita.get_prioridad_display(),
                cita.motivo or ''
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al exportar: {str(e)}')

        return redirect_next(request, 'citas_lista')



# ═══════════════════════════════════════════════════════════════
# 🔧 FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def puede_ver_cita(user, cita):
    """Verifica si el usuario puede ver la cita"""
    if user.rol == 'admin':
        return True
    elif user.rol == 'medico':
        return (cita.consultorio == user.consultorio or 
                cita.medico_asignado == user)
    elif user.rol == 'asistente':
        return cita.consultorio == user.consultorio
    return False


def puede_editar_cita(user, cita):
    """Verifica si el usuario puede editar la cita"""
    if user.rol == 'admin':
        return True
    elif user.rol == 'asistente':
        return (cita.consultorio == user.consultorio and 
                cita.estado in ['programada', 'confirmada'])
    elif user.rol == 'medico':
        return (cita.medico_asignado == user and 
                cita.estado in ['programada', 'confirmada'])
    return False


def puede_tomar_cita(user, cita):
    """Verifica si el médico puede tomar la cita"""
    return (user.rol == 'medico' and 
            user.consultorio == cita.consultorio and
            not cita.medico_asignado and
            cita.estado in ['programada', 'confirmada'])


def get_color_by_estado(estado):
    """Retorna color para el calendario según el estado"""
    colors = {
        'programada': '#6c757d',      # Gris
        'confirmada': '#0d6efd',      # Azul
        'en_espera': '#ffc107',       # Amarillo
        'en_atencion': '#fd7e14',     # Naranja
        'completada': '#198754',      # Verde
        'cancelada': '#dc3545',       # Rojo
        'no_asistio': '#6f42c1',      # Púrpura
        'reprogramada': '#20c997',    # Teal
    }
    return colors.get(estado, '#6c757d')


def validar_conflictos_horario(consultorio, fecha_hora, duracion, excluir_cita_id=None):
    """Valida si hay conflictos de horario para una cita"""
    try:
        inicio_cita = fecha_hora
        fin_cita = fecha_hora + timedelta(minutes=duracion)
        
        # Buscar citas que se solapen en el mismo consultorio
        citas_existentes = Cita.objects.filter(
            consultorio=consultorio,
            fecha_hora__date=fecha_hora.date(),
            estado__in=['programada', 'confirmada', 'en_espera', 'en_atencion']
        )
        
        if excluir_cita_id:
            citas_existentes = citas_existentes.exclude(id=excluir_cita_id)
        
        for cita_existente in citas_existentes:
            inicio_existente = cita_existente.fecha_hora
            fin_existente = cita_existente.fecha_hora + timedelta(minutes=cita_existente.duracion)
            
            # Verificar solapamiento
            if (inicio_cita < fin_existente and fin_cita > inicio_existente):
                return f"Se solapa con cita de {cita_existente.paciente.nombre_completo} de {inicio_existente.strftime('%H:%M')} a {fin_existente.strftime('%H:%M')}"
        
        return None
        
    except Exception as e:
        return f"Error al validar conflictos: {str(e)}"


def crear_notificacion_nueva_cita(cita):
    """Crea notificación para médicos del consultorio sobre nueva cita"""
    try:
        medicos = Usuario.objects.filter(
            rol='medico',
            consultorio=cita.consultorio,
            is_active=True
        )
        
        for medico in medicos:
            Notificacion.objects.create(
                destinatario=medico,
                titulo="Nueva cita disponible",
                mensaje=f"Nueva cita disponible: {cita.paciente.nombre_completo} - {cita.fecha_hora.strftime('%d/%m/%Y %H:%M')}",
                tipo="info",
                categoria="cita_creada",
                content_type_id=None,
                object_id=str(cita.id)
            )
    except Exception as e:
        print(f"Error al crear notificación nueva cita: {str(e)}")


def crear_notificacion_cita_asignada(cita, medico):
    """Crea notificación cuando se asigna una cita a un médico"""
    try:
        Notificacion.objects.create(
            destinatario=medico,
            titulo="Cita asignada",
            mensaje=f"Se te ha asignado la cita: {cita.numero_cita} - {cita.paciente.nombre_completo} - {cita.fecha_hora.strftime('%d/%m/%Y %H:%M')}",
            tipo="success",
            categoria="cita_creada",
            content_type_id=None,
            object_id=str(cita.id)
        )
    except Exception as e:
        print(f"Error al crear notificación cita asignada: {str(e)}")


def crear_notificacion_cita_liberada(cita, medico_anterior):
    """Crea notificación cuando se libera una cita"""
    try:
        medicos = Usuario.objects.filter(
            rol='medico',
            consultorio=cita.consultorio,
            is_active=True
        ).exclude(id=medico_anterior.id)
        
        for medico in medicos:
            Notificacion.objects.create(
                destinatario=medico,
                titulo="Cita liberada",
                mensaje=f"Cita liberada disponible: {cita.paciente.nombre_completo} - {cita.fecha_hora.strftime('%d/%m/%Y %H:%M')}",
                tipo="warning",
                categoria="cita_creada",
                content_type_id=None,
                object_id=str(cita.id)
            )
    except Exception as e:
        print(f"Error al crear notificación cita liberada: {str(e)}")


def crear_consulta_desde_cita(cita, medico):
    """Crea automáticamente una consulta cuando un médico toma una cita"""
    try:
        consulta, created = Consulta.objects.get_or_create(
            cita=cita,
            defaults={
                'paciente': cita.paciente,
                'tipo': 'con_cita',
                'medico': medico,
                'motivo_consulta': cita.motivo,
                'estado': 'espera'
            }
        )
        return consulta
    except Exception as e:
        print(f"Error al crear consulta desde cita: {str(e)}")
        return None



@login_required
@require_POST
def crear_consulta_desde_cita_view(request, cita_id):
    """Genera una consulta ligada a la cita sin iniciarla todavía."""
    try:
        cita = get_object_or_404(Cita, pk=cita_id)

        # Bloquear si la cita es en el futuro
        if cita.fecha_hora > timezone.now():
            messages.error(
                request,
                "No puedes atender esta consulta antes de la fecha y hora de la cita."
            )
            return redirect_next(request, 'citas_detalle', pk=cita.id)

        # Verificar permisos
        if not (request.user.rol == 'admin' or cita.medico_asignado == request.user):
            messages.error(request, 'No tienes permisos para iniciar esta consulta.')
            return redirect_next(request, 'citas_detalle', pk=cita.id)
        
        # Verificar que la cita tiene médico asignado
        if not cita.medico_asignado:
            messages.error(request, 'La cita debe tener un médico asignado para iniciar la consulta.')
            return redirect_next(request, 'citas_detalle', pk=cita.id)
        
        # Verificar si ya existe una consulta
        if hasattr(cita, 'consulta') and cita.consulta:
            consulta = cita.consulta
            messages.info(request, 'La consulta ya existe.')
        else:
            # Crear nueva consulta
            consulta = Consulta.objects.create(
                cita=cita,
                paciente=cita.paciente,
                medico=cita.medico_asignado,
                tipo='con_cita',
                motivo_consulta=cita.motivo or 'Consulta programada',
                estado='espera',
                fecha_creacion=timezone.now(),
                fecha_atencion=None,
            )
        
        # Dejar la cita y la consulta pendientes hasta que se inicie la atención
        
        messages.success(
            request,
            f'Consulta creada para {cita.paciente.nombre_completo}. '
            'Podrás iniciarla cuando el paciente sea atendido.'
        )
        
        # Redirigir directamente al detalle de la consulta
        return redirect_next(request, 'consulta_detalle', pk=consulta.pk)
        
    except Exception as e:
        messages.error(request, f'Error al crear la consulta: {str(e)}')
        return redirect_next(request, 'citas_detalle', pk=cita_id)
