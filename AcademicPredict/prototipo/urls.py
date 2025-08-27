# urls.py (app urls)
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),
    
    # Historia de Usuario 1: Listado de estudiantes con comportamiento anómalo
    path('anomalias/', views.ListadoAnomaliasView.as_view(), name='listado_anomalias'),
    path('anomalias/<int:pk>/', views.detalle_anomalia, name='detalle_anomalia'),
    path('anomalias/<int:anomalia_id>/actualizar-estado/', views.actualizar_estado_anomalia, name='actualizar_estado_anomalia'),
    path('anomalias/gestion-masiva/', views.gestion_masiva_anomalias, name='gestion_masiva_anomalias'),
    path('anomalias/exportar-todas/', views.exportar_todas_anomalias, name='exportar_todas_anomalias'),
    
    # Historia de Usuario 2: Configuración de criterios (Coordinador CPA)
    path('criterios/', views.ConfiguracionCriteriosView.as_view(), name='configuracion_criterios'),
    path('criterios/crear/', views.crear_criterio, name='crear_criterio'),
    path('criterios/<int:criterio_id>/ejecutar/', views.ejecutar_analisis, name='ejecutar_analisis'),
    path('criterios/<int:criterio_id>/', views.detalle_criterio, name='detalle_criterio'),
    path('criterios/<int:criterio_id>/editar/', views.editar_criterio, name='editar_criterio'),
    path('criterios/<int:criterio_id>/eliminar/', views.eliminar_criterio, name='eliminar_criterio'),
    
    # Historia de Usuario 3: Derivaciones (Analista CPA)
    path('derivaciones/', views.gestionar_derivaciones, name='gestionar_derivaciones'),
    path('derivaciones/crear/<int:anomalia_id>/', views.crear_derivacion, name='crear_derivacion'),
    path('derivaciones/<int:derivacion_id>/detalle/', views.detalle_derivacion_ajax, name='detalle_derivacion_ajax'),
    path('derivaciones/<int:derivacion_id>/actualizar-estado/', views.actualizar_estado_derivacion, name='actualizar_estado_derivacion'),  # ← NUEVA

    # Historia de Usuario 4: Alertas automáticas
    path('alertas/', views.alertas_usuario, name='alertas_usuario'),
    
    # Historia de Usuario 5: Asignaturas críticas (Coordinador de Carrera)
    path('asignaturas-criticas/', views.asignaturas_criticas, name='asignaturas_criticas'),
    
    # Perfil de usuario
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),  # ← NUEVA
    
    # Importación de datos desde la web
    path('importar-datos/', views.importar_datos_web, name='importar_datos_web'),

    # Verificación del sistema
    path('verificar-sistema/', views.verificar_sistema, name='verificar_sistema'),

    # APIs para datos dinámicos
    path('api/datos-dashboard/', views.api_datos_dashboard, name='api_datos_dashboard'),
    path('api/estudiante/<int:estudiante_id>/detalle/', views.api_estudiante_detalle, name='api_estudiante_detalle'),
    
    # APIs de exportación NUEVAS
    path('api/exportar-datos-avanzado/', views.api_exportar_datos_avanzado, name='api_exportar_datos_avanzado'),  # ← NUEVA
    path('api/validacion-tiempo-real/', views.api_validacion_tiempo_real, name='api_validacion_tiempo_real'),

    # APIs específicas para gráficos (opcionales, para uso futuro)
    path('api/evolucion-anomalias/', views.api_evolucion_anomalias, name='api_evolucion_anomalias'),
    path('api/tipos-anomalias/', views.api_tipos_anomalias, name='api_tipos_anomalias'),
    
    # Reportes y exportación CORREGIDOS
    path('reportes/anomalias/', views.exportar_reporte_anomalias, name='exportar_reporte_anomalias'),
    path('reportes/derivaciones/', views.exportar_reporte_derivaciones, name='exportar_reporte_derivaciones'),  # ← NUEVA

    # APIs para verificación del sistema - AGREGAR ESTAS LÍNEAS
    path('api/distribucion-carrera/', views.api_distribucion_carrera, name='api_distribucion_carrera'),
    path('api/registros-semestre/', views.api_registros_semestre, name='api_registros_semestre'),
    path('api/probar-analisis/', views.api_probar_analisis, name='api_probar_analisis'),
    
    # APIs existentes mejoradas - VERIFICAR QUE EXISTAN
    path('api/datos-tiempo-real/', views.api_datos_tiempo_real, name='api_datos_tiempo_real'),
    path('api/alertas/count/', views.api_alertas_count, name='api_alertas_count'),
    path('api/progreso-analisis/<int:ejecucion_id>/', views.api_progreso_analisis, name='api_progreso_analisis'),

    # AGREGAR ESTA LÍNEA NUEVA:
    path('api/estadisticas-distribucion/', views.api_estadisticas_distribucion, name='api_estadisticas_distribucion'),

    path('ayuda/', views.ayuda_documentacion, name='ayuda_documentacion'),
]
