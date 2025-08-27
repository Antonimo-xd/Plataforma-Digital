from django.http import HttpResponse
from django.shortcuts import redirect
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import classification_report
import time
import json
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Max, Min, Q
from .models import *
from django.contrib import messages

def ejecutar_deteccion_anomalias(criterio, usuario_ejecutor):
    """
    🎯 FUNCIÓN PRINCIPAL CORREGIDA: Ejecuta detección de anomalías
    """
    inicio_tiempo = time.time()
    
    try:
        print(f"🔍 Iniciando detección con criterio: {criterio.nombre}")
        
        # Debug del modelo (solo en desarrollo)
        if hasattr(criterio, 'debug') and criterio.debug:
            debug_modelo_estudiante()
        
        # 1. Preparar datos mejorados
        datos_estudiantes = preparar_datos_estudiantes_mejorado(criterio)
        
        if len(datos_estudiantes) < 10:
            return {
                'exitoso': False,
                'error': 'Datos insuficientes para análisis (mínimo 10 estudiantes)',
                'anomalias_detectadas': 0,
                'total_estudiantes': len(datos_estudiantes)
            }
        
        print(f"📊 Datos preparados: {len(datos_estudiantes)} estudiantes")
        
        # 2. Ejecutar modelo con parámetros dinámicos
        resultados_modelo = ejecutar_isolation_forest_mejorado(datos_estudiantes, criterio)
        
        if not resultados_modelo or not resultados_modelo.get('anomalias'):
            return {
                'exitoso': False,
                'error': 'No se detectaron anomalías',
                'anomalias_detectadas': 0,
                'total_estudiantes': len(datos_estudiantes)
            }
        
        # 3. Guardar anomalías detectadas
        anomalias_guardadas = guardar_anomalias_detectadas(
            resultados_modelo, criterio, usuario_ejecutor
        )
        
        tiempo_ejecucion = time.time() - inicio_tiempo
        
        # 4. Crear registro de ejecución
        ejecucion = EjecucionAnalisis.objects.create(
            criterio_usado=criterio,
            ejecutado_por=usuario_ejecutor,
            total_estudiantes_analizados=len(datos_estudiantes),
            anomalias_detectadas=len(anomalias_guardadas),
            porcentaje_anomalias=round((len(anomalias_guardadas) / len(datos_estudiantes)) * 100, 2),
            parametros_modelo=resultados_modelo['parametros'],
            metricas_modelo=resultados_modelo['metricas'],
            tiempo_ejecucion=tiempo_ejecucion,
            exitoso=True
        )
        
        print(f"✅ Detección completada: {len(anomalias_guardadas)} anomalías en {tiempo_ejecucion:.2f}s")
        
        return {
            'exitoso': True,
            'anomalias_detectadas': len(anomalias_guardadas),
            'total_estudiantes': len(datos_estudiantes),
            'porcentaje_anomalias': ejecucion.porcentaje_anomalias,
            'tiempo_ejecucion': tiempo_ejecucion,
            'ejecucion_id': ejecucion.id
        }
        
    except Exception as e:
        print(f"❌ Error en detección: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Guardar ejecución fallida
        try:
            EjecucionAnalisis.objects.create(
                criterio_usado=criterio,
                ejecutado_por=usuario_ejecutor,
                total_estudiantes_analizados=0,
                anomalias_detectadas=0,
                porcentaje_anomalias=0,
                parametros_modelo={},
                metricas_modelo={},
                tiempo_ejecucion=time.time() - inicio_tiempo,
                exitoso=False,
                mensaje_error=str(e)
            )
        except:
            pass  # Si falla guardar el error, continuar
        
        return {
            'exitoso': False,
            'error': str(e),
            'anomalias_detectadas': 0
        }

def preparar_datos_estudiantes_mejorado(criterio):
    """
    🛠️ FUNCIÓN CORREGIDA: Prepara datos de estudiantes para análisis de anomalías
    """
    print("📝 Preparando datos de estudiantes...")
    
    try:
        # 1. CONSULTA BASE: Obtener estudiantes activos
        estudiantes_query = Estudiante.objects.filter(activo=True)
        
        # 2. APLICAR FILTROS DEL CRITERIO (si existen)
        if criterio.carrera:
            estudiantes_query = estudiantes_query.filter(carrera=criterio.carrera)
            print(f"   🎯 Filtro aplicado - Carrera: {criterio.carrera.nombre}")
        
        if criterio.semestre:
            # Filtrar por estudiantes que tienen registros en asignaturas del semestre especificado
            estudiantes_query = estudiantes_query.filter(
                registroacademico__asignatura__semestre=criterio.semestre
            ).distinct()
            print(f"   🎯 Filtro aplicado - Semestre: {criterio.semestre}")
        
        print(f"   👥 Estudiantes después de filtros: {estudiantes_query.count()}")
        
        # 3. VERIFICAR QUE TENEMOS ESTUDIANTES
        if not estudiantes_query.exists():
            print("❌ No se encontraron estudiantes que cumplan los criterios")
            return []
        
        # 4. PROCESAR DATOS DE CADA ESTUDIANTE
        datos = []
        estudiantes_procesados = 0
        estudiantes_sin_registros = 0
        
        for estudiante in estudiantes_query:
            try:
                # Obtener registros académicos del estudiante
                registros_estudiante = RegistroAcademico.objects.filter(estudiante=estudiante)
                
                if not registros_estudiante.exists():
                    estudiantes_sin_registros += 1
                    print(f"   ⚠️ Estudiante {estudiante.nombre} sin registros académicos")
                    continue
                
                # CALCULAR MÉTRICAS DEL ESTUDIANTE
                
                # Promedio general
                promedios = registros_estudiante.values_list('promedio_notas', flat=True)
                promedio_general = np.mean(promedios) if promedios else 0
                
                # Asistencia promedio
                asistencias = registros_estudiante.values_list('porcentaje_asistencia', flat=True)
                asistencia_promedio = np.mean(asistencias) if asistencias else 0
                
                # Uso de plataforma promedio
                usos_plataforma = registros_estudiante.values_list('porcentaje_uso_plataforma', flat=True)
                uso_promedio = np.mean(usos_plataforma) if usos_plataforma else 0
                
                # Variación de notas (desviación estándar)
                variacion_notas = np.std(promedios) if len(promedios) > 1 else 0
                
                # Variación de asistencia
                variacion_asistencia = np.std(asistencias) if len(asistencias) > 1 else 0
                
                # Tendencia de notas (pendiente de regresión)
                notas = list(promedios)
                tendencia_notas = 0
                if len(notas) >= 3:
                    x = np.arange(len(notas))
                    try:
                        pendiente = np.polyfit(x, notas, 1)[0]
                        tendencia_notas = pendiente
                    except:
                        tendencia_notas = 0
                
                # 🔧 CAMBIO IMPORTANTE: INCLUIR TODOS LOS ESTUDIANTES CON REGISTROS
                # No filtrar por criterios aquí, el modelo ML decidirá qué es anómalo
                
                # Verificar que las métricas sean válidas
                if (promedio_general > 0 and asistencia_promedio >= 0 and 
                    uso_promedio >= 0 and not np.isnan(promedio_general)):
                    
                    datos.append({
                        'estudiante_pk': estudiante.pk,
                        'estudiante_id': estudiante.id_estudiante,
                        'promedio_general': float(promedio_general),
                        'asistencia_promedio': float(asistencia_promedio),
                        'uso_plataforma_promedio': float(uso_promedio),
                        'variacion_notas': float(variacion_notas),
                        'variacion_asistencia': float(variacion_asistencia),
                        'tendencia_notas': float(tendencia_notas),
                        'total_asignaturas': registros_estudiante.count(),
                        'estudiante_obj': estudiante
                    })
                    
                    estudiantes_procesados += 1
                    
                    # Log cada 20 estudiantes procesados
                    if estudiantes_procesados % 20 == 0:
                        print(f"   📊 Procesados: {estudiantes_procesados} estudiantes")
                else:
                    print(f"   ⚠️ Métricas inválidas para {estudiante.nombre}")
                    
            except Exception as e:
                print(f"   ❌ Error procesando estudiante {estudiante.nombre}: {str(e)}")
                continue
        
        # 5. RESUMEN DEL PROCESAMIENTO
        print(f"\n📊 RESUMEN DE PREPARACIÓN DE DATOS:")
        print(f"   ✅ Estudiantes válidos procesados: {len(datos)}")
        print(f"   ⚠️ Estudiantes sin registros: {estudiantes_sin_registros}")
        print(f"   🎯 Total estudiantes en query inicial: {estudiantes_query.count()}")
        
        if len(datos) == 0:
            print("❌ No se encontraron registros académicos para ningún estudiante")
            print("🔍 DIAGNÓSTICO:")
            print(f"   - Total estudiantes activos: {Estudiante.objects.filter(activo=True).count()}")
            print(f"   - Total registros académicos: {RegistroAcademico.objects.count()}")
            
            # Verificar si hay registros en general
            if RegistroAcademico.objects.count() == 0:
                print("💡 SOLUCIÓN: Importa los registros académicos primero")
            else:
                print("💡 SOLUCIÓN: Verifica los filtros del criterio (carrera/semestre)")
        
        return datos
        
    except Exception as e:
        print(f"❌ Error en preparar_datos_estudiantes_mejorado: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def ejecutar_isolation_forest_mejorado(datos_estudiantes, criterio):
    """
    🤖 FUNCIÓN CORREGIDA: Isolation Forest con referencias de ID correctas
    """
    print("🔬 Ejecutando Isolation Forest mejorado...")
    
    if not datos_estudiantes:
        print("❌ No hay datos de estudiantes para procesar")
        return {'anomalias': [], 'parametros': {}, 'metricas': {}}
    
    # Crear DataFrame con características numéricas
    df = pd.DataFrame([
        {
            'promedio_general': d['promedio_general'],
            'asistencia_promedio': d['asistencia_promedio'],
            'uso_plataforma_promedio': d['uso_plataforma_promedio'],
            'variacion_notas': d['variacion_notas'],
            'variacion_asistencia': d['variacion_asistencia'],
            'tendencia_notas': d['tendencia_notas'],
            'total_asignaturas': d['total_asignaturas']
        }
        for d in datos_estudiantes
    ])
    
    print(f"📊 DataFrame creado: {df.shape[0]} filas, {df.shape[1]} columnas")
    
    # Verificar que no hay valores NaN
    if df.isnull().any().any():
        print("⚠️ Detectados valores NaN, rellenando con 0")
        df = df.fillna(0)
    
    # Normalizar datos
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df)
    
    # Parámetros dinámicos basados en el tamaño de datos
    n_estudiantes = len(datos_estudiantes)
    
    # Contamination dinámico: entre 5% y 25%
    contamination = getattr(criterio, 'contamination_rate', 0.1)
    contamination = min(max(contamination, 0.05), 0.25)
    
    # Número de estimadores
    n_estimators = getattr(criterio, 'n_estimators', 100)
    n_estimators = min(max(n_estimators, 50), 200)
    
    print(f"🔧 Parámetros: contamination={contamination}, n_estimators={n_estimators}")
    
    # Configurar Isolation Forest
    isolation_forest = IsolationForest(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=42,
        n_jobs=-1
    )
    
    # Entrenar y predecir
    try:
        predicciones = isolation_forest.fit_predict(X_scaled)
        scores = isolation_forest.decision_function(X_scaled)
        
        # Normalizar scores a 0-100
        scores_min = np.min(scores)
        scores_max = np.max(scores)
        
        if scores_max != scores_min:
            scores_normalized = ((scores - scores_min) / (scores_max - scores_min)) * 100
        else:
            scores_normalized = np.full(len(scores), 50.0)  # Valor neutro si todos son iguales
        
        print(f"🎯 Predicciones completadas. Anomalías detectadas: {np.sum(predicciones == -1)}")
        
    except Exception as e:
        print(f"❌ Error en Isolation Forest: {str(e)}")
        return {'anomalias': [], 'parametros': {}, 'metricas': {}}
    
    # Preparar resultados de anomalías
    anomalias = []
    for i, (datos_est, pred, score) in enumerate(zip(datos_estudiantes, predicciones, scores_normalized)):
        if pred == -1:  # Es anomalía
            anomalia = {
                'estudiante': datos_est['estudiante_obj'],
                'estudiante_pk': datos_est['estudiante_pk'],  # 🔧 CORREGIDO
                'estudiante_id': datos_est['estudiante_id'],  # 🔧 CORREGIDO
                'score_anomalia': float(score),
                'confianza': min(float(score) / 100.0, 1.0),
                'promedio_general': datos_est['promedio_general'],
                'asistencia_promedio': datos_est['asistencia_promedio'],
                'uso_plataforma_promedio': datos_est['uso_plataforma_promedio'],
                'variacion_notas': datos_est['variacion_notas'],
                'tipo_anomalia': determinar_tipo_anomalia(datos_est)
            }
            anomalias.append(anomalia)
    
    # Parámetros y métricas del modelo
    parametros = {
        'contamination': contamination,
        'n_estimators': n_estimators,
        'criterio_id': criterio.id,
        'total_estudiantes': n_estudiantes
    }
    
    metricas = {
        'anomalias_detectadas': len(anomalias),
        'porcentaje_anomalias': (len(anomalias) / n_estudiantes) * 100,
        'score_min': float(np.min(scores_normalized)),
        'score_max': float(np.max(scores_normalized)),
        'score_promedio': float(np.mean(scores_normalized))
    }
    
    return {
        'anomalias': anomalias,
        'parametros': parametros,
        'metricas': metricas
    }

def determinar_tipo_anomalia(estudiante_data):
    """
    🔍 FUNCIÓN CORREGIDA: Determina el tipo específico de anomalía
    """
    try:
        promedio = estudiante_data.get('promedio_general', 0)
        asistencia = estudiante_data.get('asistencia_promedio', 0)
        uso_plataforma = estudiante_data.get('uso_plataforma_promedio', 0)
        variacion = estudiante_data.get('variacion_notas', 0)
        
        # Lógica para determinar tipo
        if promedio < 4.0 and asistencia < 60:
            return 'multiple'
        elif promedio < 4.0:
            return 'bajo_rendimiento'
        elif asistencia < 60:
            return 'baja_asistencia'
        elif uso_plataforma < 30:
            return 'uso_ineficiente_plataforma'
        elif variacion > 1.5:
            return 'alta_variabilidad'
        else:
            return 'multiple'
            
    except Exception as e:
        print(f"⚠️ Error determinando tipo de anomalía: {str(e)}")
        return 'multiple'  # Tipo por defecto

def guardar_anomalias_detectadas(resultados_modelo, criterio, usuario_ejecutor):
    """
    💾 FUNCIÓN CORREGIDA: Guarda las anomalías en la base de datos
    """
    anomalias_guardadas = []
    
    print(f"💾 Guardando {len(resultados_modelo['anomalias'])} anomalías...")
    
    for anomalia_data in resultados_modelo['anomalias']:
        try:
            estudiante = anomalia_data['estudiante']
            
            # 🔧 VERIFICACIÓN: Asegurar que el estudiante existe
            if not estudiante or not hasattr(estudiante, 'pk'):
                print(f"⚠️ Estudiante inválido en anomalía, saltando...")
                continue
            
            # Verificar si ya existe anomalía reciente para este estudiante
            anomalia_existente = DeteccionAnomalia.objects.filter(
                estudiante=estudiante,
                tipo_anomalia=anomalia_data['tipo_anomalia'],
                fecha_deteccion__gte=timezone.now() - timedelta(days=7)
            ).first()
            
            if anomalia_existente:
                print(f"⚠️ Anomalía reciente ya existe para {estudiante.nombre}")
                continue
            
            # Calcular prioridad basada en score
            score = anomalia_data['score_anomalia']
            if score >= 80:
                prioridad = 5  # Crítica
            elif score >= 60:
                prioridad = 4  # Alta
            elif score >= 40:
                prioridad = 3  # Media
            elif score >= 20:
                prioridad = 2  # Baja
            else:
                prioridad = 1  # Muy baja
            
            # Crear nueva anomalía
            nueva_anomalia = DeteccionAnomalia.objects.create(
                estudiante=estudiante,
                criterio_usado=criterio,
                tipo_anomalia=anomalia_data['tipo_anomalia'],
                score_anomalia=anomalia_data['score_anomalia'],
                confianza=anomalia_data['confianza'],
                promedio_general=anomalia_data['promedio_general'],
                asistencia_promedio=anomalia_data['asistencia_promedio'],
                uso_plataforma_promedio=anomalia_data['uso_plataforma_promedio'],
                variacion_notas=anomalia_data['variacion_notas'],
                prioridad=prioridad,
                estado='detectado'
            )
            
            anomalias_guardadas.append(nueva_anomalia)
            print(f"✅ Anomalía guardada: {nueva_anomalia.estudiante.nombre} - {nueva_anomalia.tipo_anomalia}")
            
        except Exception as e:
            print(f"❌ Error guardando anomalía: {str(e)}")
            continue
    
    print(f"💾 Total anomalías guardadas: {len(anomalias_guardadas)}")
    return anomalias_guardadas

def generar_reporte_anomalias(request, anomalia_ids=None):
    """
    🔧 FUNCIÓN CORREGIDA: Generar reporte de anomalías
    Corrige el error: 'Estudiante' object has no attribute 'ingreso_ano'
    """
    try:
        print(f"📊 Generando reporte de anomalías...")
        
        # Obtener anomalías
        if anomalia_ids:
            anomalias = DeteccionAnomalia.objects.filter(id__in=anomalia_ids)
        else:
            anomalias = DeteccionAnomalia.objects.all()
        
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
        
        print(f"📋 Exportando {anomalias.count()} anomalías...")
        
        # Crear respuesta CSV
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="anomalias_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
        
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
            'Año Ingreso',  # ← CORREGIDO: nombre del campo
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
                # CORREGIDO: usar ingreso_año en lugar de ingreso_ano
                año_ingreso = getattr(anomalia.estudiante, 'ingreso_año', 'N/A')
                
                writer.writerow([
                    anomalia.id,
                    anomalia.estudiante.id_estudiante,
                    anomalia.estudiante.nombre,
                    anomalia.estudiante.carrera.nombre if anomalia.estudiante.carrera else 'Sin carrera',
                    año_ingreso,  # ← CORREGIDO
                    anomalia.get_tipo_anomalia_display(),
                    anomalia.get_estado_display(),
                    anomalia.prioridad,
                    anomalia.score_anomalia,
                    anomalia.confianza,
                    anomalia.fecha_deteccion.strftime('%Y-%m-%d %H:%M:%S'),
                    anomalia.criterio_usado.nombre if anomalia.criterio_usado else 'N/A',
                    anomalia.descripcion or 'Sin descripción'
                ])
            except Exception as e:
                print(f"⚠️ Error procesando anomalía {anomalia.id}: {str(e)}")
                continue
        
        print(f"✅ Reporte generado exitosamente")
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte: {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Error generando reporte: {str(e)}')
        return redirect('listado_anomalias')

# 🔧 FUNCIÓN DE DEBUGGING ADICIONAL
def debug_modelo_estudiante():
    """
    🔍 Función para debuggear el modelo Estudiante
    Solo para desarrollo - eliminar en producción
    """
    try:
        # Verificar primer estudiante
        primer_estudiante = Estudiante.objects.first()
        
        if primer_estudiante:
            print(f"🔍 DEBUG - Modelo Estudiante:")
            print(f"   Tipo de objeto: {type(primer_estudiante)}")
            print(f"   Atributos disponibles: {dir(primer_estudiante)}")
            print(f"   PK: {primer_estudiante.pk}")
            print(f"   ID Estudiante: {primer_estudiante.id_estudiante}")
            print(f"   Nombre: {primer_estudiante.nombre}")
            
            # Verificar si tiene atributo 'id'
            tiene_id = hasattr(primer_estudiante, 'id')
            print(f"   ¿Tiene atributo 'id'?: {tiene_id}")
            
            if tiene_id:
                print(f"   Valor de 'id': {primer_estudiante.id}")
            else:
                print(f"   ❌ NO tiene atributo 'id' - usar 'pk' o 'id_estudiante'")
                
        else:
            print("❌ No hay estudiantes en la base de datos")
            
    except Exception as e:
        print(f"❌ Error en debug: {str(e)}")

