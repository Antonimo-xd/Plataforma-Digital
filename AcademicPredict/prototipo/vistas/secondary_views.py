from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
import logging
from ..models import (Carrera, AlertaAutomatica)
from ..utils.helpers import (_obtener_estadisticas_sistema, _determinar_estado_sistema, _calcular_asignaturas_criticas)
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

    # Obtener asignaturas con más anomalías
    asignaturas_data = _calcular_asignaturas_criticas()

    context = {
        'asignaturas_criticas': asignaturas_data,
        'umbral_critico': 20,  # 20% de estudiantes con anomalías
        'total_asignaturas': len(asignaturas_data)
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

    # Detectar problemas específicos
    problemas = []
    if stats.get('criterios_activos', 0) == 0:
        problemas.append('No hay criterios activos configurados')
    if stats.get('estudiantes_activos', 0) < 10:
        problemas.append('Muy pocos estudiantes activos en el sistema')
    if stats.get('registros_academicos', 0) < 30:
        problemas.append('Insuficientes registros académicos para análisis')
    if stats.get('anomalias_pendientes', 0) > stats.get('anomalias_total', 1) * 0.8:
        problemas.append('Muchas anomalías pendientes de revisión')

    context = {
        'stats': stats,
        'estado_general': estado_sistema.get('estado', 'unknown'),
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