from django.urls import path
from .views import *
from django.contrib.auth.views import LogoutView
from .views import CitaCreateView, Receta
from consultorio_API import views, viewscitas, views_consultas

urlpatterns = [
      # LOGIN Y LOGOUT
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # DASHBOARDS
    path('medico/dashboard/', views.DashboardMedico.as_view(), name='dashboard_medico'),
    path('asistente/dashboard/', views.DashboardAsistente.as_view(), name='dashboard_asistente'),
    path('adm/dashboard/', views.DashboardAdmin.as_view(), name='dashboard_admin'),
    
    # USUARIOS (ADMIN)
    path('usuarios/', views.UsuarioListView.as_view(), name='usuarios_lista'),
    path('usuarios/crear/', views.UsuarioCreateView.as_view(), name='usuarios_crear'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuarios_editar'),
    path('usuarios/<int:pk>/eliminar/', views.UsuarioDeleteView.as_view(), name='usuarios_eliminar'),
    
    # PACIENTES
    path('pacientes/', views.PacienteListView.as_view(), name='pacientes_lista'),
    path('pacientes/crear/', views.PacienteCreateView.as_view(), name='pacientes_crear'),
    path('pacientes/<int:pk>/', views.PacienteDetailView.as_view(), name='paciente_detalle'),
    path('pacientes/<int:pk>/editar/', views.PacienteUpdateView.as_view(), name='pacientes_editar'),
    path('pacientes/<int:pk>/eliminar/', views.PacienteDeleteView.as_view(), name='pacientes_eliminar'),
    path('pacientes/<int:pk>/pdf/', views.PacientePDFView.as_view(), name='paciente_pdf'),
    
    
    # CITAS - AGREGAR ESTAS NUEVAS LÍNEAS:
    path('citas/<uuid:cita_id>/asignar-medico/', viewscitas.asignar_medico_cita, name='asignar_medico_cita'),
    path('citas/<uuid:cita_id>/tomar/', viewscitas.tomar_cita, name='tomar_cita'),
    path('citas/<uuid:cita_id>/liberar/', viewscitas.liberar_cita, name='liberar_cita'),
    path('citas/mis-citas/', viewscitas.mis_citas_asignadas, name='mis_citas_asignadas'),
    path('citas/calendario/', viewscitas.citas_calendario, name='citas_calendario'),
    
    # CONSULTAS
    path('consultas/', views.ConsultaListView.as_view(), name='consultas_lista'),
    path('consultas/<int:pk>/', views.ConsultaDetailView.as_view(), name='consulta_detalle'),
    path('consultas/<int:pk>/editar/', views.ConsultaUpdateView.as_view(), name='consulta_editar'),
    path('consultas/<int:pk>/eliminar/', views_consultas.eliminar_consulta, name='consulta_eliminar'),
    path('consultas/crear-sin-cita/', views.ConsultaSinCitaCreateView.as_view(), name='consultas_crear_sin_cita'),
    path('consultas/<int:pk>/precheck/', views.ConsultaPrecheckView.as_view(), name='consultas_precheck'),
    path('consultas/<int:pk>/atencion/', views.ConsultaAtencionView.as_view(), name='consultas_atencion'),
    path('consultas/<int:pk>/cancelar/', views_consultas.cancelar_consulta, name='consulta_cancelar'),
    
    # HORARIOS
    path('horarios/', views.HorarioListView.as_view(), name='horarios_lista'),
    path('horarios/crear/', views.HorarioMedicoCreateView.as_view(), name='horarios_crear'),
    path('horarios/<int:pk>/editar/', views.HorarioUpdateView.as_view(), name='horarios_editar'),
    path('horarios/<int:pk>/eliminar/', views.HorarioDeleteView.as_view(), name='horarios_eliminar'),
    
    # AJAX
    
    path('ajax/consultorio-medico/<int:medico_id>/', views.ajax_consultorio_del_medico, name='ajax_consultorio_medico'),
    path('ajax/consultas-stats/', views.consultas_stats_ajax, name='ajax_consultas_stats'),
    path('ajax/dashboard-stats/', views.dashboard_stats, name='ajax_dashboard_stats'),
    path('ajax/signos-vitales/<int:consulta_id>/', views.ajax_signos_vitales, name='ajax_signos_vitales'),
    path('ajax/cita-detalle/<uuid:cita_id>/', viewscitas.ajax_cita_detalle, name='ajax_cita_detalle'),

    
    # ANTECEDENTES Y MEDICAMENTOS
    path('pacientes/<int:paciente_id>/antecedente/nuevo/', views.antecedente_nuevo, name='antecedente_nuevo'),
    path('pacientes/<int:paciente_id>/medicamento/nuevo/', views.medicamento_nuevo, name='medicamento_nuevo'),
    path('consultas/<int:consulta_id>/receta/nueva/', views.receta_nueva, name='receta_nueva'),
    
    # SIGNOS VITALES
    path('signos/<int:pk>/', views.SignosDetailView.as_view(), name='signos_detalle'),
    
    # AUDITORÍA Y NOTIFICACIONES
    path('auditoria/', views.AuditoriaListView.as_view(), name='auditoria_lista'),
    path('auditoria/<int:auditoria_id>/detalle/', views.auditoria_detalle_ajax, name='auditoria_detalle_ajax'),
    path('auditoria/exportar/', views.auditoria_exportar_csv, name='auditoria_exportar_csv'),
    path('notificaciones/', views.NotificacionListView.as_view(), name='notificaciones_lista'),
    path('notificaciones/<int:notificacion_id>/marcar-leida/', views.marcar_notificacion_leida, name='marcar_notificacion_leida'),
    path('notificaciones/<int:notificacion_id>/eliminar/', views.eliminar_notificacion, name='eliminar_notificacion'),
   path('notificaciones/marcar-todas-leidas/', views.marcar_todas_notificaciones_leidas, name='marcar_todas_notificaciones_leidas'),
    path('notificaciones/count/', views.notificaciones_count_ajax, name='notificaciones_count'),
    
    # PDF
    path('recetas/<int:receta_id>/pdf/', views.receta_pdf_view, name='receta_pdf'),
    path('citas/exportar-csv/', viewscitas.exportar_citas_csv, name='exportar_citas_csv'),  # CAMBIAR
    
    
    
    
    path("citas/", CitaListView.as_view(), name="citas_lista"), 
    path('ajax/horarios/', obtener_horarios_disponibles, name='ajax_horarios_disponibles'), 
    path("citas/crear/", CitaCreateView.as_view(), name="citas_crear"), 
  
   
   
    path('pacientes/<int:paciente_id>/signos/nuevo/', signos_nuevo, name='signos_nuevo'),
    
    
    
    path("citas/<uuid:pk>/", CitaDetailView.as_view(), name="citas_detalle"),
    path("citas/<uuid:pk>/editar/", CitaUpdateView.as_view(), name="citas_editar"),
     # Borrar (DeleteView)
    path('citas/<uuid:cita_id>/eliminar/', viewscitas.CitaDeleteView.as_view(), name='citas_eliminar'),
    # Cancelar (cambia estado)
    path('citas/<uuid:cita_id>/cancelar/', viewscitas.cancelar_cita,         name='cancelar_cita'),
    path("citas/<uuid:pk>/cambiar-estado/", cambiar_estado_cita, name="cambiar_estado_cita"),
    
    
        # Perfil de usuario
    path('perfil/', views.ver_perfil, name='ver_perfil'),
    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),
    
    path("citas/<uuid:pk>/eliminar/",  viewscitas.CitaDeleteView.as_view(),  name="eliminar_cita"),
    
    
          path('ajax/horarios-disponibles/',
         viewscitas.ajax_horarios_disponibles,
         name='ajax_horarios_disponibles'),
    
        path("citas/<uuid:cita_id>/crear-consulta/", viewscitas.crear_consulta_desde_cita_view, name="citas_crear_desde_cita"),

    # COLA VIRTUAL - NUEVAS RUTAS
    path('cola-virtual/', views.cola_virtual, name='cola_virtual'),
    path('cola-virtual/data/', views.cola_virtual_data, name='cola_virtual_data'),

    path('signos/<int:pk>/editar/', views.signos_editar, name='signos_editar'), # Added
    path('signos/<int:pk>/eliminar/', views.signos_eliminar, name='signos_eliminar'), # Added

]
