# -*- coding: utf-8 -*-
"""
Vistas para el Sistema de Predicción de Deserción Estudiantil
============================================================

Vistas para:
- Visualizar predicciones de estudiantes
- Gestionar cohortes de riesgo
- Ver seguimientos temporales
- Buscar por cohorte
- Generar nuevas predicciones
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods

from prototipo.models import (
    Estudiante, PrediccionDesercion, SeguimientoEstudiante,
    CohorteEstudiantil, AlertaPrediccion
)
from prototipo.services.prediccion_service import servicio_prediccion
import logging

logger = logging.getLogger(__name__)


@login_required
def dashboard_predicciones(request):
    """
    Dashboard principal de predicciones de deserción.
    Muestra resumen de todas las cohortes y alertas activas.
    """
    # Obtener semestre actual (puedes ajustar esto según tu lógica)
    semestre_actual = request.GET.get('semestre', 3)
    try:
        semestre_actual = int(semestre_actual)
    except:
        semestre_actual = 3

    # Estadísticas generales
    total_estudiantes = Estudiante.objects.filter(activo=True).count()
    total_predicciones = PrediccionDesercion.objects.filter(
        semestre_academico=semestre_actual
    ).count()

    # Estadísticas por nivel de riesgo
    estadisticas_riesgo = PrediccionDesercion.objects.filter(
        semestre_academico=semestre_actual
    ).values('nivel_riesgo').annotate(
        total=Count('id')
    ).order_by('nivel_riesgo')

    # Convertir a diccionario
    stats_riesgo = {
        'critico': 0,
        'alto': 0,
        'medio': 0,
        'bajo': 0
    }
    for stat in estadisticas_riesgo:
        stats_riesgo[stat['nivel_riesgo']] = stat['total']

    # Estudiantes en riesgo crítico
    estudiantes_criticos = PrediccionDesercion.objects.filter(
        semestre_academico=semestre_actual,
        nivel_riesgo='critico'
    ).select_related('estudiante').order_by('-probabilidad_desercion')[:10]

    # Alertas activas
    alertas_activas = AlertaPrediccion.objects.filter(
        activa=True,
        prediccion__semestre_academico=semestre_actual
    ).select_related('prediccion__estudiante').order_by('-fecha_generacion')[:10]

    # Cohortes
    cohortes = CohorteEstudiantil.objects.filter(
        semestre_academico=semestre_actual
    ).order_by('numero_cohorte')

    # Si no existen cohortes, inicializarlas
    if not cohortes.exists():
        try:
            cohortes = servicio_prediccion.inicializar_cohortes(semestre_actual)
            messages.info(request, f'Cohortes inicializadas para el semestre {semestre_actual}')
        except Exception as e:
            logger.error(f"Error inicializando cohortes: {e}")
            messages.error(request, 'Error al inicializar cohortes')

    context = {
        'semestre_actual': semestre_actual,
        'total_estudiantes': total_estudiantes,
        'total_predicciones': total_predicciones,
        'stats_riesgo': stats_riesgo,
        'estudiantes_criticos': estudiantes_criticos,
        'alertas_activas': alertas_activas,
        'cohortes': cohortes,
        'porcentaje_predicciones': round((total_predicciones / total_estudiantes * 100), 1) if total_estudiantes > 0 else 0
    }

    return render(request, 'predicciones/dashboard.html', context)


@login_required
def ver_cohorte(request, numero_cohorte, semestre):
    """
    Muestra los estudiantes de una cohorte específica.
    """
    try:
        cohorte = get_object_or_404(
            CohorteEstudiantil,
            numero_cohorte=numero_cohorte,
            semestre_academico=semestre
        )

        # Obtener estudiantes de la cohorte
        predicciones = PrediccionDesercion.objects.filter(
            cohorte=numero_cohorte,
            semestre_academico=semestre
        ).select_related('estudiante', 'estudiante__carrera').order_by('-probabilidad_desercion')

        # Paginación
        paginator = Paginator(predicciones, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        # Filtros adicionales
        busqueda = request.GET.get('busqueda', '')
        if busqueda:
            page_obj = predicciones.filter(
                Q(estudiante__nombre__icontains=busqueda) |
                Q(estudiante__id_estudiante__icontains=busqueda)
            )

        context = {
            'cohorte': cohorte,
            'page_obj': page_obj,
            'predicciones': page_obj,
            'busqueda': busqueda,
            'semestre': semestre
        }

        return render(request, 'predicciones/ver_cohorte.html', context)

    except Exception as e:
        logger.error(f"Error en ver_cohorte: {e}")
        messages.error(request, f'Error al cargar la cohorte: {str(e)}')
        return redirect('dashboard_predicciones')


@login_required
def seguimiento_estudiante(request, estudiante_id):
    """
    Muestra el seguimiento temporal completo de un estudiante.
    """
    try:
        estudiante = get_object_or_404(Estudiante, id_estudiante=estudiante_id)

        # Obtener todas las predicciones del estudiante
        predicciones = PrediccionDesercion.objects.filter(
            estudiante=estudiante
        ).order_by('semestre_academico')

        # Obtener seguimiento
        try:
            seguimiento = SeguimientoEstudiante.objects.get(estudiante=estudiante)
        except SeguimientoEstudiante.DoesNotExist:
            seguimiento = None

        # Preparar datos para el gráfico
        semestres = []
        probabilidades = []
        cohortes_data = []

        for pred in predicciones:
            semestres.append(f"S{pred.semestre_academico}")
            probabilidades.append(pred.probabilidad_desercion * 100)
            cohortes_data.append({
                'semestre': pred.semestre_academico,
                'cohorte': pred.cohorte,
                'nivel_riesgo': pred.get_nivel_riesgo_display()
            })

        # Alertas del estudiante
        alertas = AlertaPrediccion.objects.filter(
            prediccion__estudiante=estudiante
        ).order_by('-fecha_generacion')[:5]

        context = {
            'estudiante': estudiante,
            'predicciones': predicciones,
            'seguimiento': seguimiento,
            'semestres_json': semestres,
            'probabilidades_json': probabilidades,
            'cohortes_data': cohortes_data,
            'alertas': alertas,
            'tiene_predicciones': predicciones.exists()
        }

        return render(request, 'predicciones/seguimiento_estudiante.html', context)

    except Exception as e:
        logger.error(f"Error en seguimiento_estudiante: {e}")
        messages.error(request, f'Error al cargar el seguimiento: {str(e)}')
        return redirect('dashboard_predicciones')


@login_required
def buscar_estudiantes(request):
    """
    Búsqueda avanzada de estudiantes por cohorte, nivel de riesgo, etc.
    """
    # Parámetros de búsqueda
    semestre = request.GET.get('semestre', 3)
    cohorte = request.GET.get('cohorte', '')
    nivel_riesgo = request.GET.get('nivel_riesgo', '')
    busqueda_texto = request.GET.get('busqueda', '')
    carrera_id = request.GET.get('carrera', '')

    try:
        semestre = int(semestre)
    except:
        semestre = 3

    # Query base
    predicciones = PrediccionDesercion.objects.filter(
        semestre_academico=semestre
    ).select_related('estudiante', 'estudiante__carrera')

    # Aplicar filtros
    if cohorte:
        predicciones = predicciones.filter(cohorte=int(cohorte))

    if nivel_riesgo:
        predicciones = predicciones.filter(nivel_riesgo=nivel_riesgo)

    if busqueda_texto:
        predicciones = predicciones.filter(
            Q(estudiante__nombre__icontains=busqueda_texto) |
            Q(estudiante__id_estudiante__icontains=busqueda_texto)
        )

    if carrera_id:
        predicciones = predicciones.filter(estudiante__carrera_id=carrera_id)

    # Ordenar
    orden = request.GET.get('orden', '-probabilidad_desercion')
    predicciones = predicciones.order_by(orden)

    # Paginación
    paginator = Paginator(predicciones, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Obtener opciones para filtros
    from prototipo.models import Carrera
    carreras = Carrera.objects.all()

    context = {
        'page_obj': page_obj,
        'predicciones': page_obj,
        'semestre': semestre,
        'cohorte_seleccionada': cohorte,
        'nivel_riesgo_seleccionado': nivel_riesgo,
        'busqueda': busqueda_texto,
        'carrera_seleccionada': carrera_id,
        'carreras': carreras,
        'total_resultados': predicciones.count()
    }

    return render(request, 'predicciones/buscar_estudiantes.html', context)


@login_required
@require_http_methods(["POST"])
def generar_prediccion(request, estudiante_id):
    """
    Genera una nueva predicción para un estudiante específico.
    """
    try:
        estudiante = get_object_or_404(Estudiante, id_estudiante=estudiante_id)
        semestre = int(request.POST.get('semestre', 3))

        # Generar predicción
        resultado = servicio_prediccion.predecir_estudiante(
            estudiante=estudiante,
            semestre_academico=semestre,
            guardar=True
        )

        messages.success(
            request,
            f'Predicción generada para {estudiante.nombre}: {resultado["prediccion"]} ({resultado["probabilidad_desercion"]:.1%})'
        )

        return redirect('seguimiento_estudiante', estudiante_id=estudiante_id)

    except Exception as e:
        logger.error(f"Error generando predicción: {e}")
        messages.error(request, f'Error al generar predicción: {str(e)}')
        return redirect('dashboard_predicciones')


@login_required
@require_http_methods(["POST"])
def generar_predicciones_masivas(request):
    """
    Genera predicciones para todos los estudiantes activos.
    """
    try:
        semestre = int(request.POST.get('semestre', 3))

        # Obtener todos los estudiantes activos
        estudiantes = Estudiante.objects.filter(activo=True)
        estudiantes_ids = list(estudiantes.values_list('id_estudiante', flat=True))

        if not estudiantes_ids:
            messages.warning(request, 'No hay estudiantes activos para generar predicciones')
            return redirect('dashboard_predicciones')

        # Generar predicciones
        resultados = servicio_prediccion.predecir_multiples_estudiantes(
            estudiantes_ids=estudiantes_ids,
            semestre_academico=semestre
        )

        # Actualizar cohortes
        servicio_prediccion.inicializar_cohortes(semestre)

        messages.success(
            request,
            f'Predicciones generadas: {resultados["exitosas"]} exitosas, {resultados["fallidas"]} fallidas'
        )

        if resultados['fallidas'] > 0:
            messages.warning(
                request,
                f'Hubo {resultados["fallidas"]} errores. Revisa los logs para más detalles.'
            )

        return redirect('dashboard_predicciones')

    except Exception as e:
        logger.error(f"Error en predicciones masivas: {e}")
        messages.error(request, f'Error al generar predicciones masivas: {str(e)}')
        return redirect('dashboard_predicciones')


# ===============================================================================
# API ENDPOINTS (JSON)
# ===============================================================================

@login_required
def api_obtener_cohorte(request, numero_cohorte, semestre):
    """
    API endpoint para obtener datos de una cohorte en formato JSON.
    """
    try:
        resultado = servicio_prediccion.obtener_cohorte(numero_cohorte, semestre)
        return JsonResponse(resultado, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_seguimiento_estudiante(request, estudiante_id):
    """
    API endpoint para obtener el seguimiento de un estudiante en formato JSON.
    """
    try:
        resultado = servicio_prediccion.obtener_seguimiento_estudiante(estudiante_id)
        return JsonResponse(resultado, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_estadisticas_cohortes(request):
    """
    API endpoint para obtener estadísticas de todas las cohortes.
    """
    try:
        semestre = int(request.GET.get('semestre', 3))

        cohortes = CohorteEstudiantil.objects.filter(
            semestre_academico=semestre
        ).order_by('numero_cohorte')

        datos = []
        for cohorte in cohortes:
            datos.append({
                'numero_cohorte': cohorte.numero_cohorte,
                'nombre': cohorte.nombre,
                'total_estudiantes': cohorte.total_estudiantes,
                'porcentaje_total': cohorte.porcentaje_total,
                'color': cohorte.color,
                'descripcion': cohorte.descripcion
            })

        return JsonResponse({
            'semestre': semestre,
            'cohortes': datos,
            'total_cohortes': len(datos)
        }, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_alertas_activas(request):
    """
    API endpoint para obtener alertas activas.
    """
    try:
        semestre = int(request.GET.get('semestre', 3))
        prioridad = request.GET.get('prioridad', '')

        alertas = AlertaPrediccion.objects.filter(
            activa=True,
            prediccion__semestre_academico=semestre
        ).select_related('prediccion__estudiante')

        if prioridad:
            alertas = alertas.filter(prioridad=prioridad)

        alertas = alertas.order_by('-fecha_generacion')[:50]

        datos = []
        for alerta in alertas:
            datos.append({
                'id': alerta.id,
                'tipo_alerta': alerta.get_tipo_alerta_display(),
                'prioridad': alerta.get_prioridad_display(),
                'titulo': alerta.titulo,
                'descripcion': alerta.descripcion,
                'accion_sugerida': alerta.accion_sugerida,
                'estudiante_id': alerta.prediccion.estudiante.id_estudiante,
                'estudiante_nombre': alerta.prediccion.estudiante.nombre,
                'fecha_generacion': alerta.fecha_generacion.isoformat()
            })

        return JsonResponse({
            'total_alertas': len(datos),
            'alertas': datos
        }, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
