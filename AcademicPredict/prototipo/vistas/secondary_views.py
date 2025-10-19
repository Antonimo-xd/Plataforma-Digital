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
@user_passes_test(puede_ver_estadisticas)
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
    
    context = {
        'stats': stats,
        'estado_general': _determinar_estado_sistema(stats)
    }
    
    return render(request, 'anomalias/verificar_sistema.html', context)

@login_required
def alertas_usuario(request):
    """
    Vista simplificada para alertas del usuario
    
    🎓 EDUCATIVO: Filtrar alertas según el rol del usuario
    para mostrar solo información relevante.
    """
    # Filtrar alertas según rol
    alertas = AlertaAutomatica.objects.filter(activa=True)
    
    if request.user.rol == 'coordinador_carrera':
        # Solo alertas de su carrera
        try:
            carrera = Carrera.objects.get(coordinador=request.user)
            alertas = alertas.filter(
                Q(deteccion_relacionada__estudiante__carrera=carrera) |
                Q(asignatura_relacionada__carrera=carrera) |
                Q(deteccion_relacionada__isnull=True, asignatura_relacionada__isnull=True)
            )
        except Carrera.DoesNotExist:
            alertas = alertas.none()
    
    alertas = alertas.order_by('-fecha_creacion')[:20]
    
    context = {
        'alertas': alertas,
        'total_alertas': alertas.count()
    }
    
    return render(request, 'anomalias/alertas.html', context)