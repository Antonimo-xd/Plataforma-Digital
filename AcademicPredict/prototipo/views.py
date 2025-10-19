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
from django.urls import reverse  
import traceback
# Imports de utilidades (ahora centralizadas)
from .utils.permissions import (
    es_coordinador_cpa,
    es_analista_cpa,
    puede_ver_anomalias,
    es_coordinador_carrera
)
from .utils.helpers import (
    determinar_nivel_criticidad,
    crear_alertas_automaticas,
)
from .utils.notifications import (
    enviar_notificacion_derivacion,
    enviar_notificacion_cambio_estado,
)
# Imports de servicios
from .services.import_service import ImportService
from .services.reports_service import ReportsService
# Imports de modelos y formularios
from .models import (
    DeteccionAnomalia,
    CriterioAnomalia,
    Derivacion,
    Estudiante,
    Carrera,
    EjecucionAnalisis,
    InstanciaApoyo,
)
from .forms import (
    CriterioAnomaliaForm,
    DerivacionForm,
    FiltroAnomaliasForm,
)
from .ML import ejecutar_deteccion_anomalias

@login_required
def dashboard(request):
    """
    Vista principal del sistema - Dashboard con estadísticas
    
    🎓 APRENDIZAJE: El dashboard es el centro de navegación
    - Muestra métricas clave
    - Enlaces rápidos a funcionalidades
    - Estado general del sistema
    """
    if not puede_ver_anomalias(request.user):
        messages.error(request, 'No tienes permisos para acceder')
        return redirect('login')
    
    # Estadísticas según el rol del usuario
    if es_coordinador_carrera(request.user):
        # Solo su carrera
        anomalias = DeteccionAnomalia.objects.filter(
            estudiante__carrera=request.user.carrera
        )
    else:
        # Todas las anomalías
        anomalias = DeteccionAnomalia.objects.all()
    
    # Métricas
    stats = {
        'total_anomalias': anomalias.count(),
        'pendientes': anomalias.filter(estado='detectada').count(),
        'en_revision': anomalias.filter(estado='en_revision').count(),
        'criticas': anomalias.filter(nivel_criticidad='alta').count(),
    }
    
    # Anomalías recientes
    anomalias_recientes = anomalias.order_by('-fecha_deteccion')[:10]
    
    context = {
        'stats': stats,
        'anomalias_recientes': anomalias_recientes,
    }
    
    return render(request, 'anomalias/dashboard.html', context)

class ListadoAnomaliasView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Lista paginada de anomalías con filtros
    
    🎓 APRENDIZAJE: ListView de Django
    - Paginación automática
    - Ordenamiento
    - Filtros personalizados
    """
    model = DeteccionAnomalia
    template_name = 'anomalias/listado_anomalias.html'
    context_object_name = 'anomalias'
    paginate_by = 20
    
    def test_func(self):
        """Verifica permisos del usuario"""
        return puede_ver_anomalias(self.request.user)
    
    def get_queryset(self):
        """Filtra anomalías según permisos y filtros aplicados"""
        queryset = DeteccionAnomalia.objects.select_related(
            'estudiante',
            'estudiante__carrera',
            'criterio_usado'
        ).order_by('-fecha_deteccion')
        
        # Filtrar por carrera si es coordinador de carrera
        if es_coordinador_carrera(self.request.user):
            queryset = queryset.filter(
                estudiante__carrera=self.request.user.carrera
            )
        
        # Aplicar filtros del formulario
        form = FiltroAnomaliasForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('estado'):
                queryset = queryset.filter(estado=form.cleaned_data['estado'])
            
            if form.cleaned_data.get('tipo_anomalia'):
                queryset = queryset.filter(tipo_anomalia=form.cleaned_data['tipo_anomalia'])
            
            if form.cleaned_data.get('carrera'):
                queryset = queryset.filter(estudiante__carrera=form.cleaned_data['carrera'])
            
            if form.cleaned_data.get('nivel_criticidad'):
                queryset = queryset.filter(nivel_criticidad=form.cleaned_data['nivel_criticidad'])
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Agrega datos adicionales al contexto"""
        context = super().get_context_data(**kwargs)
        context['form_filtros'] = FiltroAnomaliasForm(self.request.GET)
        return context

class DetalleAnomaliaView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Vista detallada de una anomalía específica
    
    🎓 APRENDIZAJE: DetailView de Django
    - Carga automática del objeto por PK
    - Relaciones precargadas con select_related
    """
    model = DeteccionAnomalia
    template_name = 'anomalias/detalle_anomalia.html'
    context_object_name = 'anomalia'
    
    def test_func(self):
        return puede_ver_anomalias(self.request.user)
    
    def get_queryset(self):
        """Optimiza consultas con select_related"""
        return DeteccionAnomalia.objects.select_related(
            'estudiante',
            'estudiante__carrera',
            'criterio',
            'usuario_detector'
        ).prefetch_related(
            'derivacion_set__instancia_apoyo'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Historial de derivaciones
        context['derivaciones'] = self.object.derivacion_set.all()
        
        # Registros académicos del estudiante
        context['registros_academicos'] = self.object.estudiante.registroacademico_set.select_related(
            'asignatura'
        ).order_by('-asignatura__semestre')
        
        # Formularios
        context['form_derivacion'] = DerivacionForm()
        
        return context

@login_required
def actualizar_estado_anomalia(request, anomalia_id):
    """
    Actualiza el estado de una anomalía
    
    🎓 APRENDIZAJE: Esta función ahora es simple
    - La lógica está en el modelo
    - Solo maneja HTTP y permisos
    """
    if not puede_ver_anomalias(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    anomalia = get_object_or_404(DeteccionAnomalia, id=anomalia_id)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        observaciones = request.POST.get('observaciones', '')
        
        try:
            # Usar método del modelo (Fat Model, Thin View)
            anomalia.actualizar_estado(nuevo_estado, observaciones, request.user)
            
            # Notificar cambio
            enviar_notificacion_cambio_estado(anomalia, nuevo_estado)
            
            messages.success(request, 'Estado actualizado correctamente')
            return JsonResponse({'success': True})
            
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

@login_required
def crear_derivacion(request, anomalia_id):
    """
    Crea una derivación a instancia de apoyo
    
    🎓 APRENDIZAJE: Separación de responsabilidades
    - Vista: Maneja el formulario
    - Notificaciones: En módulo aparte
    """
    anomalia = get_object_or_404(DeteccionAnomalia, id=anomalia_id)
    
    if not anomalia.puede_ser_derivada():
        messages.error(request, 'Esta anomalía no puede ser derivada en su estado actual')
        return redirect('detalle_anomalia', pk=anomalia_id)
    
    if request.method == 'POST':
        form = DerivacionForm(request.POST)
        if form.is_valid():
            derivacion = form.save(commit=False)
            derivacion.deteccion_anomalia = anomalia
            derivacion.usuario_creador = request.user
            derivacion.save()
            
            # Actualizar estado de anomalía
            anomalia.actualizar_estado('derivada', 'Derivada a instancia de apoyo', request.user)
            
            # Notificar
            enviar_notificacion_derivacion(derivacion)
            
            messages.success(request, 'Derivación creada exitosamente')
            return redirect('detalle_anomalia', pk=anomalia_id)
    else:
        form = DerivacionForm()
    
    return render(request, 'anomalias/crear_derivacion.html', {
        'form': form,
        'anomalia': anomalia
    })

@login_required
def crear_criterio_anomalia(request):
    """
    Crea un nuevo criterio de detección ML
    
    🎓 APRENDIZAJE: Los criterios configuran el algoritmo
    - contamination: % esperado de anomalías
    - n_estimators: Árboles en el Isolation Forest
    """
    if not es_coordinador_cpa(request.user):
        messages.error(request, 'Solo coordinadores CPA pueden crear criterios')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CriterioAnomaliaForm(request.POST)
        if form.is_valid():
            criterio = form.save(commit=False)
            criterio.usuario_creador = request.user
            criterio.save()
            
            messages.success(request, 'Criterio creado exitosamente')
            return redirect('configuracion_criterios')
    else:
        form = CriterioAnomaliaForm()
    
    return render(request, 'anomalias/crear_criterio.html', {'form': form})

@login_required
def ejecutar_analisis(request, criterio_id):
    """
    Ejecuta el algoritmo ML con un criterio específico
    
    🎓 APRENDIZAJE: Esta vista conecta la UI con el ML
    - Llama a la función del módulo ML
    - Muestra resultados al usuario
    """
    if not puede_ver_anomalias(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    criterio = get_object_or_404(CriterioAnomalia, id=criterio_id)
    
    try:
        # Ejecutar detección (en ML.py)
        resultados = ejecutar_deteccion_anomalias(criterio, request.user)
        
        messages.success(
            request,
            f'Análisis completado: {resultados["anomalias_detectadas"]} anomalías encontradas'
        )
        
        return redirect('listado_anomalias')
        
    except Exception as e:
        messages.error(request, f'Error en el análisis: {str(e)}')
        return redirect('configuracion_criterios')

@login_required
def importar_datos(request):
    """
    Vista para importar datos desde archivos CSV/Excel
    
    🎓 APRENDIZAJE: Ahora usa el servicio centralizado
    - La lógica compleja está en ImportService
    - La vista solo maneja el formulario y muestra resultados
    """
    if request.method == 'POST':
        tipo_archivo = request.POST.get('tipo_archivo')
        archivo = request.FILES.get('archivo')
        
        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo')
            return redirect('importar_datos')
        
        # Usar el servicio según el tipo
        if tipo_archivo == 'estudiantes':
            resultado = ImportService.procesar_estudiantes(archivo)
        elif tipo_archivo == 'asignaturas':
            resultado = ImportService.procesar_asignaturas(archivo)
        elif tipo_archivo == 'registros':
            resultado = ImportService.procesar_registros(archivo)
        else:
            messages.error(request, 'Tipo de archivo no válido')
            return redirect('importar_datos')
        
        # Mostrar resultados
        if resultado['errores']:
            for error in resultado['errores'][:10]:  # Mostrar máximo 10
                messages.error(request, error)
        
        if resultado['advertencias']:
            for adv in resultado['advertencias'][:5]:
                messages.warning(request, adv)
        
        if resultado['importados'] > 0:
            messages.success(
                request,
                f'✅ {resultado["importados"]} registros importados correctamente'
            )
        
        return render(request, 'anomalias/importar_resultados.html', {
            'resultado': resultado
        })
    
    return render(request, 'anomalias/importar_datos.html')

@login_required
def exportar_reporte_anomalias(request):
    """
    Exporta reporte de anomalías a Excel
    
    🎓 APRENDIZAJE: Usa el servicio de reportes
    """
    return ReportsService.exportar_anomalias_completo(request, formato='excel')

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

@login_required
@user_passes_test(es_coordinador_cpa)
def configuracion_criterios(request):
    """
    🔧 CORRECCIÓN: Función que faltaba para configuración de criterios
    
    🎓 EDUCATIVO: Si tu views.py actual tiene una clase en lugar de función,
    esta función será la versión simplificada.
    """
    # Obtener criterios existentes
    criterios = CriterioAnomalia.objects.filter(activo=True).order_by('-fecha_creacion')
    
    # Estadísticas básicas
    estadisticas = {
        'total_criterios': criterios.count(),
        'total_ejecuciones': EjecucionAnalisis.objects.count(),
        'ultima_ejecucion': EjecucionAnalisis.objects.order_by('-fecha_ejecucion').first(),
    }
    
    context = {
        'criterios': criterios,
        'estadisticas': estadisticas,
        'form': CriterioAnomaliaForm(),
    }
    
    return render(request, 'anomalias/configuracion_criterios.html', context)

def generar_reporte_anomalias_seleccionadas(anomalias_queryset, request):
    """
    Genera un reporte Excel de las anomalías seleccionadas
    
    🎓 EDUCATIVO: Esta función crea un archivo Excel con:
    - Datos del estudiante
    - Métricas de la anomalía
    - Estado actual
    - Derivaciones asociadas
    
    Args:
        anomalias_queryset: QuerySet de DeteccionAnomalia
        request: HttpRequest
        
    Returns:
        HttpResponse con archivo Excel
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from django.utils import timezone
    
    # Crear workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Anomalías Seleccionadas"
    
    # ================================================================
    # ENCABEZADOS
    # ================================================================
    headers = [
        'ID', 'Estudiante', 'ID Estudiante', 'Carrera',
        'Tipo Anomalía', 'Estado', 'Prioridad',
        'Promedio General', 'Asistencia %', 'Uso Plataforma %',
        'Score Anomalía', 'Confianza %', 
        'Fecha Detección', 'Revisado Por',
        'Tiene Derivación', 'Observaciones'
    ]
    
    # Estilo para encabezados
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # ================================================================
    # DATOS
    # ================================================================
    anomalias = anomalias_queryset.select_related(
        'estudiante',
        'estudiante__carrera',
        'revisado_por'
    ).prefetch_related('derivacion_set')
    
    for row_num, anomalia in enumerate(anomalias, 2):
        # Verificar si tiene derivación
        tiene_derivacion = anomalia.derivacion_set.exists()
        
        datos = [
            anomalia.id,
            anomalia.estudiante.nombre,
            anomalia.estudiante.id_estudiante,
            anomalia.estudiante.carrera.nombre if anomalia.estudiante.carrera else 'N/A',
            anomalia.get_tipo_anomalia_display(),
            anomalia.get_estado_display(),
            anomalia.prioridad,
            round(anomalia.promedio_general, 2),
            round(anomalia.asistencia_promedio, 1),
            round(anomalia.uso_plataforma_promedio, 1),
            round(anomalia.score_anomalia, 4),
            round(anomalia.confianza, 1),
            anomalia.fecha_deteccion.strftime('%Y-%m-%d %H:%M'),
            anomalia.revisado_por.get_full_name() if anomalia.revisado_por else 'Sin asignar',
            'Sí' if tiene_derivacion else 'No',
            anomalia.observaciones[:100] if anomalia.observaciones else ''
        ]
        
        for col_num, valor in enumerate(datos, 1):
            ws.cell(row=row_num, column=col_num, value=valor)
    
    # ================================================================
    # AJUSTAR ANCHOS DE COLUMNA
    # ================================================================
    column_widths = {
        'A': 8,   # ID
        'B': 25,  # Estudiante
        'C': 15,  # ID Estudiante
        'D': 30,  # Carrera
        'E': 20,  # Tipo
        'F': 15,  # Estado
        'G': 10,  # Prioridad
        'H': 12,  # Promedio
        'I': 12,  # Asistencia
        'J': 15,  # Uso Plataforma
        'K': 12,  # Score
        'L': 12,  # Confianza
        'M': 18,  # Fecha
        'N': 20,  # Revisado Por
        'O': 15,  # Tiene Derivación
        'P': 40,  # Observaciones
    }
    
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width
    
    # ================================================================
    # HOJA DE RESUMEN
    # ================================================================
    ws_resumen = wb.create_sheet(title="Resumen")
    
    # Estadísticas
    total = anomalias.count()
    por_estado = anomalias.values('estado').annotate(
        count=Count('id')
    ).order_by('-count')
    
    por_tipo = anomalias.values('tipo_anomalia').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Escribir resumen
    ws_resumen['A1'] = 'RESUMEN DE ANOMALÍAS SELECCIONADAS'
    ws_resumen['A1'].font = Font(size=14, bold=True)
    
    ws_resumen['A3'] = f'Total de anomalías: {total}'
    ws_resumen['A4'] = f'Fecha de generación: {timezone.now().strftime("%Y-%m-%d %H:%M")}'
    ws_resumen['A5'] = f'Generado por: {request.user.get_full_name()}'
    
    # Distribución por estado
    ws_resumen['A7'] = 'DISTRIBUCIÓN POR ESTADO'
    ws_resumen['A7'].font = Font(bold=True)
    row = 8
    for item in por_estado:
        ws_resumen[f'A{row}'] = item['estado']
        ws_resumen[f'B{row}'] = item['count']
        ws_resumen[f'C{row}'] = f"{(item['count']/total)*100:.1f}%"
        row += 1
    
    # Distribución por tipo
    ws_resumen[f'A{row+1}'] = 'DISTRIBUCIÓN POR TIPO'
    ws_resumen[f'A{row+1}'].font = Font(bold=True)
    row += 2
    for item in por_tipo:
        ws_resumen[f'A{row}'] = item['tipo_anomalia']
        ws_resumen[f'B{row}'] = item['count']
        ws_resumen[f'C{row}'] = f"{(item['count']/total)*100:.1f}%"
        row += 1
    
    # ================================================================
    # PREPARAR RESPUESTA HTTP
    # ================================================================
    from io import BytesIO
    
    # Guardar en memoria
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    # Crear respuesta
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    filename = f'anomalias_seleccionadas_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response
