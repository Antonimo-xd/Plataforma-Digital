from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import timedelta, datetime
import json
# Imports de modelos - mantener las mismas dependencias
from ..models import (
    DeteccionAnomalia, Estudiante, RegistroAcademico, 
    Carrera, Asignatura, Derivacion, Usuario, CriterioAnomalia,
    EjecucionAnalisis
)
from ..ML import ejecutar_deteccion_anomalias

class DashboardAPI:
    """
    Clase de servicio para APIs del dashboard
    
    Educativo: Usar clases estáticas para organizar funciones relacionadas
    es un patrón común en servicios. Facilita testing y reutilización.
    """
    
    @staticmethod
    def get_evolution_data(user, days=30):
        """
        Obtiene datos de evolución temporal de anomalías
        
        Args:
            user: Usuario autenticado
            days: Número de días hacia atrás (default: 30)
            
        Returns:
            dict: Datos formateados para gráficos
        """
        try:
            # Filtrar anomalías según permisos del usuario
            anomalias = DeteccionAnomalia.objects.all()
            
            if user.rol == 'coordinador_carrera':
                try:
                    carrera = Carrera.objects.get(coordinador=user)
                    anomalias = anomalias.filter(estudiante__carrera=carrera)
                except Carrera.DoesNotExist:
                    pass
            
            # Calcular rango de fechas
            fecha_fin = timezone.now().date()
            fecha_inicio = fecha_fin - timedelta(days=days)
            
            # Generar lista completa de fechas (para llenar huecos)
            fechas_completas = []
            fecha_actual = fecha_inicio
            while fecha_actual <= fecha_fin:
                fechas_completas.append(fecha_actual)
                fecha_actual += timedelta(days=1)
            
            # Obtener conteos por fecha
            anomalias_por_fecha = {}
            queryset = anomalias.filter(
                fecha_deteccion__date__gte=fecha_inicio,
                fecha_deteccion__date__lte=fecha_fin
            ).extra(
                select={'dia': 'date(fecha_deteccion)'}
            ).values('dia').annotate(
                total=Count('id')
            )
            
            # Convertir a diccionario para fácil acceso
            for item in queryset:
                anomalias_por_fecha[item['dia']] = item['total']
            
            # Preparar datos con ceros para fechas sin anomalías
            evolution_data = {
                'fechas': [fecha.strftime('%Y-%m-%d') for fecha in fechas_completas],
                'counts': [anomalias_por_fecha.get(fecha, 0) for fecha in fechas_completas],
                'labels': [fecha.strftime('%d/%m') for fecha in fechas_completas]
            }
            
            return {
                'success': True,
                'evolucion_temporal': evolution_data,
                'total_periodo': sum(evolution_data['counts']),
                'promedio_diario': round(sum(evolution_data['counts']) / len(fechas_completas), 1)
            }
            
        except Exception as e:
            print(f"❌ Error en get_evolution_data: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'evolucion_temporal': {'fechas': [], 'counts': [], 'labels': []}
            }
    
    @staticmethod
    def get_anomaly_types_distribution(user):
        """
        Obtiene distribución de tipos de anomalías
        
        Args:
            user: Usuario autenticado
            
        Returns:
            dict: Distribución por tipo de anomalía
        """
        try:
            # Base queryset con filtros de permiso
            anomalias = DeteccionAnomalia.objects.all()
            
            if user.rol == 'coordinador_carrera':
                try:
                    carrera = Carrera.objects.get(coordinador=user)
                    anomalias = anomalias.filter(estudiante__carrera=carrera)
                except Carrera.DoesNotExist:
                    pass
            
            # Agregar etiquetas descriptivas
            tipo_labels = {
                'bajo_rendimiento': 'Bajo Rendimiento',
                'alta_inasistencia': 'Alta Inasistencia', 
                'bajo_uso_plataforma': 'Bajo Uso de Plataforma',
                'multiple': 'Múltiples Factores',
                'riesgo_desercion': 'Riesgo de Deserción'
            }
            
            # Obtener distribución
            anomalias_por_tipo = list(
                anomalias.values('tipo_anomalia')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
            
            # Formatear para frontend
            for item in anomalias_por_tipo:
                tipo_raw = item['tipo_anomalia']
                item['tipo_anomalia'] = tipo_labels.get(
                    tipo_raw, 
                    tipo_raw.replace('_', ' ').title()
                )
                item['porcentaje'] = 0
            
            # Calcular porcentajes
            total = sum(item['count'] for item in anomalias_por_tipo)
            if total > 0:
                for item in anomalias_por_tipo:
                    item['porcentaje'] = round((item['count'] / total) * 100, 1)
            
            return {
                'success': True,
                'anomalias_por_tipo': anomalias_por_tipo,
                'total_anomalias': total
            }
            
        except Exception as e:
            print(f"❌ Error en get_anomaly_types_distribution: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'anomalias_por_tipo': []
            }
    
    @staticmethod
    def get_real_time_stats(user):
        """
        Obtiene estadísticas en tiempo real
        
        Args:
            user: Usuario autenticado
            
        Returns:
            dict: Estadísticas actualizadas
        """
        try:
            # Base queries con filtros de permiso
            estudiantes_query = Estudiante.objects.filter(activo=True)
            anomalias_query = DeteccionAnomalia.objects.all()
            derivaciones_query = Derivacion.objects.all()
            
            # Filtrar por rol
            if user.rol == 'coordinador_carrera':
                try:
                    carrera = Carrera.objects.get(coordinador=user)
                    estudiantes_query = estudiantes_query.filter(carrera=carrera)
                    anomalias_query = anomalias_query.filter(estudiante__carrera=carrera)
                    derivaciones_query = derivaciones_query.filter(
                        deteccion_anomalia__estudiante__carrera=carrera
                    )
                except Carrera.DoesNotExist:
                    pass
            
            # Calcular estadísticas
            total_estudiantes = estudiantes_query.count()
            total_anomalias = anomalias_query.count()
            anomalias_activas = anomalias_query.filter(
                estado__in=['detectado', 'en_revision', 'intervencion_activa']
            ).count()
            anomalias_criticas = anomalias_query.filter(prioridad__gte=4).count()
            derivaciones_pendientes = derivaciones_query.filter(
                estado='pendiente'
            ).count()
            
            # Calcular tasa de anomalías
            tasa_anomalias = 0
            if total_estudiantes > 0:
                tasa_anomalias = round((anomalias_activas / total_estudiantes) * 100, 2)
            
            return {
                'success': True,
                'stats': {
                    'total_estudiantes': total_estudiantes,
                    'total_anomalias': total_anomalias,
                    'anomalias_activas': anomalias_activas,
                    'anomalias_criticas': anomalias_criticas,
                    'derivaciones_pendientes': derivaciones_pendientes,
                    'tasa_anomalias': tasa_anomalias
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error en get_real_time_stats: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'stats': {}
            }

# ================================================================
# FUNCIONES DE API (Mantienen la interfaz original)
# ================================================================

@login_required
def api_datos_dashboard(request):
    """
    🎯 API principal para datos del dashboard
    
    Educativo: Esta función actúa como una fachada (Facade Pattern)
    que coordina múltiples servicios para generar respuesta completa.
    """
    try:
        # Usar los métodos estáticos del servicio
        evolution_data = DashboardAPI.get_evolution_data(request.user, 30)
        types_data = DashboardAPI.get_anomaly_types_distribution(request.user)
        stats_data = DashboardAPI.get_real_time_stats(request.user)
        
        # Combinar resultados
        response_data = {
            'success': True,
            'evolucion_temporal': evolution_data.get('evolucion_temporal', {}),
            'anomalias_por_tipo': types_data.get('anomalias_por_tipo', []),
            'estadisticas': stats_data.get('stats', {}),
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"❌ Error en api_datos_dashboard: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'evolucion_temporal': {'fechas': [], 'counts': []},
            'anomalias_por_tipo': [],
            'estadisticas': {}
        }, status=500)

@login_required  
def api_evolucion_anomalias(request):
    """
    📈 API específica para evolución temporal de anomalías
    """
    try:
        dias = int(request.GET.get('dias', 30))
        result = DashboardAPI.get_evolution_data(request.user, dias)
        
        if result['success']:
            # Formatear específicamente para Chart.js
            evolution = result['evolucion_temporal']
            chart_data = {
                'labels': evolution['labels'],
                'datasets': [{
                    'label': 'Anomalías Detectadas',
                    'data': evolution['counts'],
                    'borderColor': '#3498db',
                    'backgroundColor': 'rgba(52, 152, 219, 0.1)',
                    'tension': 0.4,
                    'fill': True
                }]
            }
            
            return JsonResponse({
                'success': True,
                'chart_data': chart_data,
                'total_anomalias': result['total_periodo'],
                'periodo_dias': dias
            })
        else:
            return JsonResponse(result, status=500)
            
    except Exception as e:
        print(f"❌ Error en api_evolucion_anomalias: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_tipos_anomalias(request):
    """
    🎯 API específica para distribución de tipos de anomalías
    """
    try:
        result = DashboardAPI.get_anomaly_types_distribution(request.user)
        
        if result['success']:
            # Formatear para gráfico de dona/pie
            chart_data = {
                'labels': [item['tipo_anomalia'] for item in result['anomalias_por_tipo']],
                'datasets': [{
                    'data': [item['count'] for item in result['anomalias_por_tipo']],
                    'backgroundColor': [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
                        '#9966FF', '#FF9F40', '#C9CBCF'
                    ]
                }]
            }
            
            return JsonResponse({
                'success': True,
                'chart_data': chart_data,
                'tipos_detalle': result['anomalias_por_tipo'],
                'total_anomalias': result['total_anomalias']
            })
        else:
            return JsonResponse(result, status=500)
            
    except Exception as e:
        print(f"❌ Error en api_tipos_anomalias: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_datos_tiempo_real(request):
    """
    ⏱️ API para datos en tiempo real (stats básicas)
    """
    try:
        result = DashboardAPI.get_real_time_stats(request.user)
        return JsonResponse(result)
        
    except Exception as e:
        print(f"❌ Error en api_datos_tiempo_real: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_alertas_count(request):
    """
    🔔 API para contar alertas no leídas del usuario
    """
    try:
        alertas_count = 0
        
        # Contar anomalías críticas nuevas (últimas 24 horas)
        anomalias_criticas = DeteccionAnomalia.objects.filter(
            prioridad__gte=4,
            estado='detectado',
            fecha_deteccion__gte=timezone.now() - timedelta(hours=24)
        )
        
        # Filtrar por rol
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                anomalias_criticas = anomalias_criticas.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                pass
        
        alertas_count += anomalias_criticas.count()
        
        # Contar derivaciones pendientes (solo para analistas)
        derivaciones_pendientes = 0
        if request.user.rol in ['analista_cpa', 'coordinador_cpa']:
            derivaciones_pendientes = Derivacion.objects.filter(
                estado='pendiente',
                fecha_derivacion__gte=timezone.now() - timedelta(hours=48)
            ).count()
            alertas_count += derivaciones_pendientes
        
        return JsonResponse({
            'success': True,
            'count': alertas_count,
            'timestamp': timezone.now().isoformat(),
            'detalles': {
                'anomalias_criticas': anomalias_criticas.count(),
                'derivaciones_pendientes': derivaciones_pendientes
            }
        })
        
    except Exception as e:
        print(f"❌ Error en api_alertas_count: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_distribucion_carrera(request):
    """
    📊 API para distribución de anomalías por carrera
    """
    try:
        # Solo coordinadores CPA pueden ver todas las carreras
        if request.user.rol not in ['coordinador_cpa', 'analista_cpa']:
            return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
        
        # Obtener distribución por carrera
        distribucion = DeteccionAnomalia.objects.filter(
            estado__in=['detectado', 'en_revision', 'intervencion_activa']
        ).values(
            'estudiante__carrera__nombre'
        ).annotate(
            count=Count('id'),
            estudiantes_total=Count('estudiante__id', distinct=True)
        ).order_by('-count')
        
        # Formatear datos
        carreras_data = []
        for item in distribucion:
            carrera_nombre = item['estudiante__carrera__nombre'] or 'Sin Carrera'
            carreras_data.append({
                'carrera': carrera_nombre,
                'anomalias': item['count'],
                'estudiantes_afectados': item['estudiantes_total']
            })
        
        return JsonResponse({
            'success': True,
            'distribucion_carreras': carreras_data,
            'total_carreras': len(carreras_data)
        })
        
    except Exception as e:
        print(f"❌ Error en api_distribucion_carrera: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_registros_semestre(request):
    """
    📚 API para distribución de registros por semestre
    """
    try:
        # Obtener distribución por semestre
        distribucion = RegistroAcademico.objects.values(
            'asignatura__semestre'
        ).annotate(
            total_registros=Count('id'),
            promedio_general=Avg('promedio_notas'),
            promedio_asistencia=Avg('porcentaje_asistencia')
        ).order_by('asignatura__semestre')
        
        # Formatear datos
        semestres_data = []
        for item in distribucion:
            semestre = item['asignatura__semestre'] or 0
            semestres_data.append({
                'semestre': f'Semestre {semestre}',
                'total_registros': item['total_registros'],
                'promedio_notas': round(item['promedio_general'] or 0, 2),
                'promedio_asistencia': round(item['promedio_asistencia'] or 0, 1)
            })
        
        return JsonResponse({
            'success': True,
            'distribucion_semestres': semestres_data,
            'total_semestres': len(semestres_data)
        })
        
    except Exception as e:
        print(f"❌ Error en api_registros_semestre: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_probar_analisis(request):
    """
    🧪 API para probar análisis de ML en desarrollo
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    # Solo coordinadores CPA pueden ejecutar pruebas
    if request.user.rol != 'coordinador_cpa':
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    try:
        # Obtener criterio activo para prueba
        criterio = CriterioAnomalia.objects.filter(activo=True).first()
        if not criterio:
            return JsonResponse({
                'success': False, 
                'error': 'No hay criterios activos para probar'
            })
        
        # Ejecutar análisis de prueba
        print("🧪 Ejecutando análisis de prueba...")
        resultado = ejecutar_deteccion_anomalias(criterio, request.user)
        
        if resultado['exitoso']:
            return JsonResponse({
                'success': True,
                'resultados': {
                    'anomalias_detectadas': resultado['anomalias_detectadas'],
                    'total_estudiantes': resultado['total_estudiantes'],
                    'tiempo_ejecucion': f"{resultado.get('tiempo_ejecucion', 0):.2f}s",
                    'criterio_usado': criterio.nombre
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': resultado['error']
            })
            
    except Exception as e:
        print(f"❌ Error en api_probar_analisis: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required  
def api_estadisticas_distribucion(request):
    """
    📊 API para estadísticas de distribución general
    """
    try:
        # Estadísticas generales
        stats = {
            'estudiantes_activos': Estudiante.objects.filter(activo=True).count(),
            'total_registros': RegistroAcademico.objects.count(),
            'carreras_activas': Carrera.objects.count(),
            'asignaturas_activas': Asignatura.objects.count(),
            'criterios_activos': CriterioAnomalia.objects.filter(activo=True).count(),
            'ejecuciones_exitosas': EjecucionAnalisis.objects.filter(exitoso=True).count()
        }
        
        # Filtrar por rol si es necesario
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                stats['estudiantes_activos'] = Estudiante.objects.filter(
                    carrera=carrera, activo=True
                ).count()
                stats['carreras_activas'] = 1
            except Carrera.DoesNotExist:
                pass
        
        # Calcular ratios útiles
        if stats['estudiantes_activos'] > 0:
            stats['registros_por_estudiante'] = round(
                stats['total_registros'] / stats['estudiantes_activos'], 1
            )
        else:
            stats['registros_por_estudiante'] = 0
        
        return JsonResponse({
            'success': True,
            'estadisticas': stats,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error en api_estadisticas_distribucion: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_estudiante_detalle(request, estudiante_id):
    """
    👤 API para obtener detalle completo de un estudiante
    """
    try:
        # Obtener estudiante
        estudiante = Estudiante.objects.select_related('carrera').get(
            id_estudiante=estudiante_id
        )
        
        # Verificar permisos
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                if estudiante.carrera != carrera:
                    return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
            except Carrera.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
        
        # Obtener registros académicos
        registros = RegistroAcademico.objects.filter(
            estudiante=estudiante
        ).select_related('asignatura').order_by('-fecha_registro')
        
        # Obtener anomalías
        anomalias = DeteccionAnomalia.objects.filter(
            estudiante=estudiante
        ).order_by('-fecha_deteccion')
        
        # Calcular estadísticas
        if registros.exists():
            promedio_general = sum(r.promedio_notas for r in registros) / len(registros)
            asistencia_promedio = sum(r.porcentaje_asistencia for r in registros) / len(registros)
        else:
            promedio_general = 0
            asistencia_promedio = 0
        
        # Formatear respuesta
        data = {
            'success': True,
            'estudiante': {
                'id': estudiante.id_estudiante,
                'nombre': estudiante.nombre,
                'carrera': estudiante.carrera.nombre if estudiante.carrera else 'Sin carrera',
                'ingreso_año': estudiante.ingreso_año,
                'activo': estudiante.activo
            },
            'estadisticas': {
                'total_registros': registros.count(),
                'promedio_general': round(promedio_general, 2),
                'asistencia_promedio': round(asistencia_promedio, 1),
                'total_anomalias': anomalias.count(),
                'anomalias_activas': anomalias.filter(
                    estado__in=['detectado', 'en_revision', 'intervencion_activa']
                ).count()
            },
            'registros_recientes': [
                {
                    'asignatura': r.asignatura.nombre,
                    'promedio': r.promedio_notas,
                    'asistencia': r.porcentaje_asistencia,
                    'fecha': r.fecha_registro.isoformat()
                } for r in registros[:5]
            ],
            'anomalias_recientes': [
                {
                    'tipo': a.get_tipo_anomalia_display(),
                    'prioridad': a.prioridad,
                    'estado': a.get_estado_display(),
                    'fecha': a.fecha_deteccion.isoformat()
                } for a in anomalias[:3]
            ]
        }
        
        return JsonResponse(data)
        
    except Estudiante.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Estudiante no encontrado'}, status=404)
    except Exception as e:
        print(f"❌ Error en api_estudiante_detalle: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def api_exportar_datos_avanzado(request):
    """
    API para exportación avanzada con múltiples opciones
    
    🎓 EDUCATIVO: API REST que permite configurar exactamente
    qué datos exportar para integraciones externas.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        # Leer configuración JSON
        config = json.loads(request.body)
        
        # Validar configuración
        required_fields = ['tipo_reporte', 'formato', 'incluir_derivaciones']
        for field in required_fields:
            if field not in config:
                return JsonResponse({'error': f'Campo requerido: {field}'}, status=400)
        
        # Procesar según tipo de reporte
        if config['tipo_reporte'] == 'anomalias':
            response = ReportsService.exportar_anomalias_completo(
                request, 
                config['formato']
            )
        elif config['tipo_reporte'] == 'derivaciones':
            response = ReportsService.exportar_derivaciones_completo(
                request,
                config['formato'] 
            )
        else:
            return JsonResponse({'error': 'Tipo de reporte no válido'}, status=400)
        
        return response
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    """
    Aplica filtros comunes a los querysets de exportación
    
    Args:
        queryset: QuerySet base
        request_params: Parámetros del request (GET)
        
    Returns:
        QuerySet: QuerySet filtrado
    """
    try:
        # Filtro por estado
        estado = request_params.get('estado')
        if estado and estado.strip():
            queryset = queryset.filter(estado=estado)
        
        # Filtro por tipo (solo para anomalías)
        tipo = request_params.get('tipo')
        if tipo and tipo.strip() and hasattr(queryset.model, 'tipo_anomalia'):
            queryset = queryset.filter(tipo_anomalia=tipo)
        
        # Filtro por prioridad (solo para anomalías)
        prioridad = request_params.get('prioridad')
        if prioridad and prioridad.strip() and hasattr(queryset.model, 'prioridad'):
            try:
                prioridad_int = int(prioridad)
                queryset = queryset.filter(prioridad=prioridad_int)
            except ValueError:
                pass
        
        # Filtro por fecha
        fecha_desde = request_params.get('fecha_desde')
        if fecha_desde:
            try:
                fecha = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                if hasattr(queryset.model, 'fecha_deteccion'):
                    queryset = queryset.filter(fecha_deteccion__date__gte=fecha)
                elif hasattr(queryset.model, 'fecha_derivacion'):
                    queryset = queryset.filter(fecha_derivacion__date__gte=fecha)
            except ValueError:
                pass
        
        fecha_hasta = request_params.get('fecha_hasta')
        if fecha_hasta:
            try:
                fecha = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                if hasattr(queryset.model, 'fecha_deteccion'):
                    queryset = queryset.filter(fecha_deteccion__date__lte=fecha)
                elif hasattr(queryset.model, 'fecha_derivacion'):
                    queryset = queryset.filter(fecha_derivacion__date__lte=fecha)
            except ValueError:
                pass
        
        # Filtro de búsqueda (solo para anomalías)
        buscar = request_params.get('buscar')
        if buscar and buscar.strip() and hasattr(queryset.model, 'estudiante'):
            queryset = queryset.filter(
                Q(estudiante__nombre__icontains=buscar) |
                Q(estudiante__id_estudiante__icontains=buscar)
            )
        
        return queryset
        
    except Exception as e:
        print(f"❌ Error aplicando filtros: {str(e)}")
        return queryset





