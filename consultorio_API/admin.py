from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Usuario,
    Paciente,
    Consulta,
    SignosVitales,
    Expediente,
    Antecedente,
    MedicamentoActual,
    Receta,
    MedicamentoRecetado,
    Cita,
    Consultorio,
    Auditoria,
    HorarioMedico,
    Notificacion,
)


# ───────────────────────────────────────────────
# 1️⃣  USUARIOS
# ───────────────────────────────────────────────
class UsuarioAdmin(BaseUserAdmin):
    """Configuración del admin para el modelo de usuario personalizado."""

    model = Usuario

    fieldsets = (
        *BaseUserAdmin.fieldsets,
        (
            "Información adicional",
            {
                "fields": (
                    "rol",
                    "telefono",
                    "cedula_profesional",
                    "institucion_cedula",
                    "consultorio",
                    "foto",
                )
            },
        ),
    )

    list_display = (
        "username",
        "first_name",
        "last_name",
        "rol",
        "consultorio",
        "is_active",
    )
    list_filter = (
        "rol",
        "consultorio",
        "is_active",
        "date_joined",
    )
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "telefono",
        "cedula_profesional",
    )
    ordering = ("username",)


admin.site.register(Usuario, UsuarioAdmin)


# ───────────────────────────────────────────────
# 2️⃣  PACIENTES
# ───────────────────────────────────────────────
class PacienteAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_completo",
        "sexo",
        "edad",
        "telefono",
        "correo",
        "consultorio_nombre",
    )
    list_filter = ("sexo", "consultorio_asignado")
    search_fields = (
        "nombre_completo",
        "telefono",
        "correo",
        "consultorio_asignado__consultorio__nombre",
    )

    def consultorio_nombre(self, obj):
        if obj.consultorio_asignado and obj.consultorio_asignado.consultorio:
            return obj.consultorio_asignado.consultorio.nombre
        return "Sin asignar"
    consultorio_nombre.short_description = "Consultorio"


admin.site.register(Paciente, PacienteAdmin)


# ───────────────────────────────────────────────
# 3️⃣  CONSULTAS & SIGNOS
# ───────────────────────────────────────────────
class SignosVitalesInline(admin.StackedInline):
    model = SignosVitales
    can_delete = False
    readonly_fields = ("fecha_registro", "imc")
    extra = 0


class ConsultaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "paciente",
        "medico",
        "tipo",
        "estado",
        "fecha_creacion",
    )
    list_filter = ("estado", "tipo", "fecha_creacion", "medico")
    search_fields = (
        "paciente__nombre_completo",
        "medico__first_name",
        "medico__last_name",
        "motivo_consulta",
    )
    inlines = [SignosVitalesInline]


admin.site.register(Consulta, ConsultaAdmin)


# ───────────────────────────────────────────────
# 4️⃣  EXPEDIENTES & RELACIONADOS
# ───────────────────────────────────────────────
class AntecedenteInline(admin.TabularInline):
    model = Antecedente
    extra = 0


class MedicamentoActualInline(admin.TabularInline):
    model = MedicamentoActual
    extra = 0


class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ("id", "paciente", "creado", "modificado")
    inlines = [AntecedenteInline, MedicamentoActualInline]
    readonly_fields = ("creado", "modificado")


admin.site.register(Expediente, ExpedienteAdmin)
admin.site.register(Antecedente)
admin.site.register(MedicamentoActual)


# ───────────────────────────────────────────────
# 5️⃣  RECETAS
# ───────────────────────────────────────────────
class MedicamentoRecetadoInline(admin.TabularInline):
    model = MedicamentoRecetado
    extra = 0


class RecetaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "consulta",
        "medico",
        "fecha_emision",
        "valido_hasta",
    )
    list_filter = ("fecha_emision", "valido_hasta", "medico")
    inlines = [MedicamentoRecetadoInline]


admin.site.register(Receta, RecetaAdmin)


# ───────────────────────────────────────────────
# 6️⃣  CITAS
# ───────────────────────────────────────────────
class CitaAdmin(admin.ModelAdmin):
    list_display = (
        "numero_cita",
        "paciente",
        "consultorio",
        "fecha_hora",
        "estado",
        "medico_asignado",
        "prioridad",
    )
    list_filter = (
        "estado",
        "prioridad",
        "tipo_cita",
        "consultorio",
        "medico_asignado",
        "fecha_hora",
    )
    search_fields = (
        "numero_cita",
        "paciente__nombre_completo",
        "motivo",
    )
    date_hierarchy = "fecha_hora"


admin.site.register(Cita, CitaAdmin)


# ───────────────────────────────────────────────
# 7️⃣  CONSULTORIOS & HORARIOS
# ───────────────────────────────────────────────
@admin.register(Consultorio)
class ConsultorioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ubicacion", "capacidad_diaria", "horario_apertura", "horario_cierre")
    search_fields = ("nombre", "ubicacion")


@admin.register(HorarioMedico)
class HorarioMedicoAdmin(admin.ModelAdmin):
    list_display = ("medico", "consultorio", "dia", "hora_inicio", "hora_fin")
    list_filter = ("dia", "consultorio", "medico")
    search_fields = ("medico__first_name", "medico__last_name", "consultorio__nombre")


# ───────────────────────────────────────────────
# 8️⃣  AUDITORÍA & NOTIFICACIONES
# ───────────────────────────────────────────────
@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "accion", "fecha", "object_id")
    list_filter = ("accion", "fecha", "usuario")
    search_fields = ("descripcion",)
    date_hierarchy = "fecha"