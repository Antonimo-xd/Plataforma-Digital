from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Q
import logging
from ..models import (Carrera, AlertaAutomatica, Derivacion)
from ..utils.helpers import (_obtener_estadisticas_sistema, _determinar_estado_sistema, _calcular_asignaturas_criticas, detalle_derivacion_ajax)
from ..utils.permissions import (puede_administrar_sistema, puede_ver_estadisticas)

# ================================================================
# CONFIGURACIÓN DE LOGGING
# ================================================================
logger = logging.getLogger(__name__)

# ================================================================
# DECORADORES DE PERMISOS PERSONALIZADOS
# ================================================================

@login_required
@user_passes_test(lambda u: u.rol in ['analista_cpa', 'coordinador_cpa', 'coordinador_carrera', 'admin'])
def asignaturas_criticas(request):
    """
    Vista simplificada para análisis de asignaturas críticas

    🎓 EDUCATIVO: Enfocarse en una sola responsabilidad:
    mostrar asignaturas con alto índice de anomalías.
    """
    from ..models import Asignatura

    # Obtener asignaturas con más anomalías
    asignaturas_data = _calcular_asignaturas_criticas()

    # Calcular estadísticas adicionales
    total_asignaturas = Asignatura.objects.count()
    total_criticas = len(asignaturas_data)

    # Calcular promedio de anomalías
    if asignaturas_data:
        promedio_anomalias = sum(a['porcentaje_anomalias'] for a in asignaturas_data) / len(asignaturas_data)
    else:
        promedio_anomalias = 0

    context = {
        'asignaturas_criticas': asignaturas_data,
        'umbral_criticidad': 20,  # 20% de estudiantes con anomalías
        'total_asignaturas': total_asignaturas,
        'total_criticas': total_criticas,
        'promedio_anomalias_carrera': promedio_anomalias
    }

    return render(request, 'anomalias/asignaturas_criticas.html', context)

@login_required
@user_passes_test(puede_administrar_sistema)
def verificar_sistema(request):
    """
    Vista simplificada para verificación del sistema

    🎓 EDUCATIVO: Dashboard de salud del sistema enfocado
    en métricas clave, no en detalles técnicos.
    """
    stats = _obtener_estadisticas_sistema()
    estado_sistema = _determinar_estado_sistema(stats)

    # Detectar problemas específicos con mensajes más claros
    problemas = []
    if stats.get('criterios_activos', 0) == 0:
        problemas.append({
            'titulo': 'Sin criterios configurados',
            'descripcion': 'No hay criterios de detección activos. Configure al menos un criterio para detectar anomalías.',
            'accion': 'Ir a Configuración de Criterios',
            'gravedad': 'alta'
        })
    if stats.get('estudiantes_activos', 0) < 10:
        problemas.append({
            'titulo': f'Pocos estudiantes activos ({stats.get("estudiantes_activos", 0)})',
            'descripcion': 'El sistema necesita al menos 10 estudiantes activos para funcionar correctamente.',
            'accion': 'Importar más datos de estudiantes',
            'gravedad': 'media'
        })
    if stats.get('registros_academicos', 0) < 30:
        problemas.append({
            'titulo': f'Registros académicos insuficientes ({stats.get("registros_academicos", 0)})',
            'descripcion': 'Se requieren al menos 30 registros académicos para realizar análisis confiables.',
            'accion': 'Importar registros académicos',
            'gravedad': 'media'
        })
    if stats.get('anomalias_pendientes', 0) > stats.get('anomalias_total', 1) * 0.8:
        problemas.append({
            'titulo': f'Muchas anomalías pendientes ({stats.get("anomalias_pendientes", 0)})',
            'descripcion': 'Más del 80% de las anomalías están pendientes de revisión.',
            'accion': 'Revisar anomalías pendientes',
            'gravedad': 'baja'
        })

    # Determinar estado general más descriptivo
    if not problemas:
        estado_display = 'Operativo'
        estado_mensaje = 'El sistema está funcionando correctamente sin problemas detectados.'
    elif any(p['gravedad'] == 'alta' for p in problemas):
        estado_display = 'Atención Requerida'
        estado_mensaje = 'Se detectaron problemas críticos que requieren atención inmediata.'
    elif any(p['gravedad'] == 'media' for p in problemas):
        estado_display = 'Advertencia'
        estado_mensaje = 'Se detectaron advertencias que deberían ser atendidas pronto.'
    else:
        estado_display = 'Operativo con Observaciones'
        estado_mensaje = 'El sistema funciona pero hay observaciones menores.'

    context = {
        'stats': stats,
        'estado_general': estado_sistema.get('estado', 'unknown'),
        'estado_display': estado_display,
        'estado_mensaje': estado_mensaje,
        'problemas': problemas
    }

    return render(request, 'anomalias/verificar_sistema.html', context)

@login_required
def alertas_usuario(request):
    """
    Vista mejorada para alertas del usuario

    🎓 EDUCATIVO: Filtrar alertas según el rol del usuario
    y mostrar información relevante sobre anomalías críticas.
    """
    from ..models import DeteccionAnomalia
    from django.urls import reverse

    # ================================================================
    # 1. ALERTAS AUTOMÁTICAS
    # ================================================================
    alertas_sistema = AlertaAutomatica.objects.filter(activa=True)

    if request.user.rol == 'coordinador_carrera':
        # Solo alertas de su carrera
        try:
            carrera = Carrera.objects.get(coordinador=request.user)
            alertas_sistema = alertas_sistema.filter(
                Q(deteccion_relacionada__estudiante__carrera=carrera) |
                Q(asignatura_relacionada__carrera=carrera) |
                Q(deteccion_relacionada__isnull=True, asignatura_relacionada__isnull=True)
            )
        except Carrera.DoesNotExist:
            alertas_sistema = alertas_sistema.none()

    # ================================================================
    # 2. PERSONAS CON ANOMALÍAS CRÍTICAS
    # ================================================================
    anomalias_criticas = DeteccionAnomalia.objects.filter(
        nivel_criticidad='alta',
        estado__in=['detectado', 'en_revision', 'intervencion_activa']
    ).select_related('estudiante', 'estudiante__carrera')

    # Filtrar por rol
    if request.user.rol == 'coordinador_carrera':
        try:
            carrera = Carrera.objects.get(coordinador=request.user)
            anomalias_criticas = anomalias_criticas.filter(estudiante__carrera=carrera)
        except Carrera.DoesNotExist:
            anomalias_criticas = anomalias_criticas.none()

    # Agrupar por estudiante para evitar duplicados
    estudiantes_criticos = {}
    for anomalia in anomalias_criticas:
        estudiante_id = anomalia.estudiante.pk  # usar pk en lugar de id
        if estudiante_id not in estudiantes_criticos:
            estudiantes_criticos[estudiante_id] = {
                'estudiante': anomalia.estudiante,
                'anomalias': [],
                'prioridad_maxima': 0,
                'score_minimo': 100
            }

        estudiantes_criticos[estudiante_id]['anomalias'].append(anomalia)
        estudiantes_criticos[estudiante_id]['prioridad_maxima'] = max(
            estudiantes_criticos[estudiante_id]['prioridad_maxima'],
            anomalia.prioridad
        )
        estudiantes_criticos[estudiante_id]['score_minimo'] = min(
            estudiantes_criticos[estudiante_id]['score_minimo'],
            anomalia.score_anomalia
        )

    # Ordenar por prioridad y score
    estudiantes_criticos_lista = sorted(
        estudiantes_criticos.values(),
        key=lambda x: (-x['prioridad_maxima'], x['score_minimo'])
    )

    # ================================================================
    # 3. FORMATEAR ALERTAS PARA EL TEMPLATE
    # ================================================================
    alertas_formateadas = []

    # Agregar alertas de sistema
    for alerta in alertas_sistema.order_by('-fecha_creacion')[:10]:
        icono = 'fas fa-exclamation-circle'
        color = 'warning'
        url = '#'

        if alerta.tipo == 'nueva_anomalia':
            icono = 'fas fa-user-exclamation'
            color = 'info'
            if alerta.deteccion_relacionada:
                url = reverse('detalle_anomalia', args=[alerta.deteccion_relacionada.pk])
        elif alerta.tipo == 'anomalia_critica':
            icono = 'fas fa-exclamation-triangle'
            color = 'danger'
            if alerta.deteccion_relacionada:
                url = reverse('detalle_anomalia', args=[alerta.deteccion_relacionada.pk])
        elif alerta.tipo == 'asignatura_critica':
            icono = 'fas fa-book-dead'
            color = 'warning'
            url = reverse('asignaturas_criticas')
        elif alerta.tipo == 'seguimiento_vencido':
            icono = 'fas fa-clock'
            color = 'secondary'

        alertas_formateadas.append({
            'titulo': alerta.titulo,
            'mensaje': alerta.mensaje,
            'fecha': alerta.fecha_creacion,
            'icono': icono,
            'color': color,
            'url': url
        })

    context = {
        'alertas': alertas_formateadas,
        'total_alertas': len(alertas_formateadas),
        'estudiantes_criticos': estudiantes_criticos_lista,
        'total_criticos': len(estudiantes_criticos_lista)
    }

    return render(request, 'anomalias/alertas.html', context)

@login_required
@user_passes_test(lambda u: u.rol in ['analista_cpa', 'coordinador_cpa', 'coordinador_carrera', 'admin'])
def detalle_derivacion_view(request, derivacion_id):
    """
    Vista para obtener detalles de una derivación (AJAX o JSON response)

    Envuelve la función helper detalle_derivacion_ajax y retorna JSON
    """
    try:
        detalles = detalle_derivacion_ajax(derivacion_id, request.user)
        return JsonResponse({
            'success': True,
            'data': detalles
        })
    except Derivacion.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Derivación {derivacion_id} no encontrada'
        }, status=404)
    except PermissionError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=403)
    except Exception as e:
        logger.error(f"Error obteniendo detalle de derivación {derivacion_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=500)