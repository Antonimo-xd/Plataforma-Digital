# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Max, Min
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.urls import reverse  # ← AGREGAR ESTE
import json
import pandas as pd
import numpy as np
from datetime import timedelta
from io import StringIO
import traceback
import time
# Imports locales
from .models import *
from .forms import *
from .utils import ejecutar_deteccion_anomalias, generar_reporte_anomalias

# Decoradores de permisos
def es_analista_cpa(user):
    """Verifica si es analista CPA."""
    return user.rol == 'analista_cpa'

def es_coordinador_cpa(user):
    """Verifica si es coordinador CPA."""
    return user.rol == 'coordinador_cpa'

def es_coordinador_carrera(user):
    """Verifica si es coordinador de carrera."""
    return user.rol == 'coordinador_carrera'

def puede_ver_anomalias(user):
    """Verifica si el usuario puede ver anomalías."""
    return user.rol in ['analista_cpa', 'coordinador_cpa', 'coordinador_carrera']

# Vista principal del dashboard
@login_required
def dashboard(request):
    """Dashboard CORREGIDO con asignaturas críticas para todos los roles."""
    context = {}
    
    try:
        print(f"🏠 Dashboard cargando para usuario: {request.user.username} ({request.user.rol})")
        
        # Obtener datos base
        estudiantes = Estudiante.objects.filter(activo=True)
        anomalias = DeteccionAnomalia.objects.all()
        carrera = None
        
        # Filtrar por rol
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                estudiantes = estudiantes.filter(carrera=carrera)
                anomalias = anomalias.filter(estudiante__carrera=carrera)
                print(f"👨‍🎓 Filtrando por carrera: {carrera.nombre}")
            except Carrera.DoesNotExist:
                messages.warning(request, "Tu usuario no tiene carrera asignada.")
        
        # Calcular métricas FRESCAS
        total_estudiantes = estudiantes.count()
        total_anomalias = anomalias.count()
        
        # Anomalías activas (no resueltas)
        anomalias_activas = anomalias.filter(
            estado__in=['detectado', 'en_revision', 'intervencion_activa']
        ).count()
        
        # Casos críticos (prioridad alta)
        anomalias_criticas = anomalias.filter(
            prioridad__gte=4,
            estado__in=['detectado', 'en_revision', 'intervencion_activa']
        ).count()
        
        # Derivaciones pendientes
        derivaciones_pendientes = Derivacion.objects.filter(
            estado__in=['pendiente', 'enviada']
        )
        
        if request.user.rol == 'coordinador_carrera' and carrera:
            # Filtrar derivaciones por carrera
            derivaciones_pendientes = derivaciones_pendientes.filter(
                deteccion_anomalia__estudiante__carrera=carrera
            )
        
        derivaciones_pendientes_count = derivaciones_pendientes.count()
        
        # Tasa de anomalías
        tasa_anomalias = round((total_anomalias / total_estudiantes * 100), 2) if total_estudiantes > 0 else 0
        
        # Últimas detecciones (5 más recientes)
        ultimas_anomalias = anomalias.filter(
            estado='detectado'
        ).select_related('estudiante', 'criterio_usado').order_by('-fecha_deteccion')[:5]
        
        # CALCULAR ASIGNATURAS CRÍTICAS para todos los roles
        asignaturas_criticas = []
        
        try:
            if request.user.rol == 'coordinador_carrera' and carrera:
                # Para coordinadores de carrera: solo su carrera
                asignaturas_base = Asignatura.objects.filter(carrera=carrera)
                print(f"📚 Analizando {asignaturas_base.count()} asignaturas de {carrera.nombre}")
            elif request.user.rol in ['coordinador_cpa', 'analista_cpa']:
                # Para CPA: todas las carreras
                asignaturas_base = Asignatura.objects.all()
                print(f"📚 Analizando {asignaturas_base.count()} asignaturas totales")
            else:
                asignaturas_base = Asignatura.objects.none()
            
            for asignatura in asignaturas_base[:20]:  # Limitar para performance
                # Obtener estudiantes de esta asignatura
                registros = RegistroAcademico.objects.filter(
                    asignatura=asignatura,
                    estudiante__activo=True
                )
                
                if registros.exists():
                    # Estudiantes únicos en la asignatura
                    estudiantes_ids = list(registros.values_list('estudiante_id', flat=True).distinct())
                    total_estudiantes_asignatura = len(estudiantes_ids)
                    
                    if total_estudiantes_asignatura > 0:
                        # Contar anomalías activas para estos estudiantes
                        anomalias_asignatura = DeteccionAnomalia.objects.filter(
                            estudiante_id__in=estudiantes_ids,
                            estado__in=['detectado', 'en_revision', 'intervencion_activa']
                        ).count()
                        
                        # Calcular porcentaje
                        porcentaje_anomalias = round((anomalias_asignatura / total_estudiantes_asignatura) * 100, 2)
                        
                        print(f"   📊 {asignatura.nombre}: {anomalias_asignatura}/{total_estudiantes_asignatura} = {porcentaje_anomalias}%")
                        
                        # Solo incluir si es crítica (≥15% anomalías)
                        if porcentaje_anomalias >= 15.0:
                            asignaturas_criticas.append({
                                'asignatura': asignatura,
                                'porcentaje_anomalias': porcentaje_anomalias,
                                'total_estudiantes': total_estudiantes_asignatura,
                                'estudiantes_anomalos': anomalias_asignatura,
                                'nivel_criticidad': determinar_nivel_criticidad(porcentaje_anomalias)
                            })
            
            # Ordenar por porcentaje de anomalías (más críticas primero)
            asignaturas_criticas.sort(key=lambda x: x['porcentaje_anomalias'], reverse=True)
            
            # Limitar a top 10 para el dashboard
            asignaturas_criticas = asignaturas_criticas[:10]
            
            print(f"🚨 Total asignaturas críticas encontradas: {len(asignaturas_criticas)}")
            
        except Exception as e:
            print(f"⚠️ Error calculando asignaturas críticas: {e}")
            import traceback
            traceback.print_exc()
            asignaturas_criticas = []
        
        # Preparar contexto
        context.update({
            'total_estudiantes': total_estudiantes,
            'total_anomalias': total_anomalias,
            'anomalias_activas': anomalias_activas,
            'anomalias_criticas': anomalias_criticas,
            'derivaciones_pendientes': derivaciones_pendientes_count,
            'tasa_anomalias': tasa_anomalias,
            'ultimas_anomalias': ultimas_anomalias,
            'asignaturas_criticas': asignaturas_criticas,  # CLAVE: Agregar al contexto
            'ultima_actualizacion': timezone.now(),
            'carrera': carrera,
            'usuario_rol': request.user.rol
        })
        
        print(f"📊 Dashboard cargado:")
        print(f"   Total estudiantes: {total_estudiantes}")
        print(f"   Total anomalías: {total_anomalias}")
        print(f"   Anomalías activas: {anomalias_activas}")
        print(f"   Casos críticos: {anomalias_criticas}")
        print(f"   Asignaturas críticas: {len(asignaturas_criticas)}")
        
    except Exception as e:
        print(f"❌ Error en dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Error cargando dashboard: {str(e)}')
        
        # Valores por defecto en caso de error
        context.update({
            'total_estudiantes': 0,
            'total_anomalias': 0,
            'anomalias_activas': 0,
            'anomalias_criticas': 0,
            'derivaciones_pendientes': 0,
            'ultimas_anomalias': [],
            'asignaturas_criticas': [],
            'error': True
        })
    
    return render(request, 'anomalias/dashboard.html', context)

# Historia de Usuario 1: Listado de estudiantes con comportamiento anómalo
class ListadoAnomaliasView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vista mejorada para listado de anomalías con paginación dinámica."""
    model = DeteccionAnomalia
    template_name = 'anomalias/listado_anomalias.html'
    context_object_name = 'anomalias'
    paginate_by = 20  # Valor por defecto
    
    def test_func(self):
        return self.request.user.rol in ['analista_cpa', 'coordinador_cpa', 'coordinador_carrera']
    
    def get_paginate_by(self, queryset):
        """
        Permite cambiar el número de elementos por página dinámicamente.
        """
        per_page = self.request.GET.get('per_page', '20')
        try:
            per_page = int(per_page)
            # Limitar entre 10 y 100 elementos por página
            if 10 <= per_page <= 100:
                return per_page
        except (ValueError, TypeError):
            pass
        return self.paginate_by
    
    def get_queryset(self):
        """Queryset con filtros mejorados y debug."""
        print(f"\n📊 ListadoAnomaliasView - Usuario: {self.request.user.username} ({self.request.user.rol})")
        
        # Queryset base
        queryset = DeteccionAnomalia.objects.select_related(
            'estudiante', 'estudiante__carrera', 'criterio_usado', 'revisado_por'
        ).order_by('-fecha_deteccion')
        
        # Filtrar por rol del usuario
        if self.request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=self.request.user)
                queryset = queryset.filter(estudiante__carrera=carrera)
                print(f"👨‍🎓 Filtrando por carrera: {carrera.nombre}")
            except Carrera.DoesNotExist:
                print("❌ Coordinador sin carrera asignada")
                queryset = queryset.none()
        
        # APLICAR FILTROS DE BÚSQUEDA
        
        # 1. Filtro por estado
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
            print(f"🔍 Filtro estado: {estado}")
        
        # 2. Filtro por tipo de anomalía
        tipo = self.request.GET.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo_anomalia=tipo)
            print(f"🔍 Filtro tipo: {tipo}")
        
        # 3. Filtro por prioridad
        prioridad = self.request.GET.get('prioridad')
        if prioridad:
            try:
                prioridad_int = int(prioridad)
                queryset = queryset.filter(prioridad=prioridad_int)
                print(f"🔍 Filtro prioridad: {prioridad_int}")
            except ValueError:
                pass
        
        # 4. Filtro por carrera (para coordinadores CPA)
        carrera_filtro = self.request.GET.get('carrera')
        if carrera_filtro and self.request.user.rol in ['coordinador_cpa', 'analista_cpa']:
            try:
                carrera_obj = Carrera.objects.get(id=carrera_filtro)
                queryset = queryset.filter(estudiante__carrera=carrera_obj)
                print(f"🔍 Filtro carrera: {carrera_obj.nombre}")
            except Carrera.DoesNotExist:
                pass
        
        # 5. Filtro por rango de fechas
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')
        
        if fecha_desde:
            try:
                from datetime import datetime
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_deteccion__date__gte=fecha_desde_obj)
                print(f"🔍 Filtro fecha desde: {fecha_desde}")
            except ValueError:
                print(f"❌ Fecha desde inválida: {fecha_desde}")
        
        if fecha_hasta:
            try:
                from datetime import datetime
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_deteccion__date__lte=fecha_hasta_obj)
                print(f"🔍 Filtro fecha hasta: {fecha_hasta}")
            except ValueError:
                print(f"❌ Fecha hasta inválida: {fecha_hasta}")
        
        # 6. Filtro por nombre de estudiante
        buscar = self.request.GET.get('buscar')
        if buscar:
            queryset = queryset.filter(
                Q(estudiante__nombre__icontains=buscar) |
                Q(estudiante__id_estudiante__icontains=buscar)
            )
            print(f"🔍 Búsqueda: {buscar}")
        
        # 7. Ordenamiento
        orden = self.request.GET.get('orden', '-fecha_deteccion')
        if orden in ['-fecha_deteccion', 'fecha_deteccion', '-score_anomalia', 'score_anomalia', 
                     'estudiante__nombre', '-estudiante__nombre', '-prioridad', 'prioridad']:
            queryset = queryset.order_by(orden)
            print(f"📋 Ordenamiento: {orden}")
        
        print(f"📊 Total anomalías después de filtros: {queryset.count()}")
        return queryset
    
    def get_context_data(self, **kwargs):
        """Añadir datos adicionales al contexto."""
        context = super().get_context_data(**kwargs)
        
        # Obtener parámetros actuales para mantener filtros en paginación
        filtros_actuales = {
            'estado': self.request.GET.get('estado', ''),
            'tipo': self.request.GET.get('tipo', ''),
            'prioridad': self.request.GET.get('prioridad', ''),
            'carrera': self.request.GET.get('carrera', ''),
            'fecha_desde': self.request.GET.get('fecha_desde', ''),
            'fecha_hasta': self.request.GET.get('fecha_hasta', ''),
            'buscar': self.request.GET.get('buscar', ''),
            'orden': self.request.GET.get('orden', '-fecha_deteccion'),
            'per_page': self.request.GET.get('per_page', '20')
        }
        
        # Opciones para los filtros
        estados_choices = DeteccionAnomalia.ESTADOS
        tipos_choices = DeteccionAnomalia.TIPOS_ANOMALIA
        
        # Carreras disponibles (solo para coordinadores CPA)
        carreras_disponibles = []
        if self.request.user.rol in ['coordinador_cpa', 'analista_cpa']:
            carreras_disponibles = Carrera.objects.all().order_by('nombre')
        
        # Estadísticas rápidas
        total_anomalias = self.get_queryset().count()
        
        # Agregar al contexto
        context.update({
            'filtros_actuales': filtros_actuales,
            'estados_choices': estados_choices,
            'tipos_choices': tipos_choices,
            'carreras_disponibles': carreras_disponibles,
            'total_anomalias': total_anomalias,
            'usuario_rol': self.request.user.rol,
            'request': self.request,  # Para usar en templates
        })
        
        print(f"📋 Context data preparado - Total anomalías: {total_anomalias}")
        return context

@login_required
@user_passes_test(puede_ver_anomalias)
def detalle_anomalia(request, pk):
    """Vista mejorada para detalle de anomalía."""
    anomalia = get_object_or_404(DeteccionAnomalia, pk=pk)
    
    # Verificar permisos por rol
    if request.user.rol == 'coordinador_carrera':
        try:
            carrera = Carrera.objects.get(coordinador=request.user)
            if anomalia.estudiante.carrera != carrera:
                messages.error(request, "No tienes permisos para ver esta anomalía.")
                return redirect('listado_anomalias')
        except Carrera.DoesNotExist:
            messages.error(request, "Tu usuario no tiene carrera asignada.")
            return redirect('listado_anomalias')
    
    # Datos del estudiante
    registros_estudiante = RegistroAcademico.objects.filter(
        estudiante=anomalia.estudiante
    ).select_related('asignatura').order_by('asignatura__semestre', 'asignatura__nombre')
    
    # Historial de derivaciones
    derivaciones = Derivacion.objects.filter(
        deteccion_anomalia=anomalia
    ).select_related('instancia_apoyo', 'derivado_por').order_by('-fecha_derivacion')
    
    # Preparar datos para gráfico de evolución
    evolucion_datos = []
    for registro in registros_estudiante:
        evolucion_datos.append({
            'asignatura': registro.asignatura.nombre,
            'semestre': registro.asignatura.semestre,
            'promedio': float(registro.promedio_notas),
            'asistencia': float(registro.porcentaje_asistencia),
            'uso_plataforma': float(registro.porcentaje_uso_plataforma)
        })
    
    # Estados disponibles para el modal
    estados = DeteccionAnomalia.ESTADOS
    
    context = {
        'anomalia': anomalia,
        'registros_estudiante': registros_estudiante,
        'derivaciones': derivaciones,
        'evolucion_datos': json.dumps(evolucion_datos),
        'estados': estados,
        'instancias_apoyo': InstanciaApoyo.objects.filter(activo=True),
    }
    
    return render(request, 'anomalias/detalle_anomalia.html', context)

# También actualizar la vista crear_criterio
@login_required
@user_passes_test(lambda u: u.rol == 'coordinador_cpa')
def crear_criterio(request):
    """Vista para crear criterio."""
    try:
        if request.method == 'POST':
            form = CriterioAnomaliaForm(request.POST)
            if form.is_valid():
                criterio = form.save(commit=False)
                criterio.creado_por = request.user
                criterio.save()
                messages.success(request, 'Criterio creado exitosamente.')
                return redirect('configuracion_criterios')
            else:
                # Mostrar errores del formulario
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        else:
            form = CriterioAnomaliaForm()
        
        return render(request, 'anomalias/crear_criterio.html', {'form': form})
    
    except Exception as e:
        print(f"Error en crear_criterio: {e}")
        messages.error(request, f'Error al crear criterio: {str(e)}')
        return redirect('configuracion_criterios')

@login_required
@user_passes_test(lambda u: u.rol == 'coordinador_cpa')
def ejecutar_analisis(request, criterio_id):
    """Vista para ejecutar análisis con debugging."""
    criterio = get_object_or_404(CriterioAnomalia, id=criterio_id)
    
    if request.method == 'POST':
        try:
            print(f"🚀 Ejecutando análisis para: {criterio.nombre}")
            
            # Contar anomalías ANTES
            anomalias_antes = DeteccionAnomalia.objects.count()
            anomalias_criterio_antes = DeteccionAnomalia.objects.filter(criterio_usado=criterio).count()
            
            print(f"📊 ANTES - Total: {anomalias_antes}, Criterio: {anomalias_criterio_antes}")
            
            # Ejecutar análisis
            from .utils import ejecutar_deteccion_anomalias
            resultado = ejecutar_deteccion_anomalias(criterio, request.user)
            
            # Contar anomalías DESPUÉS
            anomalias_despues = DeteccionAnomalia.objects.count()
            anomalias_criterio_despues = DeteccionAnomalia.objects.filter(criterio_usado=criterio).count()
            
            print(f"📈 DESPUÉS - Total: {anomalias_despues}, Criterio: {anomalias_criterio_despues}")
            
            if resultado['exitoso']:
                nuevas = resultado.get('anomalias_detectadas', 0)
                total_estudiantes = resultado.get('total_estudiantes', 0)
                tiempo = resultado.get('tiempo_ejecucion', 0)
                
                # Mensaje detallado
                mensaje_principal = f'✅ Análisis completado exitosamente!'
                mensaje_detalle = f'📊 Resultados: {nuevas} nuevas anomalías de {total_estudiantes} estudiantes analizados'
                mensaje_bd = f'🗄️ Total en base de datos: {anomalias_despues} anomalías'
                mensaje_tiempo = f'⏱️ Tiempo de ejecución: {tiempo:.2f} segundos'
                
                messages.success(request, mensaje_principal)
                messages.info(request, mensaje_detalle)
                messages.info(request, mensaje_bd)
                messages.info(request, mensaje_tiempo)
                
                # Si no hay nuevas anomalías pero sí total, explicar
                if nuevas == 0 and anomalias_despues > 0:
                    messages.warning(
                        request, 
                        '⚠️ No se crearon nuevas anomalías porque ya existen detecciones recientes. '
                        'Las anomalías existentes pueden haber sido actualizadas.'
                    )
                
                print(f"✅ Análisis exitoso: {nuevas} nuevas anomalías")
                
            else:
                error_msg = resultado.get('error', 'Error desconocido')
                messages.error(request, f'❌ Error en el análisis: {error_msg}')
                print(f"❌ Error: {error_msg}")
            
        except Exception as e:
            print(f"💥 Excepción: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'💥 Error crítico: {str(e)}')
    
    return redirect('configuracion_criterios')

# Historia de Usuario 3: Registrar y derivar estudiantes
@login_required
@user_passes_test(lambda u: u.rol in ['analista_cpa', 'coordinador_cpa'])
def crear_derivacion(request, anomalia_id):
    """Vista para crear derivación."""
    anomalia = get_object_or_404(DeteccionAnomalia, id=anomalia_id)
    
    if request.method == 'POST':
        form = DerivacionForm(request.POST)
        if form.is_valid():
            derivacion = form.save(commit=False)
            derivacion.deteccion_anomalia = anomalia
            derivacion.derivado_por = request.user
            derivacion.save()
            
            # Actualizar estado de la anomalía
            anomalia.estado = 'intervencion_activa'
            anomalia.save()
            
            messages.success(
                request, 
                f'Derivación creada exitosamente hacia {derivacion.instancia_apoyo.nombre}'
            )
            return redirect('detalle_anomalia', pk=anomalia_id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = DerivacionForm()
    
    context = {
        'form': form,
        'anomalia': anomalia,
        'instancias_apoyo': InstanciaApoyo.objects.filter(activo=True)
    }
    
    return render(request, 'anomalias/crear_derivacion.html', context)

@login_required
@user_passes_test(lambda u: u.rol in ['analista_cpa', 'coordinador_cpa'])
def gestionar_derivaciones(request):
    """Vista mejorada para gestionar derivaciones."""
    # Queryset base
    derivaciones = Derivacion.objects.select_related(
        'deteccion_anomalia__estudiante',
        'deteccion_anomalia__estudiante__carrera',
        'instancia_apoyo',
        'derivado_por'
    ).order_by('-fecha_derivacion')
    
    # Aplicar filtros
    estado = request.GET.get('estado')
    if estado:
        derivaciones = derivaciones.filter(estado=estado)
    
    instancia = request.GET.get('instancia')
    if instancia:
        derivaciones = derivaciones.filter(instancia_apoyo_id=instancia)
    
    fecha_desde = request.GET.get('fecha_desde')
    if fecha_desde:
        derivaciones = derivaciones.filter(fecha_derivacion__date__gte=fecha_desde)
    
    busqueda = request.GET.get('busqueda')
    if busqueda:
        derivaciones = derivaciones.filter(
            Q(deteccion_anomalia__estudiante__nombre__icontains=busqueda) |
            Q(deteccion_anomalia__estudiante__id_estudiante__icontains=busqueda)
        )
    
    # Estadísticas rápidas
    total_derivaciones = derivaciones.count()
    derivaciones_pendientes = derivaciones.filter(estado='pendiente').count()
    derivaciones_proceso = derivaciones.filter(estado='en_proceso').count()
    derivaciones_completadas = derivaciones.filter(estado='completada').count()
    
    # Paginación
    paginator = Paginator(derivaciones, 15)
    page = request.GET.get('page')
    derivaciones_paginadas = paginator.get_page(page)
    
    context = {
        'derivaciones': derivaciones_paginadas,
        'derivaciones_pendientes': derivaciones_pendientes,
        'derivaciones_proceso': derivaciones_proceso,
        'derivaciones_completadas': derivaciones_completadas,
        'total_derivaciones': total_derivaciones,
        'estados_derivacion': Derivacion.ESTADOS_DERIVACION,
        'instancias_apoyo': InstanciaApoyo.objects.filter(activo=True),
    }
    
    return render(request, 'anomalias/gestionar_derivaciones.html', context)

# Historia de Usuario 4: Alertas automáticas
@login_required
def alertas_usuario(request):
    """Vista para mostrar alertas del usuario - VERSIÓN ACTIVADA"""
    try:
        alertas = []
        
        # 1. Anomalías críticas recientes
        anomalias_criticas = DeteccionAnomalia.objects.filter(
            prioridad__gte=4,
            estado='detectado',
            fecha_deteccion__gte=timezone.now() - timedelta(hours=24)
        ).select_related('estudiante', 'estudiante__carrera')
        
        # Filtrar por rol
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                anomalias_criticas = anomalias_criticas.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                pass
        
        for anomalia in anomalias_criticas:
            alertas.append({
                'tipo': 'anomalia_critica',
                'titulo': f'Anomalía Crítica: {anomalia.estudiante.nombre}',
                'mensaje': f'Score: {anomalia.score_anomalia:.1f} - {anomalia.get_tipo_anomalia_display()}',
                'fecha': anomalia.fecha_deteccion,
                'url': f'/cpa/anomalias/{anomalia.id}/',
                'icono': 'fas fa-exclamation-triangle',
                'color': 'danger'
            })
        
        # 2. Derivaciones pendientes (solo para analistas)
        if request.user.rol in ['analista_cpa', 'coordinador_cpa']:
            derivaciones_pendientes = Derivacion.objects.filter(
                estado='pendiente',
                fecha_derivacion__gte=timezone.now() - timedelta(hours=48)
            ).select_related('deteccion_anomalia__estudiante', 'instancia_apoyo')
            
            for derivacion in derivaciones_pendientes:
                alertas.append({
                    'tipo': 'derivacion_pendiente',
                    'titulo': f'Derivación Pendiente: {derivacion.deteccion_anomalia.estudiante.nombre}',
                    'mensaje': f'Pendiente desde: {derivacion.fecha_derivacion.strftime("%d/%m/%Y %H:%M")}',
                    'fecha': derivacion.fecha_derivacion,
                    'url': f'/cpa/derivaciones/',
                    'icono': 'fas fa-clock',
                    'color': 'warning'
                })
        
        # 3. Asignaturas críticas (para coordinadores de carrera)
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                asignaturas_problematicas = []
                
                for asignatura in carrera.asignatura_set.all():
                    anomalias_asignatura = DeteccionAnomalia.objects.filter(
                        estudiante__registroacademico__asignatura=asignatura,
                        fecha_deteccion__gte=timezone.now() - timedelta(days=7)
                    ).count()
                    
                    estudiantes_asignatura = asignatura.registroacademico_set.values('estudiante').distinct().count()
                    
                    if estudiantes_asignatura > 0:
                        porcentaje_anomalias = (anomalias_asignatura / estudiantes_asignatura) * 100
                        if porcentaje_anomalias > 30:  # Más del 30% con anomalías
                            asignaturas_problematicas.append({
                                'asignatura': asignatura,
                                'porcentaje': porcentaje_anomalias
                            })
                
                for item in asignaturas_problematicas:
                    alertas.append({
                        'tipo': 'asignatura_critica',
                        'titulo': f'Asignatura Crítica: {item["asignatura"].nombre}',
                        'mensaje': f'{item["porcentaje"]:.1f}% de estudiantes con anomalías',
                        'fecha': timezone.now(),
                        'url': f'/cpa/asignaturas-criticas/',
                        'icono': 'fas fa-book',
                        'color': 'info'
                    })
                    
            except Carrera.DoesNotExist:
                pass
        
        # Ordenar alertas por fecha (más recientes primero)
        alertas.sort(key=lambda x: x['fecha'], reverse=True)
        
        context = {
            'alertas': alertas,
            'total_alertas': len(alertas),
            'mensaje_info': None if alertas else 'No hay alertas pendientes en este momento.'
        }
        
        return render(request, 'anomalias/alertas.html', context)
        
    except Exception as e:
        print(f"Error en alertas_usuario: {e}")
        context = {
            'alertas': [],
            'total_alertas': 0,
            'error_message': 'No se pudieron cargar las alertas en este momento.'
        }
        return render(request, 'anomalias/alertas.html', context)

# Historia de Usuario 5: Detectar asignaturas críticas
@login_required
def asignaturas_criticas(request):
    """
    Vista FINAL para asignaturas críticas - FUNCIONA según el debug
    """
    try:
        print(f"\n🏫 === ASIGNATURAS CRÍTICAS FINAL ===")
        print(f"Usuario: {request.user.username} ({request.user.rol})")
        
        carrera = None
        asignaturas_query = Asignatura.objects.all()
        
        # Filtrar según el rol del usuario
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                asignaturas_query = asignaturas_query.filter(carrera=carrera)
                print(f"👨‍🎓 Coordinador de carrera - Filtrando por: {carrera.nombre}")
            except Carrera.DoesNotExist:
                messages.error(request, "Tu usuario no tiene una carrera asignada.")
                return redirect('dashboard')
        
        elif request.user.rol in ['coordinador_cpa', 'analista_cpa']:
            print(f"👑 {request.user.rol} - Acceso a todas las carreras")
            carrera = None
        
        else:
            messages.error(request, "No tienes permisos para acceder a esta sección.")
            return redirect('dashboard')
        
        # Obtener asignaturas
        asignaturas = asignaturas_query.select_related('carrera')
        print(f"📚 Total asignaturas encontradas: {asignaturas.count()}")
        
        if not asignaturas.exists():
            print("⚠️ No hay asignaturas en el sistema")
            messages.warning(request, "No hay asignaturas registradas en el sistema.")
            
            return render(request, 'anomalias/asignaturas_criticas.html', {
                'asignaturas_criticas': [],
                'total_asignaturas': 0,
                'total_criticas': 0,
                'promedio_anomalias_carrera': 0,
                'carrera': carrera,
                'umbral_criticidad': 15.0,
                'mostrar_todas_carreras': request.user.rol in ['coordinador_cpa', 'analista_cpa'],
                'debug_info': 'No hay asignaturas disponibles'
            })
        
        # Analizar cada asignatura
        asignaturas_criticas = []
        total_asignaturas = 0
        suma_porcentajes = 0
        
        print(f"\n🔍 Analizando asignaturas...")
        
        for asignatura in asignaturas:
            print(f"\n📖 Procesando: {asignatura.nombre}")
            
            # Obtener registros académicos para esta asignatura
            registros = RegistroAcademico.objects.filter(
                asignatura=asignatura,
                estudiante__activo=True
            )
            
            if not registros.exists():
                print(f"   ⚠️ Sin registros para {asignatura.nombre}")
                continue
            
            # Obtener estudiantes únicos
            estudiantes_ids = list(registros.values_list('estudiante_id', flat=True).distinct())
            total_estudiantes_asignatura = len(estudiantes_ids)
            
            print(f"   👥 Estudiantes únicos: {total_estudiantes_asignatura}")
            
            if total_estudiantes_asignatura == 0:
                continue
            
            # Buscar anomalías ACTIVAS para estos estudiantes
            anomalias_estudiantes = DeteccionAnomalia.objects.filter(
                estudiante_id__in=estudiantes_ids,
                estado__in=['detectado', 'en_revision', 'intervencion_activa']
            )
            
            anomalias_count = anomalias_estudiantes.count()
            print(f"   ⚠️ Anomalías activas: {anomalias_count}")
            
            # Calcular porcentaje
            porcentaje_anomalias = (anomalias_count / total_estudiantes_asignatura) * 100
            print(f"   📊 Porcentaje de anomalías: {porcentaje_anomalias:.2f}%")
            
            # Determinar nivel de criticidad
            nivel_criticidad = determinar_nivel_criticidad(porcentaje_anomalias)
            
            # Agregar a la lista si es crítica (≥15% de anomalías)
            if porcentaje_anomalias >= 15.0:
                print(f"   🔴 CRÍTICA: {asignatura.nombre} - {porcentaje_anomalias:.2f}%")
                
                asignaturas_criticas.append({
                    'asignatura': asignatura,
                    'total_estudiantes': total_estudiantes_asignatura,
                    'total_anomalias': anomalias_count,
                    'porcentaje_anomalias': round(porcentaje_anomalias, 2),
                    'nivel_criticidad': nivel_criticidad,
                    'carrera_nombre': asignatura.carrera.nombre if asignatura.carrera else 'Sin carrera'
                })
            else:
                print(f"   ✅ Normal: {asignatura.nombre} - {porcentaje_anomalias:.2f}%")
            
            total_asignaturas += 1
            suma_porcentajes += porcentaje_anomalias
        
        # Ordenar por porcentaje de anomalías (de mayor a menor)
        asignaturas_criticas.sort(key=lambda x: x['porcentaje_anomalias'], reverse=True)
        
        # Calcular promedio
        promedio_anomalias_carrera = suma_porcentajes / total_asignaturas if total_asignaturas > 0 else 0
        
        print(f"\n📊 === RESULTADOS FINALES ===")
        print(f"   Total asignaturas analizadas: {total_asignaturas}")
        print(f"   Asignaturas críticas encontradas: {len(asignaturas_criticas)}")
        print(f"   Promedio de anomalías: {promedio_anomalias_carrera:.2f}%")
        
        if len(asignaturas_criticas) > 0:
            print(f"   🔴 ¡Se encontraron {len(asignaturas_criticas)} asignaturas críticas!")
            for critica in asignaturas_criticas[:5]:  # Mostrar solo las primeras 5
                print(f"      - {critica['asignatura'].nombre}: {critica['porcentaje_anomalias']}%")
        
        context = {
            'asignaturas_criticas': asignaturas_criticas,
            'total_asignaturas': total_asignaturas,
            'total_criticas': len(asignaturas_criticas),
            'promedio_anomalias_carrera': round(promedio_anomalias_carrera, 2),
            'carrera': carrera,
            'umbral_criticidad': 15.0,
            'mostrar_todas_carreras': request.user.rol in ['coordinador_cpa', 'analista_cpa'],
            'usuario_rol': request.user.rol,
            'debug_info': f"Analizadas {total_asignaturas} asignaturas - {len(asignaturas_criticas)} críticas encontradas"
        }
        
        return render(request, 'anomalias/asignaturas_criticas.html', context)
        
    except Exception as e:
        print(f"❌ Error en asignaturas_criticas: {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Error analizando asignaturas críticas: {str(e)}')
        return render(request, 'anomalias/asignaturas_criticas.html', {
            'asignaturas_criticas': [],
            'total_asignaturas': 0,
            'total_criticas': 0,
            'promedio_anomalias_carrera': 0,
            'carrera': None,
            'umbral_criticidad': 15.0,
            'error': True,
            'error_message': str(e)
        })


# También asegúrate de que esta función exista:
def determinar_nivel_criticidad(porcentaje):
    """
    🚨 Determina el nivel de criticidad basado en el porcentaje de anomalías
    """
    if porcentaje >= 30:
        return 'muy_alta'
    elif porcentaje >= 20:
        return 'alta'
    elif porcentaje >= 15:
        return 'media'
    elif porcentaje >= 10:
        return 'baja'
    else:
        return 'normal'

def determinar_nivel_criticidad(porcentaje):
    """
    🚨 Determina el nivel de criticidad basado en el porcentaje de anomalías
    """
    if porcentaje >= 30:
        return 'muy_alta'
    elif porcentaje >= 20:
        return 'alta'
    elif porcentaje >= 15:
        return 'media'
    elif porcentaje >= 10:
        return 'baja'
    else:
        return 'normal'

@login_required
def api_estudiante_detalle(request, estudiante_id):
    """API para obtener datos detallados de un estudiante"""
    try:
        estudiante = get_object_or_404(Estudiante, id_estudiante=estudiante_id)
        
        # Verificar permisos
        if request.user.rol == 'coordinador_carrera':
            carrera = Carrera.objects.get(coordinador=request.user)
            if estudiante.carrera != carrera:
                return JsonResponse({'error': 'Sin permisos'}, status=403)
        
        registros = RegistroAcademico.objects.filter(estudiante=estudiante).select_related('asignatura')
        
        # Datos por semestre
        datos_semestre = {}
        for registro in registros:
            semestre = registro.asignatura.semestre
            if semestre not in datos_semestre:
                datos_semestre[semestre] = {
                    'promedios': [],
                    'asistencias': [],
                    'uso_plataforma': []
                }
            
            datos_semestre[semestre]['promedios'].append(registro.promedio_notas)
            datos_semestre[semestre]['asistencias'].append(registro.porcentaje_asistencia)
            datos_semestre[semestre]['uso_plataforma'].append(registro.porcentaje_uso_plataforma)
        
        # Calcular promedios por semestre
        datos_graficos = {
            'semestres': [],
            'promedio_notas': [],
            'promedio_asistencia': [],
            'promedio_plataforma': []
        }
        
        for semestre in sorted(datos_semestre.keys()):
            datos = datos_semestre[semestre]
            datos_graficos['semestres'].append(f"Semestre {semestre}")
            datos_graficos['promedio_notas'].append(round(sum(datos['promedios']) / len(datos['promedios']), 2))
            datos_graficos['promedio_asistencia'].append(round(sum(datos['asistencias']) / len(datos['asistencias']), 2))
            datos_graficos['promedio_plataforma'].append(round(sum(datos['uso_plataforma']) / len(datos['uso_plataforma']), 2))
        
        return JsonResponse(datos_graficos)
    except Exception as e:
        return JsonResponse({'error': str(e)})

# Función auxiliar para crear alertas automáticas
def crear_alertas_automaticas(nuevas_anomalias):
    """Crear alertas automáticas para nuevas anomalías detectadas"""
    
    analistas = Usuario.objects.filter(rol='analista_cpa')
    
    for anomalia in nuevas_anomalias:
        # Alerta para anomalías críticas (prioridad 4 o 5)
        if anomalia.prioridad >= 4:
            alerta = AlertaAutomatica.objects.create(
                tipo='anomalia_critica',
                titulo=f'Anomalía Crítica Detectada: {anomalia.estudiante.nombre}',
                mensaje=f'Se ha detectado una anomalía crítica en el estudiante {anomalia.estudiante.nombre} '
                        f'({anomalia.get_tipo_anomalia_display()}). Score: {anomalia.score_anomalia:.3f}. '
                        f'Requiere atención inmediata.',
                deteccion_relacionada=anomalia
            )
            alerta.destinatarios.set(analistas)
        
        # Alerta general para nuevas anomalías
        else:
            alerta = AlertaAutomatica.objects.create(
                tipo='nueva_anomalia',
                titulo=f'Nueva Anomalía: {anomalia.estudiante.nombre}',
                mensaje=f'Se ha detectado una nueva anomalía en el estudiante {anomalia.estudiante.nombre} '
                        f'({anomalia.get_tipo_anomalia_display()}). Score: {anomalia.score_anomalia:.3f}.',
                deteccion_relacionada=anomalia
            )
            alerta.destinatarios.set(analistas)

def enviar_notificacion_derivacion(derivacion):
    """Enviar notificación por email de una nueva derivación"""
    
    asunto = f'Nueva Derivación - {derivacion.deteccion_anomalia.estudiante.nombre}'
    mensaje = f"""
    Se ha creado una nueva derivación:
    
    Estudiante: {derivacion.deteccion_anomalia.estudiante.nombre}
    Tipo de Anomalía: {derivacion.deteccion_anomalia.get_tipo_anomalia_display()}
    Instancia de Apoyo: {derivacion.instancia_apoyo.nombre}
    Derivado por: {derivacion.derivado_por.get_full_name()}
    
    Motivo: {derivacion.motivo}
    
    Por favor, contactar con el estudiante a la brevedad.
    """
    
    try:
        send_mail(
            asunto,
            mensaje,
            settings.EMAIL_HOST_USER,
            [derivacion.instancia_apoyo.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"Error enviando email: {e}")

# Reportes y exportación
# 🔧 SOLUCIÓN: Corregir views.py en la función exportar_reporte_anomalias

@login_required
@user_passes_test(lambda u: u.rol in ['coordinador_cpa', 'analista_cpa', 'coordinador_carrera'])
def exportar_reporte_anomalias(request):
    """
    🔧 FUNCIÓN CORREGIDA: Exportar reporte de anomalías
    """
    try:
        print(f"📤 Iniciando exportación de reportes para {request.user.username}")
        
        # Obtener anomalías con relaciones necesarias
        anomalias = DeteccionAnomalia.objects.select_related(
            'estudiante', 
            'estudiante__carrera', 
            'criterio_usado', 
            'revisado_por'
        ).order_by('-fecha_deteccion')
        
        # Filtrar por rol del usuario
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                anomalias = anomalias.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                messages.error(request, "Usuario sin carrera asignada.")
                return redirect('listado_anomalias')
        
        if not anomalias.exists():
            messages.warning(request, "No hay anomalías para exportar.")
            return redirect('listado_anomalias')
        
        print(f"📋 Exportando {anomalias.count()} anomalías")
        
        # Preparar datos para Excel
        data = []
        for anomalia in anomalias:
            try:
                # 🔧 CORRECCIÓN PRINCIPAL: Usar ingreso_año en lugar de ingreso_ano
                año_ingreso = getattr(anomalia.estudiante, 'ingreso_año', 'N/A')
                
                data.append({
                    'ID Anomalía': anomalia.id,
                    'ID Estudiante': anomalia.estudiante.id_estudiante,
                    'Nombre Estudiante': anomalia.estudiante.nombre,
                    'Carrera': anomalia.estudiante.carrera.nombre if anomalia.estudiante.carrera else 'N/A',
                    'Año Ingreso': año_ingreso,  # 🔧 CORREGIDO: ingreso_año
                    'Tipo Anomalía': anomalia.get_tipo_anomalia_display(),
                    'Score Anomalía': round(anomalia.score_anomalia, 2),
                    'Confianza': round(anomalia.confianza, 3),
                    'Estado': anomalia.get_estado_display(),
                    'Prioridad': anomalia.prioridad,
                    'Promedio General': round(anomalia.promedio_general, 2),
                    'Asistencia Promedio (%)': round(anomalia.asistencia_promedio, 1),
                    'Uso Plataforma (%)': round(anomalia.uso_plataforma_promedio, 1),
                    'Variación Notas': round(anomalia.variacion_notas, 2),
                    'Fecha Detección': anomalia.fecha_deteccion.strftime('%Y-%m-%d %H:%M:%S'),
                    'Criterio Usado': anomalia.criterio_usado.nombre if anomalia.criterio_usado else 'N/A',
                    'Revisado Por': anomalia.revisado_por.get_full_name() if anomalia.revisado_por else 'N/A',
                    'Observaciones': (anomalia.observaciones or 'Sin observaciones')[:200]
                })
                
            except Exception as e:
                print(f"⚠️ Error procesando anomalía {anomalia.id}: {str(e)}")
                # Continúar con la siguiente anomalía en lugar de fallar completamente
                continue
        
        if not data:
            messages.error(request, "No se pudieron procesar las anomalías para exportación.")
            return redirect('listado_anomalias')
        
        # Crear Excel
        import pandas as pd
        from io import BytesIO
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Hoja principal con anomalías
            df.to_excel(writer, sheet_name='Anomalías', index=False)
            
            # Hoja de estadísticas resumen
            stats_data = {
                'Métrica': [
                    'Total Anomalías',
                    'Estudiantes Únicos',
                    'Carreras Afectadas',
                    'Score Promedio',
                    'Anomalías por Estado',
                    'Fecha Generación'
                ],
                'Valor': [
                    len(data),
                    len(set(item['ID Estudiante'] for item in data)),
                    len(set(item['Carrera'] for item in data if item['Carrera'] != 'N/A')),
                    round(sum(item['Score Anomalía'] for item in data) / len(data), 2),
                    f"{len([item for item in data if 'Detectado' in str(item['Estado'])])} detectadas",
                    timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            
            df_stats = pd.DataFrame(stats_data)
            df_stats.to_excel(writer, sheet_name='Estadísticas', index=False)
        
        output.seek(0)
        
        # Crear respuesta HTTP
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        filename = f"reporte_anomalias_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        print(f"✅ Reporte generado exitosamente: {filename}")
        messages.success(request, f'Reporte de anomalías exportado: {filename}')
        return response
        
    except Exception as e:
        print(f"❌ Error exportando reporte: {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Error generando reporte: {str(e)}')
        return redirect('listado_anomalias')

# Vista para actualizar estado de anomalía
@login_required
@user_passes_test(lambda u: u.rol in ['analista_cpa', 'coordinador_cpa'])
def actualizar_estado_anomalia(request, anomalia_id):
    """Vista para actualizar estado de anomalía."""
    if request.method == 'POST':
        anomalia = get_object_or_404(DeteccionAnomalia, id=anomalia_id)
        
        # Verificar permisos
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                if anomalia.estudiante.carrera != carrera:
                    messages.error(request, "No tienes permisos para modificar esta anomalía.")
                    return redirect('detalle_anomalia', pk=anomalia_id)
            except Carrera.DoesNotExist:
                messages.error(request, "Tu usuario no tiene carrera asignada.")
                return redirect('detalle_anomalia', pk=anomalia_id)
        
        nuevo_estado = request.POST.get('estado')
        observaciones = request.POST.get('observaciones', '')
        
        if nuevo_estado in dict(DeteccionAnomalia.ESTADOS):
            estado_anterior = anomalia.get_estado_display()
            anomalia.estado = nuevo_estado
            
            if observaciones:
                if anomalia.observaciones:
                    anomalia.observaciones += f"\n\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] {request.user.get_full_name() or request.user.username}: {observaciones}"
                else:
                    anomalia.observaciones = f"[{timezone.now().strftime('%d/%m/%Y %H:%M')}] {request.user.get_full_name() or request.user.username}: {observaciones}"
            
            anomalia.revisado_por = request.user
            anomalia.fecha_ultima_actualizacion = timezone.now()
            anomalia.save()
            
            messages.success(
                request, 
                f'Estado actualizado de "{estado_anterior}" a "{anomalia.get_estado_display()}"'
            )
        else:
            messages.error(request, 'Estado inválido seleccionado.')
    
    return redirect('detalle_anomalia', pk=anomalia_id)

# Vista para gestión masiva de anomalías
@login_required
@user_passes_test(lambda u: u.rol in ['analista_cpa', 'coordinador_cpa'])
def gestion_masiva_anomalias(request):
    """
    🔧 FUNCIÓN MEJORADA: Gestión masiva de anomalías
    """
    if request.method != 'POST':
        messages.warning(request, 'Método no permitido para gestión masiva.')
        return redirect('listado_anomalias')
    
    try:
        # Obtener parámetros del formulario
        action = request.POST.get('action')
        anomalia_ids = request.POST.getlist('anomalias_seleccionadas')
        
        print(f"🔍 Gestión masiva:")
        print(f"   Action: {action}")
        print(f"   IDs: {anomalia_ids}")
        print(f"   Usuario: {request.user.username}")
        
        # CASO ESPECIAL: exportar_filtrados (sin IDs específicos)
        if action == 'exportar_filtrados':
            print("📊 Redirigiendo a exportación filtrada...")
            # Mantener los parámetros GET para aplicar los mismos filtros
            query_params = request.GET.urlencode()
            redirect_url = f"{reverse('exportar_todas_anomalias')}?{query_params}"
            return redirect(redirect_url)
        
        # Para las demás acciones, validar que se seleccionaron anomalías
        if not anomalia_ids:
            messages.error(request, 'No se seleccionaron anomalías.')
            return redirect('listado_anomalias')
        
        # Convertir IDs a enteros
        try:
            anomalia_ids = [int(id) for id in anomalia_ids]
        except ValueError:
            messages.error(request, 'IDs de anomalías inválidos.')
            return redirect('listado_anomalias')
        
        # Obtener anomalías
        anomalias = DeteccionAnomalia.objects.filter(id__in=anomalia_ids)
        
        # Filtrar por permisos del usuario
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                anomalias = anomalias.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                messages.error(request, 'No tienes permisos para esta acción.')
                return redirect('listado_anomalias')
        
        if not anomalias.exists():
            messages.error(request, 'No se encontraron anomalías válidas.')
            return redirect('listado_anomalias')
        
        # Ejecutar acción según el tipo
        if action == 'cambiar_estado':
            nuevo_estado = request.POST.get('nuevo_estado')
            if nuevo_estado in dict(DeteccionAnomalia.ESTADOS):
                count = anomalias.update(
                    estado=nuevo_estado,
                    revisado_por=request.user,
                    fecha_ultima_actualizacion=timezone.now()
                )
                messages.success(request, f'Se actualizó el estado de {count} anomalías a "{dict(DeteccionAnomalia.ESTADOS)[nuevo_estado]}".')
            else:
                messages.error(request, 'Estado inválido.')
        
        elif action == 'exportar':
            # Exportar solo las anomalías seleccionadas
            return generar_reporte_anomalias_seleccionadas(request, anomalia_ids)
        
        else:
            messages.error(request, f'Acción no válida: {action}.')
        
        return redirect('listado_anomalias')
        
    except Exception as e:
        print(f"❌ Error en gestión masiva: {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Error en gestión masiva: {str(e)}')
        return redirect('listado_anomalias')

@login_required
@user_passes_test(lambda u: u.rol in ['coordinador_cpa'])
def importar_datos_web(request):
    """Vista COMPLETA para importar datos desde la interfaz web."""
    
    if request.method == 'POST':
        try:
            form = ImportarDatosForm(request.POST, request.FILES)
            if form.is_valid():
                print("📁 Iniciando importación desde web...")
                
                resultados = {
                    'estudiantes': {'importados': 0, 'errores': [], 'advertencias': []},
                    'asignaturas': {'importados': 0, 'errores': [], 'advertencias': []},
                    'registros': {'importados': 0, 'errores': [], 'advertencias': []}
                }
                
                total_importados = 0
                total_errores = 0
                
                # Procesar archivo de estudiantes
                if form.cleaned_data.get('archivo_estudiantes'):
                    print("👥 Procesando estudiantes...")
                    resultados['estudiantes'] = procesar_archivo_estudiantes_web(
                        form.cleaned_data['archivo_estudiantes']
                    )
                    total_importados += resultados['estudiantes']['importados']
                    total_errores += len(resultados['estudiantes']['errores'])
                
                # Procesar archivo de asignaturas
                if form.cleaned_data.get('archivo_asignaturas'):
                    print("📚 Procesando asignaturas...")
                    resultados['asignaturas'] = procesar_archivo_asignaturas_web(
                        form.cleaned_data['archivo_asignaturas']
                    )
                    total_importados += resultados['asignaturas']['importados']
                    total_errores += len(resultados['asignaturas']['errores'])
                
                # Procesar archivo de registros académicos
                if form.cleaned_data.get('archivo_registros'):
                    print("📊 Procesando registros académicos...")
                    resultados['registros'] = procesar_archivo_registros_web(
                        form.cleaned_data['archivo_registros']
                    )
                    total_importados += resultados['registros']['importados']
                    total_errores += len(resultados['registros']['errores'])
                
                # Mostrar resultados
                if total_importados > 0:
                    messages.success(
                        request, 
                        f'✅ Importación completada: {total_importados} registros importados exitosamente.'
                    )
                
                if total_errores > 0:
                    messages.warning(
                        request,
                        f'⚠️ Se encontraron {total_errores} errores durante la importación. Revisa los detalles abajo.'
                    )
                
                # Renderizar página de resultados
                return render(request, 'anomalias/importar_resultados.html', {
                    'resultados': resultados,
                    'total_importados': total_importados,
                    'total_errores': total_errores
                })
                
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
                        
        except Exception as e:
            print(f"❌ Error en importación web: {str(e)}")
            print(traceback.format_exc())
            messages.error(request, f'Error procesando archivos: {str(e)}')
    else:
        form = ImportarDatosForm()
    
    # Obtener estadísticas actuales
    stats = {
        'total_estudiantes': Estudiante.objects.count(),
        'total_asignaturas': Asignatura.objects.count(), 
        'total_registros': RegistroAcademico.objects.count(),
        'total_carreras': Carrera.objects.count(),
    }
    
    return render(request, 'anomalias/importar_datos.html', {
        'form': form,
        'stats': stats
    })

def procesar_archivo_estudiantes_web(archivo):
    """
    🎓 Procesa archivo de estudiantes desde la interfaz web - CORREGIDO
    
    Formato esperado del CSV:
    - IdEstudiante (int): ID único del estudiante
    - Nombre (str): Nombre completo del estudiante  
    - Carrera (str): Nombre de la carrera
    - Ingreso_año (int): Año de ingreso (ej: 2020)
    """
    resultado = {'importados': 0, 'errores': [], 'advertencias': []}
    
    try:
        print(f"📥 Leyendo archivo de estudiantes: {archivo.name}")
        
        # Detectar tipo de archivo y leer
        if archivo.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(archivo)
        else:
            # Leer CSV con diferentes encodings para compatibilidad
            contenido = archivo.read()
            archivo.seek(0)  # Resetear posición del archivo
            
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    if isinstance(contenido, bytes):
                        contenido_str = contenido.decode(encoding)
                    else:
                        contenido_str = contenido
                    df = pd.read_csv(StringIO(contenido_str))
                    resultado['advertencias'].append(f'Archivo leído con encoding: {encoding}')
                    break
                except (UnicodeDecodeError, pd.errors.ParserError) as e:
                    continue
            else:
                resultado['errores'].append('No se pudo leer el archivo CSV. Verifique el formato.')
                return resultado
        
        # Limpiar nombres de columnas (quitar espacios)
        df.columns = df.columns.str.strip()
        
        print(f"📊 Archivo leído. Filas: {len(df)}, Columnas: {list(df.columns)}")
        
        # Validar columnas requeridas
        columnas_requeridas = ['IdEstudiante', 'Nombre', 'Carrera', 'Ingreso_año']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            resultado['errores'].append(f'Columnas faltantes: {", ".join(columnas_faltantes)}')
            return resultado
        
        # Informar sobre columnas que se ignoran
        if 'Id_Registro' in df.columns:
            resultado['advertencias'].append('Columna Id_Registro ignorada (no necesaria)')
        if 'PromedioNotas' in df.columns:
            resultado['advertencias'].append('Columna PromedioNotas ignorada (se calcula automáticamente)')
        
        # Procesar cada fila
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Validar datos básicos
                    if pd.isna(row['IdEstudiante']) or pd.isna(row['Nombre']):
                        resultado['errores'].append(f'Fila {index + 2}: IdEstudiante o Nombre vacío')
                        continue
                    
                    # Crear o buscar carrera - SIN el campo 'descripcion'
                    nombre_carrera = str(row['Carrera']).strip()
                    if not nombre_carrera or nombre_carrera == 'nan':
                        resultado['errores'].append(f'Fila {index + 2}: Carrera vacía o inválida')
                        continue
                    
                    # ✅ CORREGIDO: Solo usar campos que existen en tu modelo
                    carrera, created = Carrera.objects.get_or_create(
                        nombre=nombre_carrera,
                        defaults={
                            'codigo': f'COD{len(nombre_carrera)}{index}'  # Generar código automático
                        }
                    )
                    
                    if created:
                        resultado['advertencias'].append(f'Carrera creada: {nombre_carrera}')
                    
                    # Validar año de ingreso
                    try:
                        año_ingreso = int(row['Ingreso_año'])
                        if año_ingreso < 2000 or año_ingreso > timezone.now().year + 1:
                            resultado['errores'].append(f'Fila {index + 2}: Año de ingreso inválido: {año_ingreso}')
                            continue
                    except (ValueError, TypeError):
                        resultado['errores'].append(f'Fila {index + 2}: Año de ingreso no es un número válido')
                        continue
                    
                    # ✅ CORREGIDO: Crear o actualizar estudiante con campos correctos
                    estudiante, created = Estudiante.objects.update_or_create(
                        id_estudiante=int(row['IdEstudiante']),
                        defaults={
                            'nombre': str(row['Nombre']).strip(),
                            'carrera': carrera,
                            'ingreso_año': año_ingreso,  # Tu modelo SÍ tiene este campo
                            'activo': True
                        }
                    )
                    
                    if created:
                        resultado['importados'] += 1
                    else:
                        resultado['advertencias'].append(f'Estudiante actualizado: {estudiante.nombre}')
                        resultado['importados'] += 1
                        
                except Exception as e:
                    resultado['errores'].append(f'Fila {index + 2}: Error procesando - {str(e)}')
                    continue
        
        print(f"✅ Estudiantes procesados: {resultado['importados']} exitosos, {len(resultado['errores'])} errores")
        
    except Exception as e:
        print(f"❌ Error general procesando estudiantes: {str(e)}")
        import traceback
        traceback.print_exc()
        resultado['errores'].append(f'Error general: {str(e)}')
    
    return resultado


def procesar_archivo_asignaturas_web(archivo):
    """
    📚 Procesa archivo de asignaturas desde la interfaz web - CORREGIDO
    
    Formato esperado del CSV:
    - Id_Asignatura (int): ID único de la asignatura
    - NombreAsignatura (str): Nombre de la asignatura
    - Semestre (int): Semestre en que se dicta (1-8)
    """
    resultado = {'importados': 0, 'errores': [], 'advertencias': []}
    
    try:
        print(f"📥 Leyendo archivo de asignaturas: {archivo.name}")
        
        # Detectar tipo de archivo y leer
        if archivo.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(archivo)
        else:
            # Leer CSV con diferentes encodings
            contenido = archivo.read()
            archivo.seek(0)
            
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    if isinstance(contenido, bytes):
                        contenido_str = contenido.decode(encoding)
                    else:
                        contenido_str = contenido
                    df = pd.read_csv(StringIO(contenido_str))
                    resultado['advertencias'].append(f'Archivo leído con encoding: {encoding}')
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            else:
                resultado['errores'].append('No se pudo leer el archivo CSV. Verifique el formato.')
                return resultado
        
        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip()
        
        print(f"📊 Archivo leído. Filas: {len(df)}, Columnas: {list(df.columns)}")
        
        # Validar columnas requeridas
        columnas_requeridas = ['Id_Asignatura', 'NombreAsignatura', 'Semestre']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            resultado['errores'].append(f'Columnas faltantes: {", ".join(columnas_faltantes)}')
            return resultado
        
        # Procesar cada fila
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Validar datos básicos
                    if pd.isna(row['Id_Asignatura']) or pd.isna(row['NombreAsignatura']):
                        resultado['errores'].append(f'Fila {index + 2}: Id_Asignatura o NombreAsignatura vacío')
                        continue
                    
                    # Validar semestre
                    try:
                        semestre = int(row['Semestre'])
                        if semestre < 1 or semestre > 8:  # Tu modelo tiene validación 1-8
                            resultado['errores'].append(f'Fila {index + 2}: Semestre inválido: {semestre} (debe ser 1-8)')
                            continue
                    except (ValueError, TypeError):
                        resultado['errores'].append(f'Fila {index + 2}: Semestre no es un número válido')
                        continue
                    
                    # ✅ CORREGIDO: Crear o actualizar asignatura SIN campo 'activa'
                    asignatura, created = Asignatura.objects.update_or_create(
                        id_asignatura=int(row['Id_Asignatura']),
                        defaults={
                            'nombre': str(row['NombreAsignatura']).strip(),
                            'semestre': semestre,
                            # Removido 'activa': True porque no existe en tu modelo
                            # Tu modelo no tiene este campo, solo: nombre, semestre, carrera
                        }
                    )
                    
                    if created:
                        resultado['importados'] += 1
                    else:
                        resultado['advertencias'].append(f'Asignatura actualizada: {asignatura.nombre}')
                        resultado['importados'] += 1
                        
                except Exception as e:
                    resultado['errores'].append(f'Fila {index + 2}: Error procesando - {str(e)}')
                    continue
        
        print(f"✅ Asignaturas procesadas: {resultado['importados']} exitosas, {len(resultado['errores'])} errores")
        
    except Exception as e:
        print(f"❌ Error general procesando asignaturas: {str(e)}")
        import traceback
        traceback.print_exc()
        resultado['errores'].append(f'Error general: {str(e)}')
    
    return resultado


def procesar_archivo_registros_web(archivo):
    """
    📊 Procesa archivo de registros académicos desde la interfaz web - CORREGIDO
    
    Formato esperado del CSV:
    - Id_Estudiante (int): ID del estudiante (debe existir)
    - Id_asignatura (int): ID de la asignatura (debe existir)
    - Nota1, Nota2, Nota3, Nota4 (float): Notas parciales (1.0-7.0)
    - % de Asistencia (float): Porcentaje de asistencia (0-100)
    - % de Uso de plataforma (float): Porcentaje de uso de plataforma (0-100)
    """
    resultado = {'importados': 0, 'errores': [], 'advertencias': []}
    
    try:
        print(f"📥 Leyendo archivo de registros: {archivo.name}")
        
        # Detectar tipo de archivo y leer
        if archivo.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(archivo)
        else:
            # Leer CSV con diferentes encodings
            contenido = archivo.read()
            archivo.seek(0)
            
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    if isinstance(contenido, bytes):
                        contenido_str = contenido.decode(encoding)
                    else:
                        contenido_str = contenido
                    df = pd.read_csv(StringIO(contenido_str))
                    resultado['advertencias'].append(f'Archivo leído con encoding: {encoding}')
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            else:
                resultado['errores'].append('No se pudo leer el archivo CSV. Verifique el formato.')
                return resultado
        
        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip()
        
        print(f"📊 Archivo leído. Filas: {len(df)}, Columnas: {list(df.columns)}")
        
        # ✅ CORREGIDO: Ajustado a tu estructura real de CSV
        # Tu archivo tiene: Id_Registro,Id_Estudiante,Id_asignatura,Nota1,Nota2,Nota3,Nota4,PromedioNotas,% de Asistencia,% de Uso de plataforma
        
        columnas_requeridas = ['Id_Estudiante', 'Id_asignatura', 'Nota1', 'Nota2', 'Nota3', 'Nota4', '% de Asistencia', '% de Uso de plataforma']
        
        # Verificar que las columnas esenciales existan
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            resultado['errores'].append(f'Columnas faltantes: {", ".join(columnas_faltantes)}')
            return resultado
        
        # Cache de estudiantes y asignaturas para optimizar consultas
        estudiantes_cache = {}
        asignaturas_cache = {}
        
        # Procesar cada fila
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Validar IDs básicos
                    if pd.isna(row['Id_Estudiante']) or pd.isna(row['Id_asignatura']):
                        resultado['errores'].append(f'Fila {index + 2}: Id_Estudiante o Id_asignatura vacío')
                        continue
                    
                    id_estudiante = int(row['Id_Estudiante'])
                    id_asignatura = int(row['Id_asignatura'])
                    
                    # ✅ CORREGIDO: Buscar estudiante por id_estudiante (que es tu PK)
                    if id_estudiante not in estudiantes_cache:
                        try:
                            estudiantes_cache[id_estudiante] = Estudiante.objects.get(id_estudiante=id_estudiante)
                        except Estudiante.DoesNotExist:
                            resultado['errores'].append(f'Fila {index + 2}: Estudiante {id_estudiante} no existe')
                            continue
                    
                    estudiante = estudiantes_cache[id_estudiante]
                    
                    # ✅ CORREGIDO: Buscar asignatura por id_asignatura (que es tu PK)
                    if id_asignatura not in asignaturas_cache:
                        try:
                            asignaturas_cache[id_asignatura] = Asignatura.objects.get(id_asignatura=id_asignatura)
                        except Asignatura.DoesNotExist:
                            resultado['errores'].append(f'Fila {index + 2}: Asignatura {id_asignatura} no existe')
                            continue
                    
                    asignatura = asignaturas_cache[id_asignatura]
                    
                    # Validar y procesar notas
                    notas = []
                    for i in range(1, 5):
                        nota_col = f'Nota{i}'
                        try:
                            if pd.isna(row[nota_col]):
                                nota = 1.0  # Nota mínima si está vacía
                            else:
                                nota = float(row[nota_col])
                                if nota < 1.0 or nota > 7.0:
                                    resultado['advertencias'].append(f'Fila {index + 2}: Nota{i} fuera de rango (1.0-7.0): {nota}')
                                    nota = max(1.0, min(7.0, nota))  # Ajustar al rango válido
                            notas.append(nota)
                        except (ValueError, TypeError):
                            resultado['errores'].append(f'Fila {index + 2}: Nota{i} no es un número válido')
                            continue
                    
                    if len(notas) != 4:
                        continue  # Error ya registrado arriba
                    
                    # Calcular promedio (tu modelo lo hace automáticamente en save())
                    promedio_notas = sum(notas) / len(notas)
                    
                    # Validar asistencia
                    try:
                        asistencia = float(row['% de Asistencia'])
                        if asistencia < 0 or asistencia > 100:
                            resultado['advertencias'].append(f'Fila {index + 2}: Asistencia fuera de rango (0-100): {asistencia}')
                            asistencia = max(0, min(100, asistencia))
                    except (ValueError, TypeError):
                        resultado['errores'].append(f'Fila {index + 2}: % de Asistencia no es un número válido')
                        continue
                    
                    # Validar uso de plataforma
                    try:
                        uso_plataforma = float(row['% de Uso de plataforma'])
                        if uso_plataforma < 0 or uso_plataforma > 100:
                            resultado['advertencias'].append(f'Fila {index + 2}: Uso de plataforma fuera de rango (0-100): {uso_plataforma}')
                            uso_plataforma = max(0, min(100, uso_plataforma))
                    except (ValueError, TypeError):
                        resultado['errores'].append(f'Fila {index + 2}: % de Uso de plataforma no es un número válido')
                        continue
                    
                    # ✅ CORREGIDO: Crear o actualizar registro académico
                    registro, created = RegistroAcademico.objects.update_or_create(
                        estudiante=estudiante,
                        asignatura=asignatura,
                        defaults={
                            'nota1': notas[0],
                            'nota2': notas[1],
                            'nota3': notas[2],
                            'nota4': notas[3],
                            # promedio_notas se calcula automáticamente en save()
                            'porcentaje_asistencia': asistencia,
                            'porcentaje_uso_plataforma': uso_plataforma
                        }
                    )
                    
                    if created:
                        resultado['importados'] += 1
                    else:
                        resultado['advertencias'].append(f'Registro actualizado: {estudiante.nombre} - {asignatura.nombre}')
                        resultado['importados'] += 1
                        
                except Exception as e:
                    resultado['errores'].append(f'Fila {index + 2}: Error procesando - {str(e)}')
                    continue
        
        print(f"✅ Registros procesados: {resultado['importados']} exitosos, {len(resultado['errores'])} errores")
        
    except Exception as e:
        print(f"❌ Error general procesando registros: {str(e)}")
        import traceback
        traceback.print_exc()
        resultado['errores'].append(f'Error general: {str(e)}')
    
    return resultado

def ejecutar_deteccion_anomalias_debug(criterio, usuario_ejecutor):
    """Versión con diagnóstico detallado."""
    import logging
    logger = logging.getLogger(__name__)
    
    inicio_tiempo = time.time()
    try:
        logger.info(f"=== INICIANDO ANÁLISIS DEBUG ===")
        logger.info(f"Criterio: {criterio.nombre}")
        logger.info(f"Usuario: {usuario_ejecutor.username}")
        
        # 1. Preparar datos con logging detallado
        logger.info("Preparando datos de estudiantes...")
        datos_estudiantes = preparar_datos_estudiantes_debug(criterio)
        
        if len(datos_estudiantes) < 10:
            error_msg = f'Datos insuficientes: {len(datos_estudiantes)} estudiantes (mínimo 10)'
            logger.error(error_msg)
            return {
                'exitoso': False,
                'error': error_msg,
                'anomalias_detectadas': 0,
                'total_estudiantes': len(datos_estudiantes),
                'debug_info': 'Insuficientes datos'
            }
        
        logger.info(f"Datos preparados exitosamente: {len(datos_estudiantes)} estudiantes")
        logger.info(f"Características disponibles: {len(datos_estudiantes.columns) - 1}")  # -1 por Id_Estudiante
        
        # 2. Ejecutar modelo
        logger.info("Ejecutando Isolation Forest...")
        resultados_modelo = ejecutar_isolation_forest_debug(datos_estudiantes, criterio)
        
        if not resultados_modelo:
            return {
                'exitoso': False,
                'error': 'Error en Isolation Forest',
                'anomalias_detectadas': 0,
                'debug_info': 'Fallo en modelo'
            }
        
        logger.info(f"Modelo ejecutado. Anomalías detectadas: {np.sum(resultados_modelo['es_anomalia'])}")
        
        # 3. Clasificar anomalías
        logger.info("Clasificando anomalías...")
        anomalias_clasificadas = clasificar_anomalias_debug(datos_estudiantes, resultados_modelo, criterio)
        logger.info(f"Anomalías clasificadas: {len(anomalias_clasificadas)}")
        
        # 4. Guardar en base de datos
        logger.info("Guardando detecciones en base de datos...")
        nuevas_anomalias = guardar_detecciones_debug(anomalias_clasificadas, criterio)
        logger.info(f"Nuevas anomalías guardadas: {len(nuevas_anomalias)}")
        
        # 5. Verificar guardado
        total_anomalias_criterio = DeteccionAnomalia.objects.filter(criterio_usado=criterio).count()
        logger.info(f"Total anomalías en BD para este criterio: {total_anomalias_criterio}")
        
        # 6. Registrar ejecución
        tiempo_ejecucion = time.time() - inicio_tiempo
        registrar_ejecucion(criterio, usuario_ejecutor, datos_estudiantes, 
                            resultados_modelo, tiempo_ejecucion, True)
        
        logger.info(f"=== ANÁLISIS COMPLETADO ===")
        
        return {
            'exitoso': True,
            'anomalias_detectadas': len(nuevas_anomalias),
            'total_estudiantes': len(datos_estudiantes),
            'porcentaje_anomalias': (len(nuevas_anomalias) / len(datos_estudiantes)) * 100,
            'tiempo_ejecucion': tiempo_ejecucion,
            'nuevas_anomalias': nuevas_anomalias,
            'debug_info': {
                'caracteristicas_usadas': len(datos_estudiantes.columns) - 1,
                'modelo_score_promedio': float(np.mean(resultados_modelo['scores'])),
                'total_en_bd': total_anomalias_criterio
            }
        }
        
    except Exception as e:
        logger.error(f"ERROR EN ANÁLISIS: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        tiempo_ejecucion = time.time() - inicio_tiempo
        registrar_ejecucion(criterio, usuario_ejecutor, [], {}, 
                            tiempo_ejecucion, False, str(e))
        
        return {
            'exitoso': False,
            'error': str(e),
            'anomalias_detectadas': 0,
            'tiempo_ejecucion': tiempo_ejecucion,
            'debug_info': 'Excepción crítica'
        }

def preparar_datos_estudiantes_debug(criterio):
    """Preparación de datos con logging detallado."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Filtros aplicados:")
    logger.info(f"  - Carrera: {criterio.carrera}")
    logger.info(f"  - Semestre: {criterio.semestre}")
    
    # Contar estudiantes
    queryset_estudiantes = Estudiante.objects.filter(activo=True)
    if criterio.carrera:
        queryset_estudiantes = queryset_estudiantes.filter(carrera=criterio.carrera)
    
    estudiantes_count = queryset_estudiantes.count()
    logger.info(f"Estudiantes que cumplen filtros: {estudiantes_count}")
    
    # Contar registros
    queryset_registros = RegistroAcademico.objects.select_related('estudiante', 'asignatura')
    if criterio.carrera:
        queryset_registros = queryset_registros.filter(estudiante__carrera=criterio.carrera)
    if criterio.semestre:
        queryset_registros = queryset_registros.filter(asignatura__semestre=criterio.semestre)
    
    registros_count = queryset_registros.count()
    logger.info(f"Registros académicos que cumplen filtros: {registros_count}")
    
    if registros_count == 0:
        logger.error("No hay registros académicos para procesar")
        return pd.DataFrame()
    
    # Convertir a DataFrame
    registros_data = []
    for registro in queryset_registros:
        registros_data.append({
            'Id_Estudiante': registro.estudiante.id_estudiante,
            'Id_asignatura': registro.asignatura.id_asignatura,
            'Semestre': registro.asignatura.semestre,
            'PromedioNotas': registro.promedio_notas,
            'PorcentajeAsistencia': registro.porcentaje_asistencia,
            'PorcentajeUsoPlataforma': registro.porcentaje_uso_plataforma,
            'Nota1': registro.nota1,
            'Nota2': registro.nota2,
            'Nota3': registro.nota3,
            'Nota4': registro.nota4,
        })
    
    df_registros = pd.DataFrame(registros_data)
    logger.info(f"DataFrame creado: {len(df_registros)} filas")
    logger.info(f"Estudiantes únicos en DataFrame: {df_registros['Id_Estudiante'].nunique()}")
    
    # Verificar distribución de registros por estudiante
    registros_por_estudiante = df_registros.groupby('Id_Estudiante').size()
    logger.info(f"Registros por estudiante - Min: {registros_por_estudiante.min()}, Max: {registros_por_estudiante.max()}, Media: {registros_por_estudiante.mean():.1f}")
    
    # Calcular métricas
    metricas_estudiantes = calcular_metricas_estudiantes(df_registros)
    logger.info(f"Métricas calculadas para {len(metricas_estudiantes)} estudiantes")
    
    return metricas_estudiantes

def guardar_detecciones_debug(anomalias_clasificadas, criterio):
    """Guardado con verificación detallada."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Guardando {len(anomalias_clasificadas)} anomalías clasificadas")
    
    nuevas_anomalias = []
    actualizadas = 0
    errores = 0
    
    for i, anomalia_info in enumerate(anomalias_clasificadas):
        try:
            estudiante_id = anomalia_info['estudiante_id']
            logger.debug(f"Procesando estudiante {estudiante_id}")
            
            try:
                estudiante = Estudiante.objects.get(id_estudiante=estudiante_id)
            except Estudiante.DoesNotExist:
                logger.warning(f"Estudiante {estudiante_id} no encontrado")
                errores += 1
                continue
            
            # Verificar si existe detección reciente
            deteccion_existente = DeteccionAnomalia.objects.filter(
                estudiante=estudiante,
                fecha_deteccion__gte=timezone.now() - timedelta(days=30),
                estado__in=['detectado', 'en_revision', 'intervencion_activa']
            ).first()
            
            if deteccion_existente:
                # Actualizar si es peor
                if anomalia_info['score_anomalia'] < deteccion_existente.score_anomalia:
                    deteccion_existente.score_anomalia = anomalia_info['score_anomalia']
                    deteccion_existente.confianza = anomalia_info['confianza']
                    deteccion_existente.prioridad = anomalia_info['prioridad']
                    deteccion_existente.tipo_anomalia = anomalia_info['tipo_anomalia']
                    deteccion_existente.criterio_usado = criterio
                    deteccion_existente.fecha_ultima_actualizacion = timezone.now()
                    deteccion_existente.save()
                    actualizadas += 1
                    logger.debug(f"Detección actualizada para estudiante {estudiante.nombre}")
            else:
                # Crear nueva
                nueva_deteccion = DeteccionAnomalia.objects.create(
                    estudiante=estudiante,
                    criterio_usado=criterio,
                    tipo_anomalia=anomalia_info['tipo_anomalia'],
                    score_anomalia=anomalia_info['score_anomalia'],
                    confianza=anomalia_info['confianza'],
                    promedio_general=anomalia_info['promedio_general'],
                    asistencia_promedio=anomalia_info['asistencia_promedio'],
                    uso_plataforma_promedio=anomalia_info['uso_plataforma_promedio'],
                    variacion_notas=anomalia_info['variacion_notas'],
                    prioridad=anomalia_info['prioridad']
                )
                nuevas_anomalias.append(nueva_deteccion)
                logger.debug(f"Nueva detección creada para estudiante {estudiante.nombre}")
                
        except Exception as e:
            logger.error(f"Error guardando detección para estudiante {anomalia_info.get('estudiante_id', 'N/A')}: {str(e)}")
            errores += 1
    
    logger.info(f"Guardado completado: {len(nuevas_anomalias)} nuevas, {actualizadas} actualizadas, {errores} errores")
    
    return nuevas_anomalias

@login_required
@user_passes_test(es_coordinador_cpa)
def verificar_sistema(request):
    """Vista para verificación rápida del sistema."""
    
    # Estadísticas básicas
    stats = {
        'estudiantes_activos': Estudiante.objects.filter(activo=True).count(),
        'registros_academicos': RegistroAcademico.objects.count(),
        'criterios_activos': CriterioAnomalia.objects.filter(activo=True).count(),
        'anomalias_total': DeteccionAnomalia.objects.count(),
        'anomalias_activas': DeteccionAnomalia.objects.filter(
            estado__in=['detectado', 'en_revision', 'intervencion_activa']
        ).count(),
        'ejecuciones_exitosas': EjecucionAnalisis.objects.filter(exitoso=True).count(),
        'ultima_ejecucion': EjecucionAnalisis.objects.order_by('-fecha_ejecucion').first()
    }
    
    # Problemas detectados
    problemas = []
    
    if stats['estudiantes_activos'] < 10:
        problemas.append('Muy pocos estudiantes activos (< 10)')
    
    if stats['registros_academicos'] < 30:
        problemas.append('Muy pocos registros académicos (< 30)')
    
    if stats['criterios_activos'] == 0:
        problemas.append('No hay criterios activos')
    
    if stats['anomalias_total'] == 0 and stats['ejecuciones_exitosas'] > 0:
        problemas.append('Hay ejecuciones exitosas pero no hay anomalías guardadas')
    
    # Distribución por estudiante
    if stats['estudiantes_activos'] > 0 and stats['registros_academicos'] > 0:
        registros_por_estudiante = stats['registros_academicos'] / stats['estudiantes_activos']
        if registros_por_estudiante < 3:
            problemas.append(f'Pocos registros por estudiante ({registros_por_estudiante:.1f} < 3)')
    
    context = {
        'stats': stats,
        'problemas': problemas,
        'estado_general': 'OK' if not problemas else 'PROBLEMAS DETECTADOS'
    }
    
    return render(request, 'anomalias/verificar_sistema.html', context)

class ConfiguracionCriteriosView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vista para configuración de criterios."""
    model = CriterioAnomalia
    template_name = 'anomalias/configuracion_criterios.html'
    context_object_name = 'criterios'
    
    def test_func(self):
        return self.request.user.rol == 'coordinador_cpa'
    
    def get_queryset(self):
        try:
            return CriterioAnomalia.objects.filter(activo=True).order_by('-fecha_creacion')
        except Exception as e:
            print(f"Error en get_queryset criterios: {e}")
            return CriterioAnomalia.objects.none()

@login_required
@user_passes_test(lambda u: u.rol in ['coordinador_cpa', 'analista_cpa', 'coordinador_carrera'])
def api_exportar_datos_avanzado(request):
    """
    🔧 API NUEVA: Exportación avanzada con filtros personalizados
    """
    try:
        # Obtener parámetros del request
        formato = request.GET.get('formato', 'excel')  # excel, csv, json
        incluir_derivaciones = request.GET.get('incluir_derivaciones', 'true').lower() == 'true'
        incluir_estadisticas = request.GET.get('incluir_estadisticas', 'true').lower() == 'true'
        estado_filtro = request.GET.get('estado', '')
        tipo_filtro = request.GET.get('tipo', '')
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        
        print(f"📊 Exportación avanzada - Formato: {formato}")
        
        # Construir queryset con filtros
        queryset = DeteccionAnomalia.objects.select_related(
            'estudiante', 'estudiante__carrera', 'criterio_usado'
        )
        
        # Filtros por rol
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                queryset = queryset.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                return JsonResponse({'error': 'Usuario sin carrera asignada'}, status=403)
        
        # Aplicar filtros opcionales
        if estado_filtro:
            queryset = queryset.filter(estado=estado_filtro)
        
        if tipo_filtro:
            queryset = queryset.filter(tipo_anomalia=tipo_filtro)
        
        if fecha_desde:
            queryset = queryset.filter(fecha_deteccion__date__gte=fecha_desde)
        
        if fecha_hasta:
            queryset = queryset.filter(fecha_deteccion__date__lte=fecha_hasta)
        
        # Preparar datos
        datos_export = []
        for anomalia in queryset:
            dato = {
                'id_estudiante': anomalia.estudiante.id_estudiante,
                'nombre_estudiante': anomalia.estudiante.nombre,
                'carrera': anomalia.estudiante.carrera.nombre if anomalia.estudiante.carrera else 'N/A',
                'tipo_anomalia': anomalia.get_tipo_anomalia_display(),
                'score_anomalia': round(anomalia.score_anomalia, 2),
                'confianza': round(anomalia.confianza, 2),
                'promedio_general': round(anomalia.promedio_general, 2),
                'asistencia_promedio': round(anomalia.asistencia_promedio, 2),
                'uso_plataforma_promedio': round(anomalia.uso_plataforma_promedio, 2),
                'estado': anomalia.get_estado_display(),
                'prioridad': anomalia.prioridad,
                'fecha_deteccion': anomalia.fecha_deteccion.strftime('%Y-%m-%d %H:%M:%S'),
                'criterio_usado': anomalia.criterio_usado.nombre if anomalia.criterio_usado else 'N/A'
            }
            
            # Incluir derivaciones si se solicita
            if incluir_derivaciones:
                derivaciones = Derivacion.objects.filter(deteccion_anomalia=anomalia)
                if derivaciones.exists():
                    derivacion = derivaciones.first()
                    dato.update({
                        'tiene_derivacion': 'Sí',
                        'instancia_apoyo': derivacion.instancia_apoyo.nombre,
                        'estado_derivacion': derivacion.get_estado_display(),
                        'fecha_derivacion': derivacion.fecha_derivacion.strftime('%Y-%m-%d')
                    })
                else:
                    dato.update({
                        'tiene_derivacion': 'No',
                        'instancia_apoyo': '',
                        'estado_derivacion': '',
                        'fecha_derivacion': ''
                    })
            
            datos_export.append(dato)
        
        # Estadísticas resumidas
        estadisticas = {}
        if incluir_estadisticas:
            estadisticas = {
                'total_registros': len(datos_export),
                'por_tipo': list(queryset.values('tipo_anomalia').annotate(count=Count('id'))),
                'por_estado': list(queryset.values('estado').annotate(count=Count('id'))),
                'por_carrera': list(queryset.values('estudiante__carrera__nombre').annotate(count=Count('id'))),
                'promedio_score': queryset.aggregate(Avg('score_anomalia'))['score_anomalia__avg'],
                'promedio_confianza': queryset.aggregate(Avg('confianza'))['confianza__avg']
            }
        
        # Generar respuesta según formato
        if formato == 'json':
            return JsonResponse({
                'datos': datos_export,
                'estadisticas': estadisticas,
                'filtros_aplicados': {
                    'estado': estado_filtro,
                    'tipo': tipo_filtro,
                    'fecha_desde': fecha_desde,
                    'fecha_hasta': fecha_hasta
                },
                'timestamp': timezone.now().isoformat()
            })
        
        elif formato == 'csv':
            import csv
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="anomalias_export_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
            
            if datos_export:
                # Usar BOM UTF-8 para Excel
                response.write('\ufeff')
                
                writer = csv.DictWriter(response, fieldnames=datos_export[0].keys())
                writer.writeheader()
                writer.writerows(datos_export)
            
            return response
        
        else:  # Excel por defecto
            df = pd.DataFrame(datos_export)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Datos', index=False)
                
                if estadisticas:
                    df_stats = pd.DataFrame([
                        {'Métrica': k, 'Valor': v} for k, v in estadisticas.items()
                        if not isinstance(v, (list, dict))
                    ])
                    df_stats.to_excel(writer, sheet_name='Estadísticas', index=False)
            
            output.seek(0)
            
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="export_avanzado_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
            
            return response
    
    except Exception as e:
        print(f"❌ Error en exportación avanzada: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def api_validacion_tiempo_real(request):
    """API para validación de calidad de datos en tiempo real."""
    try:
        validaciones = {
            'notas_fuera_rango': 0,
            'asistencia_invalida': 0,
            'registros_duplicados': 0,
            'estudiantes_sin_registros': 0,
            'datos_inconsistentes': 0
        }
        
        # Validar rangos de notas
        validaciones['notas_fuera_rango'] = RegistroAcademico.objects.filter(
            Q(nota1__lt=1.0) | Q(nota1__gt=7.0) |
            Q(nota2__lt=1.0) | Q(nota2__gt=7.0) |
            Q(nota3__lt=1.0) | Q(nota3__gt=7.0) |
            Q(nota4__lt=1.0) | Q(nota4__gt=7.0)
        ).count()
        
        # Validar rangos de asistencia
        validaciones['asistencia_invalida'] = RegistroAcademico.objects.filter(
            Q(porcentaje_asistencia__lt=0) | Q(porcentaje_asistencia__gt=100)
        ).count()
        
        # Validar registros duplicados
        from django.db.models import Count
        duplicados = RegistroAcademico.objects.values(
            'estudiante', 'asignatura'
        ).annotate(count=Count('id')).filter(count__gt=1)
        validaciones['registros_duplicados'] = duplicados.count()
        
        # Estudiantes sin registros
        validaciones['estudiantes_sin_registros'] = Estudiante.objects.filter(
            registroacademico__isnull=True,
            activo=True
        ).count()
        
        # Datos inconsistentes (promedio calculado vs almacenado)
        registros_inconsistentes = 0
        for registro in RegistroAcademico.objects.all()[:100]:  # Muestra pequeña para performance
            promedio_calculado = (registro.nota1 + registro.nota2 + registro.nota3 + registro.nota4) / 4
            if abs(promedio_calculado - registro.promedio_notas) > 0.1:
                registros_inconsistentes += 1
        validaciones['datos_inconsistentes'] = registros_inconsistentes
        
        # Evaluar estado general
        total_problemas = sum(validaciones.values())
        total_registros = RegistroAcademico.objects.count()
        
        if total_registros == 0:
            estado_general = {'estado': 'sin_datos', 'mensaje': 'No hay datos para validar'}
        elif total_problemas == 0:
            estado_general = {'estado': 'excelente', 'mensaje': 'Todos los datos son válidos'}
        elif total_problemas < total_registros * 0.01:  # Menos del 1%
            estado_general = {'estado': 'bueno', 'mensaje': 'Calidad de datos buena'}
        elif total_problemas < total_registros * 0.05:  # Menos del 5%
            estado_general = {'estado': 'aceptable', 'mensaje': 'Calidad de datos aceptable'}
        else:
            estado_general = {'estado': 'problemático', 'mensaje': 'Problemas significativos en los datos'}
        
        # Sugerencias de mejora
        sugerencias = []
        if validaciones['notas_fuera_rango'] > 0:
            sugerencias.append('Revisar y corregir notas fuera del rango 1.0-7.0')
        if validaciones['asistencia_invalida'] > 0:
            sugerencias.append('Corregir porcentajes de asistencia inválidos')
        if validaciones['registros_duplicados'] > 0:
            sugerencias.append('Eliminar o consolidar registros duplicados')
        if validaciones['estudiantes_sin_registros'] > 0:
            sugerencias.append('Agregar registros académicos para estudiantes activos')
        
        return JsonResponse({
            'validaciones': validaciones,
            'estado_general': estado_general,
            'sugerencias': sugerencias,
            'timestamp': timezone.now().isoformat(),
            'total_registros': total_registros,
            'porcentaje_problemas': round((total_problemas / max(total_registros, 1)) * 100, 2)
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'validaciones': {},
            'estado_general': {'estado': 'error', 'mensaje': f'Error en validación: {str(e)}'}
        }, status=500)

@login_required
@user_passes_test(lambda u: u.rol == 'coordinador_cpa')
def detalle_criterio(request, criterio_id):
    """Vista para ver detalles del criterio."""
    criterio = get_object_or_404(CriterioAnomalia, id=criterio_id)
    
    # Obtener estadísticas del criterio
    ejecuciones = EjecucionAnalisis.objects.filter(criterio_usado=criterio).order_by('-fecha_ejecucion')
    total_ejecuciones = ejecuciones.count()
    ejecuciones_exitosas = ejecuciones.filter(exitoso=True).count()
    
    # Anomalías detectadas con este criterio
    anomalias_detectadas = DeteccionAnomalia.objects.filter(criterio_usado=criterio)
    total_anomalias = anomalias_detectadas.count()
    
    # Última ejecución
    ultima_ejecucion = ejecuciones.first()
    
    # Distribución por tipo de anomalía
    anomalias_por_tipo = anomalias_detectadas.values('tipo_anomalia').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'criterio': criterio,
        'total_ejecuciones': total_ejecuciones,
        'ejecuciones_exitosas': ejecuciones_exitosas,
        'total_anomalias': total_anomalias,
        'ultima_ejecucion': ultima_ejecucion,
        'anomalias_por_tipo': anomalias_por_tipo,
        'ejecuciones_recientes': ejecuciones[:5],
    }
    
    return render(request, 'anomalias/detalle_criterio.html', context)

@login_required
@user_passes_test(lambda u: u.rol == 'coordinador_cpa')
def editar_criterio(request, criterio_id):
    """Vista para editar criterio."""
    criterio = get_object_or_404(CriterioAnomalia, id=criterio_id)
    
    if request.method == 'POST':
        form = CriterioAnomaliaForm(request.POST, instance=criterio)
        if form.is_valid():
            form.save()
            messages.success(request, f'Criterio "{criterio.nombre}" actualizado exitosamente.')
            return redirect('configuracion_criterios')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CriterioAnomaliaForm(instance=criterio)
    
    context = {
        'form': form,
        'criterio': criterio,
        'editando': True,
    }
    
    return render(request, 'anomalias/crear_criterio.html', context)

@login_required
def detalle_derivacion_ajax(request, derivacion_id):
    """
    🔧 FUNCIÓN CORREGIDA: Mostrar detalle de derivación vía AJAX
    """
    try:
        derivacion = get_object_or_404(Derivacion, id=derivacion_id)
        
        # Verificar permisos
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                if derivacion.deteccion_anomalia.estudiante.carrera != carrera:
                    return JsonResponse({'error': 'Sin permisos'}, status=403)
            except Carrera.DoesNotExist:
                return JsonResponse({'error': 'Usuario sin carrera'}, status=403)
        
        # 🔧 SOLUCIÓN TEMPORAL: Usar prioridad de la anomalía si no existe en derivación
        try:
            prioridad_display = derivacion.get_prioridad_display()
        except AttributeError:
            # Si no existe prioridad en derivación, usar la de la anomalía
            prioridad_display = f"Prioridad {derivacion.deteccion_anomalia.prioridad}"
        
        # 🔧 SOLUCIÓN TEMPORAL: Usar observaciones_derivacion si no existe observaciones_seguimiento
        observaciones_seguimiento = getattr(derivacion, 'observaciones_seguimiento', None) or derivacion.observaciones_derivacion
        
        html_detalle = f"""
        <div class="row">
            <div class="col-md-6">
                <h6><i class="fas fa-user-graduate me-2"></i>Información del Estudiante</h6>
                <table class="table table-sm">
                    <tr>
                        <td><strong>ID:</strong></td>
                        <td>{derivacion.deteccion_anomalia.estudiante.id_estudiante}</td>
                    </tr>
                    <tr>
                        <td><strong>Nombre:</strong></td>
                        <td>{derivacion.deteccion_anomalia.estudiante.nombre}</td>
                    </tr>
                    <tr>
                        <td><strong>Carrera:</strong></td>
                        <td>{derivacion.deteccion_anomalia.estudiante.carrera.nombre if derivacion.deteccion_anomalia.estudiante.carrera else 'N/A'}</td>
                    </tr>
                    <tr>
                        <td><strong>Tipo Anomalía:</strong></td>
                        <td><span class="badge bg-info">{derivacion.deteccion_anomalia.get_tipo_anomalia_display()}</span></td>
                    </tr>
                    <tr>
                        <td><strong>Derivado por:</strong></td>
                        <td>{derivacion.derivado_por.get_full_name() if derivacion.derivado_por else 'N/A'}</td>
                    </tr>
                </table>
            </div>
            <div class="col-md-6">
                <h6><i class="fas fa-info-circle me-2"></i>Detalles de la Derivación</h6>
                <table class="table table-sm">
                    <tr>
                        <td><strong>Fecha:</strong></td>
                        <td>{derivacion.fecha_derivacion.strftime('%d/%m/%Y %H:%M')}</td>
                    </tr>
                    <tr>
                        <td><strong>Prioridad:</strong></td>
                        <td><span class="badge bg-warning">{prioridad_display}</span></td>
                    </tr>
                    <tr>
                        <td><strong>Estado:</strong></td>
                        <td><span class="badge bg-primary">{derivacion.get_estado_display()}</span></td>
                    </tr>
                    <tr>
                        <td><strong>Instancia:</strong></td>
                        <td>{derivacion.instancia_apoyo.nombre}</td>
                    </tr>
                </table>
            </div>
        </div>
        
        <hr>
        
        <div class="row">
            <div class="col-12">
                <h6><i class="fas fa-comment me-2"></i>Motivo de la Derivación</h6>
                <div class="alert alert-light">
                    {derivacion.motivo or 'Sin motivo especificado'}
                </div>
            </div>
        </div>
        
        {f'''
        <div class="row">
            <div class="col-12">
                <h6><i class="fas fa-notes-medical me-2"></i>Observaciones y Seguimiento</h6>
                <div class="alert alert-info">
                    {observaciones_seguimiento}
                </div>
            </div>
        </div>
        ''' if observaciones_seguimiento else ''}
        
        {f'''
        <div class="row">
            <div class="col-12">
                <h6><i class="fas fa-reply me-2"></i>Respuesta de la Instancia</h6>
                <div class="alert alert-success">
                    {derivacion.respuesta_instancia}
                </div>
            </div>
        </div>
        ''' if derivacion.respuesta_instancia else ''}
        """
        
        return JsonResponse({
            'success': True,
            'html': html_detalle
        })
        
    except Exception as e:
        print(f"❌ Error en detalle_derivacion_ajax: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# Vista de perfil de usuario CORREGIDA
@login_required
def perfil_usuario(request):
    """
    👤 FUNCIÓN CORREGIDA: Vista de perfil de usuario
    """
    print(f"👤 Cargando perfil para usuario: {request.user.username}")
    
    try:
        if request.method == 'POST':
            print("📝 Procesando actualización de perfil...")
            
            # Obtener datos del formulario
            nombre = request.POST.get('first_name', '').strip()
            apellido = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            
            # Validaciones básicas
            errores = []
            
            if not nombre:
                errores.append("El nombre es obligatorio")
            
            if not email:
                errores.append("El email es obligatorio")
            elif not '@' in email:
                errores.append("El email no es válido")
            
            # Verificar si el email ya existe (excepto el usuario actual)
            if Usuario.objects.filter(email=email).exclude(id=request.user.id).exists():
                errores.append("Este email ya está en uso por otro usuario")
            
            if errores:
                for error in errores:
                    messages.error(request, error)
            else:
                # Actualizar datos del usuario
                request.user.first_name = nombre
                request.user.last_name = apellido
                request.user.email = email
                
                # Actualizar teléfono si el campo existe
                if hasattr(request.user, 'telefono'):
                    request.user.telefono = telefono
                
                request.user.save()
                
                messages.success(request, 'Perfil actualizado exitosamente.')
                print(f"✅ Perfil actualizado para {request.user.username}")
                
                return redirect('perfil_usuario')
        
        # Calcular estadísticas del usuario
        stats = {}
        
        # Estadísticas comunes para todos los roles
        if request.user.rol in ['analista_cpa', 'coordinador_cpa']:
            # Derivaciones creadas
            stats['derivaciones_creadas'] = Derivacion.objects.filter(
                derivado_por=request.user
            ).count()
            
            # Anomalías revisadas
            stats['anomalias_revisadas'] = DeteccionAnomalia.objects.filter(
                revisado_por=request.user
            ).count()
            
            # Derivaciones pendientes
            stats['derivaciones_pendientes'] = Derivacion.objects.filter(
                derivado_por=request.user,
                estado__in=['pendiente', 'enviada']
            ).count()
            
            # Anomalías resueltas por el usuario
            stats['anomalias_resueltas'] = DeteccionAnomalia.objects.filter(
                revisado_por=request.user,
                estado='resuelto'
            ).count()
        
        # Estadísticas específicas para coordinador CPA
        if request.user.rol == 'coordinador_cpa':
            stats['criterios_creados'] = CriterioAnomalia.objects.filter(
                creado_por=request.user
            ).count()
            
            stats['analisis_ejecutados'] = EjecucionAnalisis.objects.filter(
                ejecutado_por=request.user
            ).count()
            
            stats['criterios_activos'] = CriterioAnomalia.objects.filter(
                creado_por=request.user,
                activo=True
            ).count()
        
        # Estadísticas para coordinador de carrera
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                
                stats['estudiantes_carrera'] = Estudiante.objects.filter(
                    carrera=carrera,
                    activo=True
                ).count()
                
                stats['anomalias_carrera'] = DeteccionAnomalia.objects.filter(
                    estudiante__carrera=carrera
                ).count()
                
                stats['asignaturas_carrera'] = Asignatura.objects.filter(
                    carrera=carrera
                ).count()
                
                # Asignaturas críticas
                asignaturas_criticas = 0
                for asignatura in Asignatura.objects.filter(carrera=carrera):
                    registros = RegistroAcademico.objects.filter(asignatura=asignatura)
                    if registros.exists():
                        estudiantes_ids = registros.values_list('estudiante_id', flat=True).distinct()
                        anomalias = DeteccionAnomalia.objects.filter(
                            estudiante_id__in=estudiantes_ids,
                            estado__in=['detectado', 'en_revision', 'intervencion_activa']
                        ).count()
                        
                        if len(estudiantes_ids) > 0:
                            porcentaje = (anomalias / len(estudiantes_ids)) * 100
                            if porcentaje >= 15:
                                asignaturas_criticas += 1
                
                stats['asignaturas_criticas'] = asignaturas_criticas
                stats['carrera_nombre'] = carrera.nombre
                
            except Carrera.DoesNotExist:
                stats['carrera_nombre'] = 'Sin carrera asignada'
                messages.warning(request, "Tu usuario no tiene carrera asignada.")
        
        # Actividad reciente del usuario
        actividad_reciente = []
        
        # Últimas derivaciones
        ultimas_derivaciones = Derivacion.objects.filter(
            derivado_por=request.user
        ).order_by('-fecha_derivacion')[:5]
        
        for derivacion in ultimas_derivaciones:
            actividad_reciente.append({
                'tipo': 'derivacion',
                'descripcion': f'Derivación creada para {derivacion.deteccion_anomalia.estudiante.nombre}',
                'fecha': derivacion.fecha_derivacion,
                'url': reverse('detalle_anomalia', kwargs={'pk': derivacion.deteccion_anomalia.id})
            })
        
        # Últimas anomalías revisadas
        ultimas_revisiones = DeteccionAnomalia.objects.filter(
            revisado_por=request.user
        ).order_by('-fecha_ultima_actualizacion')[:5]
        
        for anomalia in ultimas_revisiones:
            actividad_reciente.append({
                'tipo': 'revision',
                'descripcion': f'Anomalía revisada: {anomalia.estudiante.nombre}',
                'fecha': anomalia.fecha_ultima_actualizacion,
                'url': reverse('detalle_anomalia', kwargs={'pk': anomalia.id})
            })
        
        # Ordenar actividad por fecha
        actividad_reciente.sort(key=lambda x: x['fecha'], reverse=True)
        actividad_reciente = actividad_reciente[:10]  # Top 10
        
        context = {
            'usuario': request.user,
            'stats': stats,
            'actividad_reciente': actividad_reciente,
            'roles_disponibles': Usuario.ROLES,
        }
        
        print(f"📊 Estadísticas calculadas para {request.user.username}: {stats}")
        
        return render(request, 'anomalias/perfil_usuario.html', context)
        
    except Exception as e:
        print(f"❌ Error en perfil_usuario: {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Error cargando perfil: {str(e)}')
        
        # Contexto mínimo en caso de error
        context = {
            'usuario': request.user,
            'stats': {},
            'actividad_reciente': [],
            'error': True
        }
        
        return render(request, 'anomalias/perfil_usuario.html', context)

# Vista para exportar derivaciones
@login_required
@user_passes_test(lambda u: u.rol in ['coordinador_cpa', 'analista_cpa', 'coordinador_carrera'])
def exportar_reporte_derivaciones(request):
    """
    🔧 FUNCIÓN CORREGIDA: Exportar reporte de derivaciones
    """
    try:
        queryset = Derivacion.objects.select_related(
            'deteccion_anomalia__estudiante',
            'deteccion_anomalia__estudiante__carrera',
            'instancia_apoyo',
            'derivado_por'
        ).order_by('-fecha_derivacion')
        
        # Filtrar por carrera si es coordinador de carrera
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                queryset = queryset.filter(deteccion_anomalia__estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                messages.error(request, "Usuario sin carrera asignada.")
                return redirect('gestionar_derivaciones')
        
        if not queryset.exists():
            messages.warning(request, "No hay derivaciones para exportar.")
            return redirect('gestionar_derivaciones')
        
        # Preparar datos
        data = []
        for derivacion in queryset:
            # 🔧 MANEJO SEGURO DE PRIORIDAD
            try:
                prioridad_display = derivacion.get_prioridad_display()
            except AttributeError:
                # Si no existe prioridad en derivación, usar la de la anomalía
                prioridad_display = f"Prioridad {derivacion.deteccion_anomalia.prioridad}"
            
            # 🔧 MANEJO SEGURO DE OBSERVACIONES
            observaciones = getattr(derivacion, 'observaciones_seguimiento', None) or derivacion.observaciones_derivacion or 'Sin observaciones'
            
            data.append({
                'ID Derivación': derivacion.id,
                'ID Estudiante': derivacion.deteccion_anomalia.estudiante.id_estudiante,
                'Nombre Estudiante': derivacion.deteccion_anomalia.estudiante.nombre,
                'Carrera': derivacion.deteccion_anomalia.estudiante.carrera.nombre if derivacion.deteccion_anomalia.estudiante.carrera else 'N/A',
                'Tipo Anomalía': derivacion.deteccion_anomalia.get_tipo_anomalia_display(),
                'Instancia Apoyo': derivacion.instancia_apoyo.nombre,
                'Estado Derivación': derivacion.get_estado_display(),
                'Prioridad': prioridad_display,  # 🔧 CORREGIDO
                'Motivo': derivacion.motivo,
                'Fecha Derivación': derivacion.fecha_derivacion.strftime('%Y-%m-%d %H:%M'),
                'Derivado Por': derivacion.derivado_por.get_full_name() if derivacion.derivado_por else 'N/A',
                'Observaciones': observaciones[:500]  # 🔧 CORREGIDO - Limitar longitud
            })
        
        # Crear Excel
        import pandas as pd
        from io import BytesIO
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Derivaciones', index=False)
        
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        filename = f"reporte_derivaciones_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        messages.success(request, f'Reporte de derivaciones exportado: {filename}')
        return response
        
    except Exception as e:
        print(f"❌ Error exportando derivaciones: {str(e)}")
        messages.error(request, f'Error generando reporte: {str(e)}')
        return redirect('gestionar_derivaciones')

# Vista para actualizar estado de derivación CORREGIDA
@login_required
@user_passes_test(lambda u: u.rol in ['analista_cpa', 'coordinador_cpa'])
def actualizar_estado_derivacion(request, derivacion_id):
    """
    🔧 FUNCIÓN CORREGIDA: Actualizar estado de derivación
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        derivacion = get_object_or_404(Derivacion, id=derivacion_id)
        
        nuevo_estado = request.POST.get('estado')
        observaciones = request.POST.get('observaciones', '')
        
        if nuevo_estado not in dict(Derivacion.ESTADOS_DERIVACION):
            return JsonResponse({'error': 'Estado inválido'}, status=400)
        
        # Actualizar derivación
        estado_anterior = derivacion.get_estado_display()
        derivacion.estado = nuevo_estado
        
        # 🔧 AGREGAR OBSERVACIONES AL CAMPO CORRECTO
        if observaciones:
            timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
            usuario = request.user.get_full_name() or request.user.username
            nueva_observacion = f"[{timestamp}] {usuario}: {observaciones}"
            
            # Verificar si existe campo observaciones_seguimiento
            if hasattr(derivacion, 'observaciones_seguimiento'):
                # Si existe el campo, usarlo
                if derivacion.observaciones_seguimiento:
                    derivacion.observaciones_seguimiento += f"\n\n{nueva_observacion}"
                else:
                    derivacion.observaciones_seguimiento = nueva_observacion
            else:
                # Si no existe, usar observaciones_derivacion
                if derivacion.observaciones_derivacion:
                    derivacion.observaciones_derivacion += f"\n\n{nueva_observacion}"
                else:
                    derivacion.observaciones_derivacion = f"SEGUIMIENTO:\n{nueva_observacion}"
        
        derivacion.save()
        
        # Si la derivación se completa, actualizar la anomalía
        if nuevo_estado == 'completada':
            derivacion.deteccion_anomalia.estado = 'resuelto'
            derivacion.deteccion_anomalia.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Estado actualizado de "{estado_anterior}" a "{derivacion.get_estado_display()}"',
            'nuevo_estado': nuevo_estado,
            'nuevo_estado_display': derivacion.get_estado_display()
        })
        
    except Exception as e:
        print(f"❌ Error actualizando derivación: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# Vista para eliminar criterio NUEVA
@login_required
@user_passes_test(lambda u: u.rol == 'coordinador_cpa')
def eliminar_criterio(request, criterio_id):
    """🗑️ Eliminar criterio de detección"""
    try:
        criterio = get_object_or_404(CriterioAnomalia, id=criterio_id)
        
        # Verificar si el criterio tiene anomalías asociadas
        anomalias_asociadas = DeteccionAnomalia.objects.filter(criterio_usado=criterio).count()
        
        if request.method == 'POST':
            confirmar = request.POST.get('confirmar') == 'true'
            
            if confirmar:
                nombre_criterio = criterio.nombre
                
                if anomalias_asociadas > 0:
                    # No eliminar, solo desactivar
                    criterio.activo = False
                    criterio.save()
                    
                    messages.success(
                        request,
                        f'Criterio "{nombre_criterio}" desactivado exitosamente. '
                        f'Se mantiene para preservar el historial de {anomalias_asociadas} anomalías.'
                    )
                else:
                    # Eliminar completamente
                    criterio.delete()
                    
                    messages.success(
                        request,
                        f'Criterio "{nombre_criterio}" eliminado exitosamente.'
                    )
                
                return redirect('configuracion_criterios')
            else:
                messages.error(request, 'Eliminación cancelada.')
                return redirect('detalle_criterio', criterio_id=criterio_id)
        
        # Mostrar confirmación
        context = {
            'criterio': criterio,
            'anomalias_asociadas': anomalias_asociadas,
            'puede_eliminar': anomalias_asociadas == 0
        }
        
        return render(request, 'anomalias/confirmar_eliminar_criterio.html', context)
        
    except Exception as e:
        print(f"❌ Error eliminando criterio: {str(e)}")
        messages.error(request, f'Error eliminando criterio: {str(e)}')
        return redirect('configuracion_criterios')
    
# APIs para gráficos de verificación del sistema
@login_required
def api_distribucion_carrera(request):
    """
    📊 API para obtener distribución de estudiantes por carrera
    """
    try:
        # Contar estudiantes por carrera
        distribucion = Estudiante.objects.filter(activo=True).values(
            'carrera__nombre'
        ).annotate(
            total=Count('id')
        ).order_by('-total')
        
        # Preparar datos para el gráfico
        datos_grafico = {
            'labels': [],
            'datasets': [{
                'data': [],
                'backgroundColor': [
                    '#FF6384',
                    '#36A2EB', 
                    '#FFCE56',
                    '#4BC0C0',
                    '#9966FF',
                    '#FF9F40',
                    '#FF6384',
                    '#C9CBCF'
                ]
            }]
        }
        
        for item in distribucion:
            carrera_nombre = item['carrera__nombre'] or 'Sin Carrera'
            datos_grafico['labels'].append(carrera_nombre)
            datos_grafico['datasets'][0]['data'].append(item['total'])
        
        return JsonResponse({
            'success': True,
            'data': datos_grafico,
            'total_carreras': len(datos_grafico['labels']),
            'total_estudiantes': sum(datos_grafico['datasets'][0]['data'])
        })
        
    except Exception as e:
        print(f"❌ Error en api_distribucion_carrera: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def api_registros_semestre(request):
    """
    📈 API CORREGIDA para obtener registros académicos por semestre
    """
    try:
        print("📊 Generando datos de registros por semestre...")
        
        # Contar registros por semestre de las asignaturas - MÉTODO ALTERNATIVO
        try:
            # Método 1: Intentar consulta directa
            registros_semestre = RegistroAcademico.objects.select_related('asignatura').values(
                'asignatura__semestre'
            ).annotate(
                total_registros=Count('id'),
                estudiantes_unicos=Count('estudiante', distinct=True)
            ).order_by('asignatura__semestre')
            
            print(f"📊 Método 1 - Registros encontrados: {registros_semestre.count()}")
            
        except Exception as e:
            print(f"⚠️ Método 1 falló, intentando método alternativo: {e}")
            
            # Método 2: Consulta más básica
            registros_semestre = []
            
            # Obtener semestres únicos
            semestres_disponibles = Asignatura.objects.values_list(
                'semestre', flat=True
            ).distinct().order_by('semestre')
            
            print(f"📊 Semestres encontrados: {list(semestres_disponibles)}")
            
            for semestre in semestres_disponibles:
                if semestre is not None:
                    # Contar registros para este semestre
                    asignaturas_semestre = Asignatura.objects.filter(semestre=semestre)
                    total_registros = RegistroAcademico.objects.filter(
                        asignatura__in=asignaturas_semestre
                    ).count()
                    
                    estudiantes_unicos = RegistroAcademico.objects.filter(
                        asignatura__in=asignaturas_semestre
                    ).values('estudiante').distinct().count()
                    
                    registros_semestre.append({
                        'asignatura__semestre': semestre,
                        'total_registros': total_registros,
                        'estudiantes_unicos': estudiantes_unicos
                    })
        
        # Preparar datos para el gráfico
        datos_grafico = {
            'labels': [],
            'datasets': [{
                'label': 'Registros Académicos',
                'data': [],
                'backgroundColor': '#36A2EB',
                'borderColor': '#1E88E5',
                'borderWidth': 1
            }]
        }
        
        total_registros_global = 0
        total_semestres = 0
        
        for item in registros_semestre:
            semestre = item['asignatura__semestre'] if isinstance(item, dict) else item.get('asignatura__semestre')
            total_registros = item['total_registros'] if isinstance(item, dict) else item.get('total_registros', 0)
            
            if semestre is not None and total_registros > 0:
                datos_grafico['labels'].append(f'Semestre {semestre}')
                datos_grafico['datasets'][0]['data'].append(total_registros)
                total_registros_global += total_registros
                total_semestres += 1
        
        print(f"📊 Datos preparados - Semestres: {total_semestres}, Registros: {total_registros_global}")
        
        # Si no hay datos, crear datos por defecto
        if total_semestres == 0:
            print("⚠️ No se encontraron datos, generando estructura por defecto...")
            
            # Verificar si hay asignaturas
            total_asignaturas = Asignatura.objects.count()
            total_registros_db = RegistroAcademico.objects.count()
            
            if total_asignaturas == 0:
                datos_grafico = {
                    'labels': ['Sin Datos'],
                    'datasets': [{
                        'label': 'Registros Académicos',
                        'data': [0],
                        'backgroundColor': '#DC3545',
                        'borderColor': '#DC3545',
                        'borderWidth': 1
                    }]
                }
            else:
                # Hay asignaturas pero sin semestre definido
                datos_grafico = {
                    'labels': ['Semestre No Definido'],
                    'datasets': [{
                        'label': 'Registros Académicos',
                        'data': [total_registros_db],
                        'backgroundColor': '#FFC107',
                        'borderColor': '#FFC107',
                        'borderWidth': 1
                    }]
                }
                total_semestres = 1
                total_registros_global = total_registros_db
        
        response_data = {
            'success': True,
            'data': datos_grafico,
            'total_semestres': total_semestres,
            'total_registros': total_registros_global,
            'debug_info': {
                'total_asignaturas': Asignatura.objects.count(),
                'total_registros_db': RegistroAcademico.objects.count(),
                'semestres_unicos': list(Asignatura.objects.values_list('semestre', flat=True).distinct()),
                'mensaje': 'Datos generados correctamente'
            }
        }
        
        print(f"✅ API registros semestre completada exitosamente")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"❌ Error en api_registros_semestre: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'debug_info': {
                'total_asignaturas': Asignatura.objects.count() if 'Asignatura' in globals() else 0,
                'total_registros': RegistroAcademico.objects.count() if 'RegistroAcademico' in globals() else 0,
                'error_type': type(e).__name__
            }
        }, status=500)

@login_required
@user_passes_test(lambda u: u.rol == 'coordinador_cpa')
def api_probar_analisis(request):
    """
    🧪 API para probar la funcionalidad de análisis de anomalías
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        print("🧪 Iniciando prueba de análisis...")
        
        # Verificar si hay criterios activos
        criterios_activos = CriterioAnomalia.objects.filter(activo=True)
        
        if not criterios_activos.exists():
            return JsonResponse({
                'success': False,
                'error': 'No hay criterios activos para probar',
                'sugerencias': [
                    'Crear al menos un criterio de detección',
                    'Verificar que el criterio esté marcado como activo'
                ]
            })
        
        # Usar el primer criterio activo para la prueba
        criterio_prueba = criterios_activos.first()
        print(f"🎯 Probando con criterio: {criterio_prueba.nombre}")
        
        # Verificar datos disponibles
        total_estudiantes = Estudiante.objects.filter(activo=True).count()
        total_registros = RegistroAcademico.objects.count()
        
        if total_estudiantes < 5:
            return JsonResponse({
                'success': False,
                'error': 'Insuficientes estudiantes para prueba (mínimo 5)',
                'datos_actuales': {
                    'estudiantes': total_estudiantes,
                    'registros': total_registros
                }
            })
        
        if total_registros < 10:
            return JsonResponse({
                'success': False,
                'error': 'Insuficientes registros académicos para prueba (mínimo 10)',
                'datos_actuales': {
                    'estudiantes': total_estudiantes,
                    'registros': total_registros
                }
            })
        
        # Importar la función de detección
        from .utils import ejecutar_deteccion_anomalias
        
        # Ejecutar análisis de prueba
        print("🚀 Ejecutando análisis de prueba...")
        resultado = ejecutar_deteccion_anomalias(criterio_prueba, request.user)
        
        if resultado['exitoso']:
            return JsonResponse({
                'success': True,
                'mensaje': 'Análisis de prueba completado exitosamente',
                'resultados': {
                    'anomalias_detectadas': resultado['anomalias_detectadas'],
                    'total_estudiantes': resultado.get('total_estudiantes', 0),
                    'porcentaje_anomalias': resultado.get('porcentaje_anomalias', 0),
                    'tiempo_ejecucion': resultado.get('tiempo_ejecucion', 0)
                },
                'criterio_usado': {
                    'id': criterio_prueba.id,
                    'nombre': criterio_prueba.nombre
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': resultado.get('error', 'Error desconocido en análisis'),
                'detalles': resultado
            })
        
    except ImportError as e:
        print(f"❌ Error de importación: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error importando módulo de análisis',
            'detalles': str(e),
            'solucion': 'Verificar que utils.py esté configurado correctamente'
        }, status=500)
        
    except Exception as e:
        print(f"❌ Error en api_probar_analisis: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'tipo_error': type(e).__name__
        }, status=500)

@login_required
def api_datos_tiempo_real(request):
    """
    ⏱️ API mejorada para datos en tiempo real
    """
    try:
        # Métricas básicas
        estudiantes = Estudiante.objects.filter(activo=True)
        anomalias = DeteccionAnomalia.objects.all()
        
        # Filtrar por rol si es necesario
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                estudiantes = estudiantes.filter(carrera=carrera)
                anomalias = anomalias.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                pass
        
        # Calcular métricas
        total_estudiantes = estudiantes.count()
        total_anomalias = anomalias.count()
        anomalias_activas = anomalias.filter(
            estado__in=['detectado', 'en_revision', 'intervencion_activa']
        ).count()
        anomalias_criticas = anomalias.filter(
            prioridad__gte=4,
            estado__in=['detectado', 'en_revision', 'intervencion_activa']
        ).count()
        
        # Derivaciones pendientes
        derivaciones_pendientes = Derivacion.objects.filter(
            estado__in=['pendiente', 'enviada']
        ).count()
        
        return JsonResponse({
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'metricas': {
                'total_estudiantes': total_estudiantes,
                'total_anomalias': total_anomalias,
                'anomalias_activas': anomalias_activas,
                'anomalias_criticas': anomalias_criticas,
                'derivaciones_pendientes': derivaciones_pendientes,
                'tasa_anomalias': round((total_anomalias / total_estudiantes * 100), 2) if total_estudiantes > 0 else 0
            }
        })
        
    except Exception as e:
        print(f"❌ Error en api_datos_tiempo_real: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def api_alertas_count(request):
    """🔔 API para contar alertas no leídas del usuario - VERSIÓN ACTIVADA"""
    try:
        # Implementación real del conteo de alertas
        alertas_count = 0
        
        # Contar alertas automáticas no leídas
        if hasattr(request.user, 'alertaautomatica_destinatarios'):
            alertas_count += request.user.alertaautomatica_destinatarios.filter(
                leida=False,
                activa=True
            ).count()
        
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
                'derivaciones_pendientes': derivaciones_pendientes if request.user.rol in ['analista_cpa', 'coordinador_cpa'] else 0
            }
        })
        
    except Exception as e:
        print(f"❌ Error en api_alertas_count: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'count': 0
        }, status=500)

@login_required
def api_progreso_analisis(request, ejecucion_id):
    """
    📊 API para monitorear progreso de análisis
    """
    try:
        ejecucion = get_object_or_404(EjecucionAnalisis, id=ejecucion_id)
        
        # Simular progreso basado en tiempo transcurrido
        tiempo_transcurrido = (timezone.now() - ejecucion.fecha_ejecucion).total_seconds()
        
        if ejecucion.exitoso and ejecucion.tiempo_ejecucion:
            # Análisis completado
            progreso = 100
            mensaje = "Análisis completado exitosamente"
            detalle = f"{ejecucion.anomalias_detectadas} anomalías detectadas"
            completado = True
        elif tiempo_transcurrido > 60:  # Más de 1 minuto
            # Probablemente falló
            progreso = 0
            mensaje = "El análisis parece haber fallado"
            detalle = "Tiempo de espera agotado"
            completado = True
        else:
            # En progreso
            progreso = min(int((tiempo_transcurrido / 30) * 100), 95)  # 30 segundos para completar
            mensaje = "Analizando datos de estudiantes..."
            detalle = f"Procesando... {progreso}%"
            completado = False
        
        return JsonResponse({
            'success': True,
            'progreso': progreso,
            'mensaje': mensaje,
            'detalle': detalle,
            'completado': completado,
            'exitoso': ejecucion.exitoso if completado else None,
            'anomalias_detectadas': ejecucion.anomalias_detectadas if completado else None,
            'tiempo_ejecucion': ejecucion.tiempo_ejecucion if completado else None
        })
        
    except Exception as e:
        print(f"❌ Error en api_progreso_analisis: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'completado': True,
            'exitoso': False
        }, status=500)

@login_required
def api_estadisticas_distribucion(request):
    """
    📊 API para estadísticas de distribución completas del sistema - JSON SAFE
    """
    try: 
        print("📊 Generando estadísticas de distribución...")
        
        # 1. Distribución por carrera - CORREGIDO
        distribucion_carreras = Estudiante.objects.filter(activo=True).values(
            'carrera__nombre'
        ).annotate(
            total=Count('id_estudiante'),
            con_anomalias=Count('deteccionanomalia', distinct=True)
        ).order_by('-total')
        
        carreras_data = []
        for item in distribucion_carreras:
            carrera_nombre = item['carrera__nombre'] or 'Sin Carrera'
            total = item['total']
            con_anomalias = item['con_anomalias']
            porcentaje_anomalias = round((con_anomalias / total * 100), 2) if total > 0 else 0
            
            carreras_data.append({
                'nombre': carrera_nombre,
                'total_estudiantes': total,
                'estudiantes_con_anomalias': con_anomalias,
                'porcentaje_anomalias': porcentaje_anomalias
            })
        
        # 2. Distribución por semestre
        distribucion_semestres = RegistroAcademico.objects.values(
            'asignatura__semestre'
        ).annotate(
            total_registros=Count('id'),
            estudiantes_unicos=Count('estudiante', distinct=True)
        ).order_by('asignatura__semestre')
        
        semestres_data = []
        for item in distribucion_semestres:
            semestre = item['asignatura__semestre'] or 0
            semestres_data.append({
                'semestre': semestre,
                'total_registros': item['total_registros'],
                'estudiantes_unicos': item['estudiantes_unicos']
            })
        
        # 3. Distribución por tipo de anomalía
        distribucion_anomalias = DeteccionAnomalia.objects.values(
            'tipo_anomalia'
        ).annotate(
            total=Count('id')
        ).order_by('-total')
        
        anomalias_data = []
        for item in distribucion_anomalias:
            tipo_display = dict(DeteccionAnomalia.TIPOS_ANOMALIA).get(
                item['tipo_anomalia'], 
                item['tipo_anomalia']
            )
            anomalias_data.append({
                'tipo': item['tipo_anomalia'],
                'tipo_display': tipo_display,
                'total': item['total']
            })
        
        # 4. Distribución por estado de anomalías
        distribucion_estados = DeteccionAnomalia.objects.values(
            'estado'
        ).annotate(
            total=Count('id')
        ).order_by('-total')
        
        estados_data = []
        for item in distribucion_estados:
            estado_display = dict(DeteccionAnomalia.ESTADOS).get(
                item['estado'], 
                item['estado']
            )
            estados_data.append({
                'estado': item['estado'],
                'estado_display': estado_display,
                'total': item['total']
            })
        
        # 5. Estadísticas de derivaciones
        total_derivaciones = Derivacion.objects.count()
        derivaciones_por_estado = Derivacion.objects.values(
            'estado'
        ).annotate(
            total=Count('id')
        )
        
        derivaciones_data = []
        # Estados por defecto si no existen en el modelo
        estados_derivacion_default = [
            ('pendiente', 'Pendiente'),
            ('enviada', 'Enviada'),
            ('en_proceso', 'En Proceso'),
            ('completada', 'Completada'),
            ('cancelada', 'Cancelada')
        ]
        
        for item in derivaciones_por_estado:
            estado_display = dict(estados_derivacion_default).get(
                item['estado'], 
                item['estado']
            )
            derivaciones_data.append({
                'estado': item['estado'],
                'estado_display': estado_display,
                'total': item['total']
            })
        
        # 6. Métricas generales del sistema - SOLO DATOS SERIALIZABLES
        total_estudiantes = Estudiante.objects.filter(activo=True).count()
        total_registros = RegistroAcademico.objects.count()
        total_anomalias = DeteccionAnomalia.objects.count()
        total_carreras = Carrera.objects.count()
        total_asignaturas = Asignatura.objects.count()
        criterios_activos = CriterioAnomalia.objects.filter(activo=True).count()
        
        # Obtener fechas de última actividad - CONVERTIR A STRING
        ultima_deteccion_obj = DeteccionAnomalia.objects.order_by('-fecha_deteccion').first()
        ultima_derivacion_obj = Derivacion.objects.order_by('-fecha_derivacion').first()
        
        # Convertir a strings serializables
        ultima_deteccion_fecha = 'Sin detecciones'
        if ultima_deteccion_obj:
            ultima_deteccion_fecha = ultima_deteccion_obj.fecha_deteccion.strftime('%d/%m/%Y %H:%M')
        
        ultima_derivacion_fecha = 'Sin derivaciones'
        if ultima_derivacion_obj:
            ultima_derivacion_fecha = ultima_derivacion_obj.fecha_derivacion.strftime('%d/%m/%Y %H:%M')
        
        metricas_generales = {
            'total_estudiantes': total_estudiantes,
            'total_registros': total_registros,
            'total_anomalias': total_anomalias,
            'total_derivaciones': total_derivaciones,
            'total_carreras': total_carreras,
            'total_asignaturas': total_asignaturas,
            'criterios_activos': criterios_activos,
            'ultima_deteccion_fecha': ultima_deteccion_fecha,
            'ultima_derivacion_fecha': ultima_derivacion_fecha
        }
        
        # 7. Calcular tasas y ratios
        ratios = {
            'tasa_anomalias_global': round((total_anomalias / total_estudiantes * 100), 2) if total_estudiantes > 0 else 0,
            'registros_por_estudiante': round((total_registros / total_estudiantes), 2) if total_estudiantes > 0 else 0,
            'derivaciones_por_anomalia': round((total_derivaciones / total_anomalias), 2) if total_anomalias > 0 else 0
        }
        
        # Preparar respuesta completa - SOLO DATOS SERIALIZABLES
        response_data = {
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'metricas_generales': metricas_generales,
            'ratios': ratios,
            'distribuciones': {
                'carreras': carreras_data,
                'semestres': semestres_data,
                'tipos_anomalia': anomalias_data,
                'estados_anomalia': estados_data,
                'derivaciones': derivaciones_data
            }
        }
        
        print("✅ Estadísticas de distribución generadas exitosamente")
        print(f"   Total estudiantes: {total_estudiantes}")
        print(f"   Total carreras: {len(carreras_data)}")
        print(f"   Total semestres: {len(semestres_data)}")
        print(f"   Total anomalías: {total_anomalias}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"❌ Error en api_estadisticas_distribucion: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Respuesta de error también serializable
        error_response = {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'timestamp': timezone.now().isoformat(),
            'debug_info': {
                'message': 'Error en consulta de base de datos',
                'estudiante_fields': [f.name for f in Estudiante._meta.get_fields()]
            }
        }
        
        return JsonResponse(error_response, status=500)

@login_required  
def api_datos_dashboard(request):
    """
    📈 API completa para datos del dashboard con evolución temporal y tipos de anomalías
    
    Como estudiante de informática, es importante entender que esta función:
    1. Consulta la base de datos para obtener anomalías
    2. Procesa los datos para crear estructuras apropiadas para los gráficos
    3. Retorna JSON que el frontend (JavaScript) puede consumir
    """ 
    try:
        print("🔄 Generando datos para dashboard...")

        # Filtrar anomalías según el rol del usuario
        anomalias_base = DeteccionAnomalia.objects.all()
        
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                anomalias_base = anomalias_base.filter(estudiante__carrera=carrera)
                print(f"👨‍🎓 Filtrando por carrera: {carrera.nombre}")
            except Carrera.DoesNotExist:
                pass
        
        # 1. EVOLUCIÓN TEMPORAL (últimos 30 días)
        # Esta parte genera datos para el gráfico de líneas que muestra cómo evolucionan las anomalías en el tiempo
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=30)
        
        # Generar lista de fechas (una por cada día)
        fechas_periodo = []
        fecha_actual = fecha_inicio
        while fecha_actual <= fecha_fin:
            fechas_periodo.append(fecha_actual)
            fecha_actual += timedelta(days=1)
        
        # Contar anomalías por día
        evolucion_temporal = {
            'fechas': [],
            'counts': []
        }
         
        for fecha in fechas_periodo:
            # Contar anomalías detectadas en esta fecha específica
            count = anomalias_base.filter(
                fecha_deteccion__date=fecha
            ).count()
            
            evolucion_temporal['fechas'].append(fecha.strftime('%d/%m'))
            evolucion_temporal['counts'].append(count)
        
        print(f"📈 Evolución temporal: {sum(evolucion_temporal['counts'])} anomalías en 30 días")
        
        # 2. TIPOS DE ANOMALÍAS
        # Esta consulta agrupa las anomalías por tipo y cuenta cuántas hay de cada tipo
        anomalias_por_tipo = list(
            anomalias_base.values('tipo_anomalia')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Agregar etiquetas más descriptivas para los tipos de anomalía
        tipo_labels = {
            'bajo_rendimiento': 'Bajo Rendimiento',
            'alta_inasistencia': 'Alta Inasistencia',
            'bajo_uso_plataforma': 'Bajo Uso de Plataforma',
            'multiple': 'Múltiples Factores',
            'riesgo_desercion': 'Riesgo de Deserción'
        }
        
        # Formatear datos para el gráfico de dona/pastel
        for item in anomalias_por_tipo:
            tipo_raw = item['tipo_anomalia']
            item['tipo_anomalia'] = tipo_labels.get(tipo_raw, tipo_raw.replace('_', ' ').title())
        
        print(f"🎯 Tipos de anomalías: {len(anomalias_por_tipo)} tipos diferentes")
        
        # 3. ESTADÍSTICAS ADICIONALES (opcional, para futuras mejoras)
        total_anomalias = anomalias_base.count()
        anomalias_mes_actual = anomalias_base.filter(
            fecha_deteccion__month=timezone.now().month,
            fecha_deteccion__year=timezone.now().year
        ).count()
        
        # Crear la respuesta JSON
        response_data = {
            'success': True,
            'evolucion_temporal': evolucion_temporal,
            'anomalias_por_tipo': anomalias_por_tipo,
            'estadisticas': {
                'total_anomalias': total_anomalias,
                'anomalias_mes_actual': anomalias_mes_actual,
                'promedio_diario': round(sum(evolucion_temporal['counts']) / 30, 1)
            },
            'timestamp': timezone.now().isoformat()
        }
        
        print("✅ Datos del dashboard generados exitosamente")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"❌ Error en api_datos_dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # En caso de error, retornar datos vacíos pero válidos para que el frontend no falle
        error_response = {
            'success': False,
            'error': str(e),
            'evolucion_temporal': {
                'fechas': [],
                'counts': []
            },
            'anomalias_por_tipo': [],
            'estadisticas': {
                'total_anomalias': 0,
                'anomalias_mes_actual': 0,
                'promedio_diario': 0
            },
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(error_response, status=500)

@login_required
def api_evolucion_anomalias(request):
    """
    📈 API específica para evolución temporal de anomalías
    
    Esta función es útil para entender cómo separar responsabilidades:
    - Una API general (api_datos_dashboard) para datos múltiples
    - APIs específicas (como esta) para casos particulares
    """
    try:
        # Obtener parámetros de la URL (opcional)
        dias = int(request.GET.get('dias', 30))  # Por defecto 30 días
        
        # Filtrar anomalías según usuario
        anomalias = DeteccionAnomalia.objects.all()
        
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                anomalias = anomalias.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                pass
        
        # Calcular rango de fechas
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=dias)
        
        # Agrupar por fecha y contar
        evolucion = anomalias.filter(
            fecha_deteccion__date__gte=fecha_inicio,
            fecha_deteccion__date__lte=fecha_fin
        ).extra(
            select={'dia': 'date(fecha_deteccion)'}
        ).values('dia').annotate(
            total=Count('id')
        ).order_by('dia')
        
        # Preparar datos para Chart.js
        response_data = {
            'labels': [item['dia'].strftime('%d/%m/%Y') for item in evolucion],
            'datasets': [{
                'label': 'Anomalías Detectadas',
                'data': [item['total'] for item in evolucion],
                'borderColor': '#3498db',
                'backgroundColor': 'rgba(52, 152, 219, 0.1)',
                'tension': 0.4,
                'fill': True
            }]
        }
        
        return JsonResponse({
            'success': True,
            'chart_data': response_data,
            'total_anomalias': sum(item['total'] for item in evolucion),
            'periodo_dias': dias
        })
        
    except Exception as e:
        print(f"❌ Error en api_evolucion_anomalias: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def api_tipos_anomalias(request):
    """
    🎯 API específica para distribución de tipos de anomalías
    
    Concepto clave: Esta función demuestra cómo usar agregaciones en Django ORM
    - values(): especifica qué campos agrupar
    - annotate(): aplica funciones de agregación (Count, Sum, Avg, etc.)
    - order_by(): ordena los resultados
    """
    try:
        # Filtrar anomalías según usuario
        anomalias = DeteccionAnomalia.objects.all()
        
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                anomalias = anomalias.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                pass
        
        # Agrupar por tipo de anomalía
        tipos_data = anomalias.values('tipo_anomalia').annotate(
            total=Count('id')
        ).order_by('-total')
        
        # Mapeo de tipos a etiquetas más amigables
        tipo_labels = {
            'bajo_rendimiento': 'Bajo Rendimiento',
            'alta_inasistencia': 'Alta Inasistencia', 
            'bajo_uso_plataforma': 'Bajo Uso de Plataforma',
            'multiple': 'Múltiples Factores',
            'riesgo_desercion': 'Riesgo de Deserción'
        }
        
        # Colores predefinidos para el gráfico
        colores = [
            '#e74c3c',  # Rojo
            '#f39c12',  # Naranja
            '#3498db',  # Azul
            '#27ae60',  # Verde
            '#9b59b6',  # Púrpura
            '#34495e'   # Gris oscuro
        ]
        
        # Preparar datos para Chart.js (gráfico de dona/pastel)
        labels = []
        data = []
        backgroundColor = []
        
        for i, item in enumerate(tipos_data):
            tipo_raw = item['tipo_anomalia']
            etiqueta = tipo_labels.get(tipo_raw, tipo_raw.replace('_', ' ').title())
            
            labels.append(etiqueta)
            data.append(item['total'])
            backgroundColor.append(colores[i % len(colores)])
        
        response_data = {
            'labels': labels,
            'datasets': [{
                'data': data,
                'backgroundColor': backgroundColor,
                'borderWidth': 2,
                'borderColor': '#ffffff'
            }]
        }
        
        return JsonResponse({
            'success': True,
            'chart_data': response_data,
            'total_tipos': len(labels),
            'total_anomalias': sum(data)
        })
        
    except Exception as e:
        print(f"❌ Error en api_tipos_anomalias: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def debug_models_info(request):
    """
    🔍 Función de debug para inspeccionar modelos (solo para desarrollo)
    """
    try:
        info = {
            'estudiante_fields': [f.name for f in Estudiante._meta.get_fields()],
            'deteccion_anomalia_fields': [f.name for f in DeteccionAnomalia._meta.get_fields()],
            'registro_academico_fields': [f.name for f in RegistroAcademico._meta.get_fields()],
            'derivacion_fields': [f.name for f in Derivacion._meta.get_fields()],
            'total_estudiantes': Estudiante.objects.count(),
            'total_anomalias': DeteccionAnomalia.objects.count(),
            'ejemplo_estudiante': None,
            'ejemplo_anomalia': None
        }
        
        # Agregar ejemplos si existen registros
        estudiante_ejemplo = Estudiante.objects.first()
        if estudiante_ejemplo:
            info['ejemplo_estudiante'] = {
                'id_estudiante': estudiante_ejemplo.id_estudiante,
                'nombre': estudiante_ejemplo.nombre,
                'carrera': str(estudiante_ejemplo.carrera) if estudiante_ejemplo.carrera else None
            }
        
        anomalia_ejemplo = DeteccionAnomalia.objects.first()
        if anomalia_ejemplo:
            info['ejemplo_anomalia'] = {
                'id': anomalia_ejemplo.id,
                'tipo_anomalia': anomalia_ejemplo.tipo_anomalia,
                'estado': anomalia_ejemplo.estado,
                'fecha_deteccion': anomalia_ejemplo.fecha_deteccion.isoformat()
            }
        
        return JsonResponse({
            'success': True,
            'debug_info': info,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@user_passes_test(lambda u: u.rol in ['analista_cpa', 'coordinador_cpa', 'coordinador_carrera'])
def exportar_todas_anomalias(request):
    """
    🔧 FUNCIÓN CORREGIDA: Exportar TODAS las anomalías 
    """
    try:
        print(f"\n📊 === EXPORTACIÓN COMPLETA ===")
        print(f"Usuario: {request.user.username} ({request.user.rol})")
        print(f"Parámetros GET: {dict(request.GET)}")
        
        # Empezar con TODAS las anomalías
        queryset = DeteccionAnomalia.objects.select_related(
            'estudiante', 'estudiante__carrera', 'criterio_usado', 'revisado_por'
        ).order_by('-fecha_deteccion')
        
        print(f"📊 Anomalías iniciales: {queryset.count()}")
        
        # IMPORTANTE: Para coordinador_cpa, NO filtrar por carrera automáticamente
        # Solo filtrar si es coordinador_carrera
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                queryset = queryset.filter(estudiante__carrera=carrera)
                print(f"👨‍🎓 Filtrado por carrera {carrera.nombre}: {queryset.count()} anomalías")
            except Carrera.DoesNotExist:
                messages.error(request, "Usuario sin carrera asignada.")
                return redirect('listado_anomalias')
        else:
            print(f"👑 Usuario {request.user.rol} - acceso a todas las anomalías")
        
        # APLICAR SOLO LOS FILTROS QUE REALMENTE EXISTEN
        filtros_aplicados = []
        
        # 1. Filtro por estado (solo si existe y no está vacío)
        estado = request.GET.get('estado')
        if estado and estado.strip():
            queryset = queryset.filter(estado=estado)
            filtros_aplicados.append(f"estado={estado}")
            print(f"🔍 Filtro estado '{estado}': {queryset.count()} anomalías")
        
        # 2. Filtro por tipo de anomalía (solo si existe y no está vacío)
        tipo = request.GET.get('tipo')
        if tipo and tipo.strip():
            queryset = queryset.filter(tipo_anomalia=tipo)
            filtros_aplicados.append(f"tipo={tipo}")
            print(f"🔍 Filtro tipo '{tipo}': {queryset.count()} anomalías")
        
        # 3. Filtro por prioridad (solo si existe y no está vacío)
        prioridad = request.GET.get('prioridad')
        if prioridad and prioridad.strip():
            try:
                prioridad_int = int(prioridad)
                queryset = queryset.filter(prioridad=prioridad_int)
                filtros_aplicados.append(f"prioridad={prioridad_int}")
                print(f"🔍 Filtro prioridad {prioridad_int}: {queryset.count()} anomalías")
            except ValueError:
                print(f"❌ Prioridad inválida ignorada: {prioridad}")
        
        # 4. Filtro por carrera (solo para coordinadores CPA y si existe)
        carrera_filtro = request.GET.get('carrera')
        if carrera_filtro and carrera_filtro.strip() and request.user.rol in ['coordinador_cpa', 'analista_cpa']:
            try:
                carrera_obj = Carrera.objects.get(id=carrera_filtro)
                queryset = queryset.filter(estudiante__carrera=carrera_obj)
                filtros_aplicados.append(f"carrera={carrera_obj.nombre}")
                print(f"🔍 Filtro carrera '{carrera_obj.nombre}': {queryset.count()} anomalías")
            except (Carrera.DoesNotExist, ValueError):
                print(f"❌ Carrera inválida ignorada: {carrera_filtro}")
        
        # 5. Filtro por búsqueda (solo si existe y no está vacío)
        buscar = request.GET.get('buscar')
        if buscar and buscar.strip():
            queryset = queryset.filter(
                Q(estudiante__nombre__icontains=buscar) |
                Q(estudiante__id_estudiante__icontains=buscar)
            )
            filtros_aplicados.append(f"buscar={buscar}")
            print(f"🔍 Búsqueda '{buscar}': {queryset.count()} anomalías")
        
        # 6. Filtros de fecha (solo si existen y no están vacíos)
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')
        
        if fecha_desde and fecha_desde.strip():
            try:
                from datetime import datetime
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_deteccion__date__gte=fecha_desde_obj)
                filtros_aplicados.append(f"desde={fecha_desde}")
                print(f"🔍 Filtro fecha desde {fecha_desde}: {queryset.count()} anomalías")
            except ValueError:
                print(f"❌ Fecha desde inválida ignorada: {fecha_desde}")
        
        if fecha_hasta and fecha_hasta.strip():
            try:
                from datetime import datetime
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha_deteccion__date__lte=fecha_hasta_obj)
                filtros_aplicados.append(f"hasta={fecha_hasta}")
                print(f"🔍 Filtro fecha hasta {fecha_hasta}: {queryset.count()} anomalías")
            except ValueError:
                print(f"❌ Fecha hasta inválida ignorada: {fecha_hasta}")
        
        # Verificar resultado final
        total_anomalias = queryset.count()
        print(f"📊 TOTAL FINAL: {total_anomalias} anomalías")
        print(f"📋 Filtros aplicados: {filtros_aplicados}")
        
        # Si no hay anomalías, mostrar las primeras 5 sin filtros para debug
        if total_anomalias == 0:
            print(f"⚠️ No hay anomalías después de filtros")
            print(f"🔍 Primeras 3 anomalías sin filtros:")
            for anomalia in DeteccionAnomalia.objects.all()[:3]:
                print(f"   - ID:{anomalia.id} {anomalia.estudiante.nombre} ({anomalia.estado})")
            
            messages.warning(request, f'No hay anomalías para exportar. Filtros aplicados: {len(filtros_aplicados)}')
            return redirect('listado_anomalias')
        
        # GENERAR EL ARCHIVO CSV
        print(f"💾 Generando CSV con {total_anomalias} anomalías...")
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        
        # Nombre del archivo descriptivo
        nombre_archivo = f"anomalias_todas_{timezone.now().strftime('%Y%m%d_%H%M')}"
        if filtros_aplicados:
            nombre_archivo += f"_filtros_{len(filtros_aplicados)}"
        
        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}.csv"'
        
        # Escribir BOM para Excel
        response.write('\ufeff')
        
        import csv
        writer = csv.writer(response)
        
        # Escribir cabeceras
        headers = [
            'ID Anomalía',
            'Estudiante ID',
            'Nombre Estudiante', 
            'Carrera',
            'Año Ingreso',
            'Tipo Anomalía',
            'Estado',
            'Prioridad',
            'Score',
            'Confianza',
            'Fecha Detección',
            'Criterio Usado',
            'Revisado Por',
            'Descripción'
        ]
        
        writer.writerow(headers)
        print(f"📋 Cabeceras escritas: {len(headers)} columnas")
        
        # Escribir datos
        filas_escritas = 0
        errores = 0
        
        for anomalia in queryset:
            try:
                fila = [
                    anomalia.id,
                    anomalia.estudiante.id_estudiante,
                    anomalia.estudiante.nombre,
                    anomalia.estudiante.carrera.nombre if anomalia.estudiante.carrera else 'Sin carrera',
                    anomalia.estudiante.ingreso_año,
                    anomalia.get_tipo_anomalia_display(),
                    anomalia.get_estado_display(),
                    anomalia.prioridad,
                    round(anomalia.score_anomalia, 2),
                    round(anomalia.confianza, 3),
                    anomalia.fecha_deteccion.strftime('%Y-%m-%d %H:%M:%S'),
                    anomalia.criterio_usado.nombre if anomalia.criterio_usado else 'N/A',
                    anomalia.revisado_por.get_full_name() if anomalia.revisado_por else 'N/A',
                    (anomalia.observaciones or 'Sin observaciones')[:100] # Limitar descripción
                ]
                
                writer.writerow(fila)
                filas_escritas += 1
                
                # Mostrar progreso cada 10 filas
                if filas_escritas % 10 == 0:
                    print(f"📝 Escritas {filas_escritas}/{total_anomalias} filas...")
                
            except Exception as e:
                errores += 1
                print(f"❌ Error en fila {anomalia.id}: {str(e)}")
                
                if errores > 5:  # Máximo 5 errores
                    print("❌ Demasiados errores, deteniendo")
                    break
        
        print(f"✅ EXPORTACIÓN COMPLETADA:")
        print(f"   Filas escritas: {filas_escritas}")
        print(f"   Errores: {errores}")
        print(f"   Archivo: {nombre_archivo}.csv")
        
        if filas_escritas == 0:
            print("❌ PROBLEMA: No se escribió ninguna fila de datos")
            messages.error(request, 'Error: No se pudieron escribir los datos al archivo CSV.')
            return redirect('listado_anomalias')
        
        messages.success(request, f'Se exportaron {filas_escritas} anomalías exitosamente.')
        return response
        
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Error exportando anomalías: {str(e)}')
        return redirect('listado_anomalias')

def generar_reporte_anomalias_seleccionadas(request, anomalia_ids):
    """
    🔧 FUNCIÓN ESPECÍFICA: Generar reporte de anomalías seleccionadas
    """
    try:
        print(f"📊 Generando reporte de {len(anomalia_ids)} anomalías seleccionadas...")
        
        # Obtener anomalías
        anomalias = DeteccionAnomalia.objects.filter(id__in=anomalia_ids)
        
        # Filtrar por permisos del usuario
        if request.user.rol == 'coordinador_carrera':
            try:
                carrera = Carrera.objects.get(coordinador=request.user)
                anomalias = anomalias.filter(estudiante__carrera=carrera)
            except Carrera.DoesNotExist:
                raise Exception("Usuario sin carrera asignada")
        
        anomalias = anomalias.select_related(
            'estudiante', 'estudiante__carrera', 'criterio_usado'
        ).order_by('-fecha_deteccion')
        
        if not anomalias.exists():
            raise Exception("No hay anomalías para exportar")
        
        # Crear respuesta CSV
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="anomalias_seleccionadas_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
        
        # Escribir BOM para Excel
        response.write('\ufeff')
        
        import csv
        writer = csv.writer(response)
        
        # Escribir cabeceras
        writer.writerow([
            'ID Anomalía',
            'Estudiante ID',
            'Nombre Estudiante', 
            'Carrera',
            'Año Ingreso',
            'Tipo Anomalía',
            'Estado',
            'Prioridad',
            'Score',
            'Confianza',
            'Fecha Detección',
            'Criterio Usado',
            'Descripción'
        ])
        
        # Escribir datos
        for anomalia in anomalias:
            try:
                writer.writerow([
                    anomalia.id,
                    anomalia.estudiante.id_estudiante,
                    anomalia.estudiante.nombre,
                    anomalia.estudiante.carrera.nombre if anomalia.estudiante.carrera else 'Sin carrera',
                    anomalia.estudiante.ingreso_año,  # ← CORREGIDO
                    anomalia.get_tipo_anomalia_display(),
                    anomalia.get_estado_display(),
                    anomalia.prioridad,
                    anomalia.score_anomalia,
                    anomalia.confianza,
                    anomalia.fecha_deteccion.strftime('%Y-%m-%d %H:%M:%S'),
                    anomalia.criterio_usado.nombre if anomalia.criterio_usado else 'N/A',
                    anomalia.observaciones  or 'Sin observaciones'
                ])
            except Exception as e:
                print(f"⚠️ Error procesando anomalía {anomalia.id}: {str(e)}")
                continue
        
        print(f"✅ Reporte de seleccionadas generado: {anomalias.count()} anomalías")
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte de seleccionadas: {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Error generando reporte: {str(e)}')
        return redirect('listado_anomalias')

# 🔧 VERIFICACIÓN RÁPIDA: Función para confirmar el nombre correcto
def verificar_campo_ingreso():
    """
    🔍 Verificación rápida del campo de año de ingreso
    """
    try:
        estudiante = Estudiante.objects.first()
        if estudiante:
            print("🔍 Verificando campos de año de ingreso:")
            
            campos_posibles = ['ingreso_año', 'ingreso_ano', 'año_ingreso', 'ano_ingreso']
            
            for campo in campos_posibles:
                if hasattr(estudiante, campo):
                    valor = getattr(estudiante, campo)
                    print(f"   ✅ {campo}: {valor}")
                else:
                    print(f"   ❌ {campo}: NO EXISTE")
        else:
            print("❌ No hay estudiantes en la base de datos")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
# 🔧 Para usar la verificación, agregar esta línea temporalmente en views.py:
# verificar_campo_ingreso()  # ← Agregar esta línea al inicio de exportar_reporte_anomalias

@login_required
def ayuda_documentacion(request):
    """Vista para mostrar ayuda y documentación"""
    return render(request, 'anomalias/ayuda_documentacion.html')

# 🔧 FUNCIÓN ADICIONAL: Verificar todos los campos de Estudiante
def debug_campos_estudiante():
    """
    🔍 Función para verificar los campos reales del modelo Estudiante
    Solo para debugging - eliminar en producción
    """
    try:
        from django.apps import apps
        
        # Obtener el modelo Estudiante
        modelo_estudiante = apps.get_model('prototipo', 'Estudiante')
        
        print("🔍 DEBUG - Campos del modelo Estudiante:")
        for field in modelo_estudiante._meta.get_fields():
            print(f"   - {field.name}: {type(field).__name__}")
        
        # Verificar un estudiante real
        estudiante_ejemplo = modelo_estudiante.objects.first()
        if estudiante_ejemplo:
            print(f"\n📝 Ejemplo de estudiante:")
            print(f"   ID: {estudiante_ejemplo.pk}")
            print(f"   ID Estudiante: {estudiante_ejemplo.id_estudiante}")
            print(f"   Nombre: {estudiante_ejemplo.nombre}")
            
            # Verificar campo de año de ingreso
            if hasattr(estudiante_ejemplo, 'ingreso_año'):
                print(f"   Ingreso Año (con ñ): {estudiante_ejemplo.ingreso_año}")
            else:
                print(f"   ❌ NO tiene campo 'ingreso_año'")
                
            if hasattr(estudiante_ejemplo, 'ingreso_ano'):
                print(f"   Ingreso Ano (sin ñ): {estudiante_ejemplo.ingreso_ano}")
            else:
                print(f"   ❌ NO tiene campo 'ingreso_ano'")
        
    except Exception as e:
        print(f"❌ Error en debug: {str(e)}")