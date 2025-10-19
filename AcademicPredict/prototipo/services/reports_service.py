from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import datetime
import pandas as pd
from io import BytesIO

# Imports de modelos
from ..models import (
    DeteccionAnomalia, Derivacion, Carrera)

class ReportsService:
    """
    Servicio optimizado para generación de reportes y exportaciones
    
    🎓 EDUCATIVO: Esta clase aplica el patrón Service Layer,
    centralizando toda la lógica de reportes para reutilización
    y mejor testing.
    """
    
    @staticmethod
    def exportar_anomalias_completo(request, formato='excel'):
        """
        🆕 FUNCIÓN MOVIDA DESDE VIEWS.PY
        Maneja toda la lógica de exportación de anomalías
        
        🎓 EDUCATIVO: Al mover esta función desde views.py a services,
        separamos las responsabilidades:
        - Views: Manejo HTTP (request/response)  
        - Services: Lógica de negocio (exportación)
        
        Args:
            request: HttpRequest object
            formato: 'excel' o 'csv'
            
        Returns:
            HttpResponse: Archivo para descarga
        """
        try:
            # PASO 1: Construir queryset base con optimizaciones
            queryset = ReportsService._build_optimized_queryset()
            
            # PASO 2: Aplicar filtros de usuario (permisos)
            queryset = ReportsService._apply_user_filters(queryset, request.user)
            
            # PASO 3: Aplicar filtros de la URL
            queryset = ReportsService._apply_url_filters(queryset, request.GET)
            
            # PASO 4: Validar que hay datos
            if not queryset.exists():
                raise ValueError("No hay anomalías para exportar con los filtros aplicados")
            
            # PASO 5: Generar archivo según formato
            if formato.lower() == 'excel':
                return ReportsService._generate_excel_response(queryset)
            else:
                return ReportsService._generate_csv_response(queryset)
                
        except Exception as e:
            # En services, lanzamos excepciones que las views manejan
            raise Exception(f"Error generando reporte: {str(e)}")
    
    @login_required
    @user_passes_test(lambda u: u.rol in ['coordinador_cpa', 'analista_cpa', 'coordinador_carrera'])
    def exportar_reporte_anomalias(request):
        """
        🔧 CORRECCIÓN: Función simplificada que delega a service
        
        🎓 EDUCATIVO: Esta es la versión "thin" que solo maneja HTTP
        y delega la lógica al service.
        """
        try:
            formato = request.GET.get('formato', 'excel')
            
            # Delegar toda la lógica al service
            from .reports_service import ReportsService
            response = ReportsService.exportar_anomalias_completo(request, formato)
            return response
            
        except Exception as e:
            messages.error(request, f'Error generando reporte: {str(e)}')
            return redirect('listado_anomalias')


    @staticmethod
    def _build_optimized_queryset():
        """
        Construye queryset optimizado con select_related
        
        🎓 EDUCATIVO: select_related() evita el problema N+1
        al hacer JOINs en la base de datos en lugar de queries separados.
        """
        return DeteccionAnomalia.objects.select_related(
            'estudiante',
            'estudiante__carrera', 
            'criterio_usado',
            'revisado_por'
        ).prefetch_related(
            'derivacion_set__instancia_apoyo'  # Para derivaciones relacionadas
        ).order_by('-fecha_deteccion')
    
    @staticmethod
    def _apply_user_filters(queryset, user):
        """
        Aplica filtros según el rol del usuario
        
        🎓 EDUCATIVO: Seguridad a nivel de datos - cada usuario
        solo ve los datos que le corresponden según su rol.
        """
        if user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=user)
                return queryset.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                return queryset.none()  # Sin datos si no tiene carrera asignada
        
        # coordinador_cpa y analista_cpa ven todo
        return queryset
    
    @staticmethod
    def _apply_url_filters(queryset, get_params):
        """
        Aplica filtros desde parámetros GET de la URL
        
        🎓 EDUCATIVO: Función pura que recibe datos y retorna
        datos filtrados sin efectos secundarios.
        """
        # Filtro por estado
        estado = get_params.get('estado')
        if estado and estado.strip():
            queryset = queryset.filter(estado=estado)
        
        # Filtro por tipo de anomalía
        tipo = get_params.get('tipo')
        if tipo and tipo.strip():
            queryset = queryset.filter(tipo_anomalia=tipo)
        
        # Filtro por prioridad
        prioridad = get_params.get('prioridad')
        if prioridad and prioridad.strip():
            try:
                prioridad_int = int(prioridad)
                queryset = queryset.filter(prioridad=prioridad_int)
            except ValueError:
                pass  # Ignorar prioridades inválidas
        
        # Filtro por rango de fechas
        fecha_desde = get_params.get('fecha_desde')
        fecha_hasta = get_params.get('fecha_hasta')
        
        if fecha_desde:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_deteccion__date__gte=fecha_desde_obj)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_deteccion__date__lte=fecha_hasta_obj)
            except ValueError:
                pass
        
        return queryset
    
    @staticmethod
    def _generate_excel_response(queryset):
        """
        Genera respuesta HTTP con archivo Excel
        
        🎓 EDUCATIVO: pandas.ExcelWriter permite crear archivos
        Excel con múltiples hojas y formato profesional.
        """
        # Preparar datos para DataFrame
        data = ReportsService._prepare_data_for_export(queryset)
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Hoja principal: Anomalías
            df_anomalias = pd.DataFrame(data['anomalias'])
            df_anomalias.to_excel(writer, sheet_name='Anomalías', index=False)
            
            # Hoja secundaria: Resumen estadístico
            df_resumen = pd.DataFrame(data['resumen'])
            df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
            
            # Hoja terciaria: Derivaciones (si existen)
            if data['derivaciones']:
                df_derivaciones = pd.DataFrame(data['derivaciones'])
                df_derivaciones.to_excel(writer, sheet_name='Derivaciones', index=False)
        
        output.seek(0)
        
        # Configurar respuesta HTTP
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Nombre del archivo con timestamp
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_anomalias_{timestamp}.xlsx'
        response['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
    
    @staticmethod
    def _generate_csv_response(queryset):
        """
        Genera respuesta HTTP con archivo CSV
        
        🎓 EDUCATIVO: CSV es más liviano que Excel y mejor
        para integración con otros sistemas.
        """
        # Preparar datos
        data = ReportsService._prepare_data_for_export(queryset)
        
        # Crear CSV
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_anomalias_{timestamp}.csv'
        response['Content-Disposition'] = f'attachment; filename={filename}'
        
        # Escribir BOM para Excel en español
        response.write('\ufeff')
        
        # Crear DataFrame y exportar
        df = pd.DataFrame(data['anomalias'])
        df.to_csv(response, index=False, encoding='utf-8')
        
        return response
    
    @staticmethod
    def _prepare_data_for_export(queryset):
        """
        Prepara los datos para exportación en formato estructurado
        
        🎓 EDUCATIVO: Separar la preparación de datos permite
        reutilizar esta lógica para diferentes formatos de salida.
        """
        anomalias_data = []
        derivaciones_data = []
        
        # PASO 1: Procesar cada anomalía
        for anomalia in queryset:
            # Datos básicos de la anomalía
            anomalia_row = {
                'ID Anomalía': anomalia.id,
                'ID Estudiante': anomalia.estudiante.id_estudiante,
                'Nombre Estudiante': anomalia.estudiante.nombre,
                'Carrera': anomalia.estudiante.carrera.nombre,
                'Año Ingreso': anomalia.estudiante.ingreso_año,
                'Tipo Anomalía': anomalia.get_tipo_anomalia_display(),
                'Score Anomalía': round(anomalia.score_anomalia, 4),
                'Confianza': round(anomalia.confianza, 2),
                'Prioridad': anomalia.prioridad,
                'Estado': anomalia.get_estado_display(),
                'Fecha Detección': anomalia.fecha_deteccion.strftime('%d/%m/%Y %H:%M'),
                'Promedio General': round(anomalia.promedio_general, 2),
                'Asistencia Promedio': f"{anomalia.asistencia_promedio:.1f}%",
                'Uso Plataforma': f"{anomalia.uso_plataforma_promedio:.1f}%",
                'Variación Notas': round(anomalia.variacion_notas, 2),
                'Criterio Usado': anomalia.criterio_usado.nombre if anomalia.criterio_usado else 'N/A',
                'Revisado Por': anomalia.revisado_por.username if anomalia.revisado_por else 'No revisado',
                'Observaciones': anomalia.observaciones or 'Sin observaciones'
            }
            
            anomalias_data.append(anomalia_row)
            
            # PASO 2: Procesar derivaciones relacionadas
            for derivacion in anomalia.derivacion_set.all():
                derivacion_row = {
                    'ID Anomalía': anomalia.id,
                    'Estudiante': anomalia.estudiante.nombre,
                    'Instancia Apoyo': derivacion.instancia_apoyo.nombre,
                    'Tipo Apoyo': derivacion.instancia_apoyo.get_tipo_display(),
                    'Estado Derivación': derivacion.get_estado_display(),
                    'Fecha Derivación': derivacion.fecha_derivacion.strftime('%d/%m/%Y %H:%M'),
                    'Derivado Por': derivacion.derivado_por.username if derivacion.derivado_por else 'Sistema',
                    'Motivo': derivacion.motivo,
                    'Prioridad Derivación': derivacion.prioridad,
                    'Fecha Respuesta': derivacion.fecha_respuesta.strftime('%d/%m/%Y %H:%M') if derivacion.fecha_respuesta else 'Pendiente'
                }
                derivaciones_data.append(derivacion_row)
        
        # PASO 3: Generar resumen estadístico
        resumen_data = ReportsService._generate_summary_stats(queryset)
        
        return {
            'anomalias': anomalias_data,
            'derivaciones': derivaciones_data,
            'resumen': resumen_data
        }
    
    @staticmethod
    def _generate_summary_stats(queryset):
        """
        Genera estadísticas resumidas para el reporte
        
        🎓 EDUCATIVO: Incluir resúmenes estadísticos hace
        los reportes más útiles para toma de decisiones.
        """
        total_anomalias = queryset.count()
        
        if total_anomalias == 0:
            return [{'Métrica': 'Total Anomalías', 'Valor': 0}]
        
        # Estadísticas por estado
        stats_estado = list(queryset.values('estado').annotate(
            total=Count('id')
        ).values_list('estado', 'total'))
        
        # Estadísticas por tipo
        stats_tipo = list(queryset.values('tipo_anomalia').annotate(
            total=Count('id')
        ).values_list('tipo_anomalia', 'total'))
        
        # Estadísticas por prioridad
        stats_prioridad = list(queryset.values('prioridad').annotate(
            total=Count('id')
        ).values_list('prioridad', 'total'))
        
        # Estadísticas por carrera
        stats_carrera = list(queryset.values('estudiante__carrera__nombre').annotate(
            total=Count('id')
        ).values_list('estudiante__carrera__nombre', 'total'))
        
        # Métricas generales
        promedios = queryset.aggregate(
            promedio_score=Avg('score_anomalia'),
            promedio_confianza=Avg('confianza'),
            promedio_prioridad=Avg('prioridad')
        )
        
        resumen = [
            {'Métrica': 'Total Anomalías', 'Valor': total_anomalias},
            {'Métrica': 'Score Promedio', 'Valor': round(promedios['promedio_score'] or 0, 4)},
            {'Métrica': 'Confianza Promedio', 'Valor': f"{promedios['promedio_confianza'] or 0:.2f}%"},
            {'Métrica': 'Prioridad Promedio', 'Valor': round(promedios['promedio_prioridad'] or 0, 2)},
        ]
        
        # Agregar distribuciones
        resumen.append({'Métrica': '--- DISTRIBUCIÓN POR ESTADO ---', 'Valor': ''})
        for estado, total in stats_estado:
            porcentaje = (total / total_anomalias) * 100
            resumen.append({
                'Métrica': f'Estado: {estado}', 
                'Valor': f'{total} ({porcentaje:.1f}%)'
            })
        
        resumen.append({'Métrica': '--- DISTRIBUCIÓN POR TIPO ---', 'Valor': ''})
        for tipo, total in stats_tipo:
            porcentaje = (total / total_anomalias) * 100
            resumen.append({
                'Métrica': f'Tipo: {tipo}', 
                'Valor': f'{total} ({porcentaje:.1f}%)'
            })
        
        resumen.append({'Métrica': '--- DISTRIBUCIÓN POR CARRERA ---', 'Valor': ''})
        for carrera, total in stats_carrera[:10]:  # Top 10 carreras
            porcentaje = (total / total_anomalias) * 100
            resumen.append({
                'Métrica': f'Carrera: {carrera}', 
                'Valor': f'{total} ({porcentaje:.1f}%)'
            })
        
        return resumen
    
    # ================================================================
    # FUNCIONES EXISTENTES MANTENIDAS
    # ================================================================
    
    @staticmethod
    def exportar_derivaciones_completo(request, formato='excel'):
        """
        Exporta reporte completo de derivaciones
        
        🎓 EDUCATIVO: Reutilizar la misma estructura para 
        diferentes tipos de reportes mantiene consistencia.
        """
        try:
            # Construir queryset de derivaciones
            queryset = Derivacion.objects.select_related(
                'deteccion_anomalia__estudiante',
                'deteccion_anomalia__estudiante__carrera',
                'instancia_apoyo',
                'derivado_por'
            ).order_by('-fecha_derivacion')
            
            # Aplicar filtros de usuario
            if request.user.rol == 'coordinador_carrera':
                try:
                    carrera = Carrera.objects.get(coordinador=request.user)
                    queryset = queryset.filter(
                        deteccion_anomalia__estudiante__carrera=carrera
                    )
                except Carrera.DoesNotExist:
                    queryset = queryset.none()
            
            # Aplicar filtros de URL
            estado = request.GET.get('estado')
            if estado:
                queryset = queryset.filter(estado=estado)
            
            if not queryset.exists():
                raise ValueError("No hay derivaciones para exportar")
            
            # Generar archivo
            if formato.lower() == 'excel':
                return ReportsService._generate_derivaciones_excel(queryset)
            else:
                return ReportsService._generate_derivaciones_csv(queryset)
                
        except Exception as e:
            raise Exception(f"Error generando reporte de derivaciones: {str(e)}")
    
    @staticmethod
    def _generate_derivaciones_excel(queryset):
        """Genera Excel específico para derivaciones"""
        output = BytesIO()
        
        data = []
        for derivacion in queryset:
            data.append({
                'ID Derivación': derivacion.id,
                'Estudiante': derivacion.deteccion_anomalia.estudiante.nombre,
                'ID Estudiante': derivacion.deteccion_anomalia.estudiante.id_estudiante,
                'Carrera': derivacion.deteccion_anomalia.estudiante.carrera.nombre,
                'Tipo Anomalía': derivacion.deteccion_anomalia.get_tipo_anomalia_display(),
                'Instancia Apoyo': derivacion.instancia_apoyo.nombre,
                'Tipo Apoyo': derivacion.instancia_apoyo.get_tipo_display(),
                'Estado': derivacion.get_estado_display(),
                'Prioridad': derivacion.prioridad,
                'Fecha Derivación': derivacion.fecha_derivacion.strftime('%d/%m/%Y %H:%M'),
                'Derivado Por': derivacion.derivado_por.username if derivacion.derivado_por else 'Sistema',
                'Motivo': derivacion.motivo,
                'Fecha Respuesta': derivacion.fecha_respuesta.strftime('%d/%m/%Y %H:%M') if derivacion.fecha_respuesta else 'Pendiente',
                'Contacto': derivacion.instancia_apoyo.contacto,
                'Email': derivacion.instancia_apoyo.email
            })
        
        df = pd.DataFrame(data)
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_derivaciones_{timestamp}.xlsx'
        response['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
    
    @staticmethod
    def _generate_derivaciones_csv(queryset):
        """Genera CSV específico para derivaciones"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_derivaciones_{timestamp}.csv'
        response['Content-Disposition'] = f'attachment; filename={filename}'
        
        # BOM para Excel
        response.write('\ufeff')
        
        data = []
        for derivacion in queryset:
            data.append({
                'ID Derivación': derivacion.id,
                'Estudiante': derivacion.deteccion_anomalia.estudiante.nombre,
                'Carrera': derivacion.deteccion_anomalia.estudiante.carrera.nombre,
                'Instancia Apoyo': derivacion.instancia_apoyo.nombre,
                'Estado': derivacion.get_estado_display(),
                'Fecha Derivación': derivacion.fecha_derivacion.strftime('%d/%m/%Y %H:%M'),
                'Derivado Por': derivacion.derivado_por.username if derivacion.derivado_por else 'Sistema'
            })
        
        df = pd.DataFrame(data)
        df.to_csv(response, index=False, encoding='utf-8')
        
        return response

# ================================================================
# FUNCIONES DE VISTA SIMPLIFICADAS (para mantener en views.py)
# ================================================================

@login_required
@user_passes_test(lambda u: u.rol in ['coordinador_cpa', 'analista_cpa', 'coordinador_carrera'])
def exportar_reporte_derivaciones(request):
    """
    Vista HTTP para exportar derivaciones
    
    🎓 EDUCATIVO: Vista "thin" que solo maneja HTTP,
    delegando toda la lógica al service.
    """
    try:
        formato = request.GET.get('formato', 'excel')
        response = ReportsService.exportar_derivaciones_completo(request, formato)
        return response
        
    except Exception as e:
        messages.error(request, str(e))
        return redirect('gestionar_derivaciones')

@login_required  
@user_passes_test(lambda u: u.rol in ['coordinador_cpa', 'analista_cpa'])
def exportar_todas_anomalias(request):
    """
    Vista para exportar TODAS las anomalías sin filtros
    
    🎓 EDUCATIVO: Endpoint específico para reportes completos,
    útil para análisis administrativos.
    """
    try:
        formato = request.GET.get('formato', 'excel')
        
        # Crear request simulado sin filtros
        class RequestSinFiltros:
            def __init__(self, user):
                self.user = user
                self.GET = {}  # Sin filtros
        
        request_limpio = RequestSinFiltros(request.user)
        response = ReportsService.exportar_anomalias_completo(request_limpio, formato)
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error exportando todas las anomalías: {str(e)}')
        return redirect('listado_anomalias')

