from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Información Adicional', {'fields': ('rol', 'telefono')}),
    )

@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'coordinador')
    search_fields = ('nombre', 'codigo')
    list_filter = ('coordinador',)

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('id_estudiante', 'nombre', 'carrera', 'ingreso_año', 'activo')
    list_filter = ('carrera', 'ingreso_año', 'activo')
    search_fields = ('nombre', 'id_estudiante')
    list_editable = ('activo',)

@admin.register(Asignatura)
class AsignaturaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'semestre', 'carrera')
    list_filter = ('semestre', 'carrera')
    search_fields = ('nombre',)

@admin.register(RegistroAcademico)
class RegistroAcademicoAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'asignatura', 'promedio_notas', 'porcentaje_asistencia', 'fecha_registro')
    list_filter = ('asignatura__semestre', 'estudiante__carrera', 'fecha_registro')
    search_fields = ('estudiante__nombre', 'asignatura__nombre')
    readonly_fields = ('promedio_notas',)

@admin.register(DeteccionAnomalia)
class DeteccionAnomaliaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo_anomalia', 'score_anomalia', 'prioridad', 'estado', 'fecha_deteccion')
    list_filter = ('tipo_anomalia', 'estado', 'prioridad', 'fecha_deteccion')
    search_fields = ('estudiante__nombre', 'estudiante__id_estudiante')
    readonly_fields = ('score_anomalia', 'confianza', 'fecha_deteccion')

@admin.register(CriterioAnomalia)
class CriterioAnomaliaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'carrera', 'semestre', 'contamination_rate', 'activo', 'fecha_creacion')
    list_filter = ('carrera', 'semestre', 'activo', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')

@admin.register(InstanciaApoyo)
class InstanciaApoyoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'email', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre', 'email')

@admin.register(Derivacion)
class DerivacionAdmin(admin.ModelAdmin):
    list_display = ('deteccion_anomalia', 'instancia_apoyo', 'estado', 'fecha_derivacion', 'derivado_por')
    list_filter = ('estado', 'instancia_apoyo', 'fecha_derivacion')
    search_fields = ('deteccion_anomalia__estudiante__nombre',)

@admin.register(AlertaAutomatica)
class AlertaAutomaticaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'titulo', 'fecha_creacion', 'leida', 'activa')
    list_filter = ('tipo', 'leida', 'activa', 'fecha_creacion')
    search_fields = ('titulo', 'mensaje')