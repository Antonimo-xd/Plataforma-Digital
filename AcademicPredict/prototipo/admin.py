from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

def export_as_csv(modeladmin, request, queryset):
    """
    🔧 CORRECCIÓN: Función que faltaba para exportar CSV
    
    🎓 EDUCATIVO: Esta función debe estar definida ANTES de usarla
    en las configuraciones de admin. Python ejecuta de arriba hacia abajo.
    """
    meta = modeladmin.model._meta
    field_names = [field.name for field in meta.fields]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={meta}.csv'
    
    writer = csv.writer(response)
    writer.writerow(field_names)  # Escribir headers
    
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])

    return response

export_as_csv.short_description = "Exportar como CSV"

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    # 🎓 MEJORAS AGREGADAS:
    list_per_page = 25                          # Paginación
    actions = [export_as_csv]                   # Acción personalizada
    
    fieldsets = UserAdmin.fieldsets + (
        ('Información Adicional', {'fields': ('rol', 'telefono')}),
    )

@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'coordinador', 'total_estudiantes')
    search_fields = ('nombre', 'codigo')
    list_filter = ('coordinador',)
    
    # 🎓 MEJORAS AGREGADAS:
    list_per_page = 25
    actions = [export_as_csv]
    
    def total_estudiantes(self, obj):
        """
        Método personalizado para mostrar total de estudiantes
        
        🎓 EDUCATIVO: Los métodos en ModelAdmin permiten mostrar
        información calculada en el listado.
        """
        return obj.estudiante_set.filter(activo=True).count()
    
    total_estudiantes.short_description = 'Estudiantes Activos'

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('id_estudiante', 'nombre', 'carrera', 'ingreso_año', 'activo', 'total_anomalias')
    list_filter = ('carrera', 'ingreso_año', 'activo')
    search_fields = ('nombre', 'id_estudiante')
    list_editable = ('activo',)                 # Edición inline
    
    # 🎓 MEJORAS AGREGADAS:
    list_per_page = 25
    actions = [export_as_csv, 'activar_estudiantes', 'desactivar_estudiantes']
    
    def total_anomalias(self, obj):
        return obj.deteccionanomalia_set.count()
    total_anomalias.short_description = 'Anomalías'
    
    def activar_estudiantes(self, request, queryset):
        """Acción para activar estudiantes en lote"""
        updated = queryset.update(activo=True)
        self.message_user(request, f'{updated} estudiantes activados.')
    activar_estudiantes.short_description = 'Activar estudiantes seleccionados'
    
    def desactivar_estudiantes(self, request, queryset):
        """Acción para desactivar estudiantes en lote"""
        updated = queryset.update(activo=False)
        self.message_user(request, f'{updated} estudiantes desactivados.')
    desactivar_estudiantes.short_description = 'Desactivar estudiantes seleccionados'

@admin.register(CriterioAnomalia)
class CriterioAnomaliaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'carrera', 'semestre', 'contamination_rate', 'activo', 'fecha_creacion', 'total_ejecuciones')
    list_filter = ('carrera', 'semestre', 'activo', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')
    
    # 🎓 MEJORAS AGREGADAS:
    list_per_page = 25
    actions = [export_as_csv, 'activar_criterios', 'desactivar_criterios']
    
    def total_ejecuciones(self, obj):
        return obj.ejecucionanalisis_set.count()
    total_ejecuciones.short_description = 'Ejecuciones'
    
    def activar_criterios(self, request, queryset):
        updated = queryset.update(activo=True)
        self.message_user(request, f'{updated} criterios activados.')
    activar_criterios.short_description = 'Activar criterios'
    
    def desactivar_criterios(self, request, queryset):
        updated = queryset.update(activo=False)
        self.message_user(request, f'{updated} criterios desactivados.')
    desactivar_criterios.short_description = 'Desactivar criterios'

@admin.register(DeteccionAnomalia)
class DeteccionAnomaliaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo_anomalia', 'score_anomalia', 'prioridad', 'estado', 'fecha_deteccion')
    list_filter = ('tipo_anomalia', 'estado', 'prioridad', 'fecha_deteccion', 'criterio_usado')
    search_fields = ('estudiante__nombre', 'estudiante__id_estudiante')
    readonly_fields = ('score_anomalia', 'confianza', 'fecha_deteccion')
    
    # 🎓 MEJORAS AGREGADAS:
    list_per_page = 25
    actions = [export_as_csv, 'marcar_como_resuelto', 'marcar_como_revision']
    
    def marcar_como_resuelto(self, request, queryset):
        """Acción para resolver anomalías en lote"""
        updated = queryset.update(estado='resuelto')
        self.message_user(request, f'{updated} anomalías marcadas como resueltas.')
    marcar_como_resuelto.short_description = 'Marcar como resuelto'
    
    def marcar_como_revision(self, request, queryset):
        """Acción para poner en revisión anomalías en lote"""
        updated = queryset.update(estado='en_revision')
        self.message_user(request, f'{updated} anomalías puestas en revisión.')
    marcar_como_revision.short_description = 'Poner en revisión'

@admin.register(Derivacion)
class DerivacionAdmin(admin.ModelAdmin):
    list_display = ('deteccion_anomalia', 'instancia_apoyo', 'estado', 'fecha_derivacion', 'derivado_por', 'prioridad')
    list_filter = ('estado', 'instancia_apoyo', 'fecha_derivacion', 'prioridad')
    search_fields = ('deteccion_anomalia__estudiante__nombre',)
    
    # 🎓 MEJORAS AGREGADAS:
    list_per_page = 25
    actions = [export_as_csv, 'marcar_completadas']
    
    def marcar_completadas(self, request, queryset):
        updated = queryset.update(estado='completada')
        self.message_user(request, f'{updated} derivaciones marcadas como completadas.')
    marcar_completadas.short_description = 'Marcar como completadas'

# Primero, definimos un "Inline" para la tabla intermedia
class DestinatariosInline(admin.TabularInline):
    # 'AlertaAutomatica.destinatarios.through' le dice a Django que
    # edite la tabla que conecta Alertas con Usuarios
    model = AlertaAutomatica.destinatarios.through
    verbose_name = "Destinatario"
    verbose_name_plural = "Destinatarios Asignados"
    extra = 1 # Muestra 1 campo vacío para añadir
    raw_id_fields = ('usuario',) # Mejor para listas largas de usuarios

@admin.register(AlertaAutomatica)
class AlertaAutomaticaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'titulo', 'fecha_creacion', 'leida', 'activa')
    list_filter = ('tipo', 'leida', 'activa', 'fecha_creacion')
    search_fields = ('titulo', 'mensaje')
    
    # 🎓 MEJORAS AGREGADAS:
    list_per_page = 25
    actions = [export_as_csv, 'marcar_como_leidas']
    inlines = [DestinatariosInline]
    exclude = ('destinatarios',)
    
    def marcar_como_leidas(self, request, queryset):
        updated = queryset.update(leida=True)
        self.message_user(request, f'{updated} alertas marcadas como leídas.')
    marcar_como_leidas.short_description = 'Marcar como leídas'

@admin.register(RegistroAcademico)
class RegistroAcademicoAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'asignatura', 'promedio_notas', 'porcentaje_asistencia', 'fecha_registro')
    list_filter = ('asignatura__carrera', 'asignatura__semestre', 'fecha_registro')
    search_fields = ('estudiante__nombre', 'estudiante__id_estudiante', 'asignatura__nombre')
    # 'raw_id_fields' es crucial si tienes miles de registros,
    # reemplaza los menús desplegables por un campo de búsqueda.
    raw_id_fields = ('estudiante', 'asignatura')

@admin.register(Asignatura)
class AsignaturaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'id_asignatura', 'carrera', 'semestre')
    list_filter = ('carrera', 'semestre')
    search_fields = ('nombre', 'id_asignatura')
    raw_id_fields = ('carrera',)

@admin.register(InstanciaApoyo)
class InstanciaApoyoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'email', 'telefono', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre', 'email')

@admin.register(EjecucionAnalisis)
class EjecucionAnalisisAdmin(admin.ModelAdmin):
    list_display = ('criterio_usado', 'fecha_ejecucion', 'anomalias_detectadas', 'ejecutado_por', 'exitoso')
    list_filter = ('exitoso', 'fecha_ejecucion', 'criterio_usado__nombre')
    raw_id_fields = ('ejecutado_por', 'criterio_usado')

@admin.register(AsignaturaCritica)
class AsignaturaCriticaAdmin(admin.ModelAdmin):
    list_display = ('asignatura', 'semestre_analizado', 'porcentaje_anomalias', 'total_estudiantes', 'estudiantes_anomalos')
    list_filter = ('semestre_analizado', 'asignatura__carrera__nombre')
    search_fields = ('asignatura__nombre',)
    raw_id_fields = ('asignatura',)