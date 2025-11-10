from django.urls import path
from django.conf import settings

# ================================================================
# IMPORTS ORGANIZADOS POR MÓDULO (SIN FUNCIONES ELIMINADAS)
# ================================================================

# 🏠 VIEWS PRINCIPALES (Funciones críticas)
from . import views

# 🔧 VISTAS SECUNDARIAS (Solo las optimizadas)
from .vistas.secondary_views import (asignaturas_criticas, alertas_usuario, verificar_sistema,)

# 📊 APIs DEL DASHBOARD (Mantener todas)
from .api.dashboard_api import ( api_datos_dashboard, api_evolucion_anomalias, api_tipos_anomalias, api_datos_tiempo_real, api_alertas_count, api_distribucion_carrera, api_registros_semestre, api_estadisticas_distribucion, api_estudiante_detalle, api_exportar_datos_avanzado)

# 📋 SERVICIOS DE REPORTES (Con nuevas funciones optimizadas)
from .services.reports_service import ( exportar_reporte_derivaciones, exportar_todas_anomalias)

# ================================================================
# CONFIGURACIÓN DE URLs OPTIMIZADA
# ================================================================

urlpatterns = [
    
    # ================================================================
    # 🏠 RUTAS PRINCIPALES (Críticas del sistema)
    # ================================================================
    
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),
    
    # ================================================================
    # 📋 GESTIÓN DE ANOMALÍAS (Core functionality)  
    # ================================================================
    
    path('anomalias/', views.ListadoAnomaliasView.as_view(), name='listado_anomalias'),
    path('anomalias/<int:pk>/', views.detalle_anomalia, name='detalle_anomalia'),
    path('anomalias/<int:anomalia_id>/actualizar-estado/', views.actualizar_estado_anomalia, name='actualizar_estado_anomalia'),

    # ================================================================
    # 🔧 IMPORTAR DATOS
    # ================================================================
    
    path('importar/', views.importar_datos, name='importar_datos_web'),
    
    # ================================================================
    # 🔧 CONFIGURACIÓN Y CRITERIOS
    # ================================================================
    
    path('criterios/', views.configuracion_criterios, name='configuracion_criterios'),
    path('criterios/crear/', views.crear_criterio_anomalia, name='crear_criterio'),
    path('criterios/<int:criterio_id>/', views.detalle_criterio, name='detalle_criterio'),
    path('criterios/<int:criterio_id>/editar/', views.editar_criterio, name='editar_criterio'),
    path('criterios/<int:criterio_id>/ejecutar/', views.ejecutar_analisis, name='ejecutar_analisis'),
    path('criterios/<int:criterio_id>/eliminar/', views.eliminar_criterio, name='eliminar_criterio'),
    
    # ================================================================
    # 🤝 GESTIÓN DE DERIVACIONES
    # ================================================================
    
    path('derivaciones/', views.gestionar_derivaciones, name='gestionar_derivaciones'),
    path('anomalias/<int:anomalia_id>/derivar/', views.crear_derivacion, name='crear_derivacion'),
    
    # ================================================================
    # 🎯 VISTAS SECUNDARIAS (Solo las optimizadas)
    # ================================================================
    
    path('alertas/', alertas_usuario, name='alertas_usuario'),
    path('asignaturas-criticas/', asignaturas_criticas, name='asignaturas_criticas'), 
    path('verificar-sistema/', verificar_sistema, name='verificar_sistema'),

    # ================================================================
    # 📊 REPORTES Y EXPORTACIONES (Optimizadas)
    # ================================================================
    
    # Reportes principales (MEJORADOS - ahora usan services)
    path('reportes/anomalias/', views.exportar_reporte_anomalias, name='exportar_reporte_anomalias'),
    path('reportes/derivaciones/', exportar_reporte_derivaciones, name='exportar_reporte_derivaciones'),
    path('anomalias/exportar-todas/', exportar_todas_anomalias, name='exportar_todas_anomalias'),
    
    # ================================================================
    # 📡 APIs DEL DASHBOARD (Datos dinámicos para frontend)
    # ================================================================
    
    # APIs principales del dashboard
    path('api/datos-dashboard/', api_datos_dashboard, name='api_datos_dashboard'),
    path('api/datos-tiempo-real/', api_datos_tiempo_real, name='api_datos_tiempo_real'),
    path('api/alertas/count/', api_alertas_count, name='api_alertas_count'),
    
    # APIs específicas para gráficos
    path('api/evolucion-anomalias/', api_evolucion_anomalias, name='api_evolucion_anomalias'),
    path('api/tipos-anomalias/', api_tipos_anomalias, name='api_tipos_anomalias'),
    
    # APIs para análisis y estadísticas
    path('api/distribucion-carrera/', api_distribucion_carrera, name='api_distribucion_carrera'),
    path('api/registros-semestre/', api_registros_semestre, name='api_registros_semestre'),
    path('api/estadisticas-distribucion/', api_estadisticas_distribucion, name='api_estadisticas_distribucion'),
    
    # APIs para detalles específicos
    path('api/estudiante/<int:estudiante_id>/detalle/', api_estudiante_detalle, name='api_estudiante_detalle'),
    
    # APIs de exportación avanzada
    path('api/exportar-datos-avanzado/', api_exportar_datos_avanzado, name='api_exportar_datos_avanzado'),
    
]