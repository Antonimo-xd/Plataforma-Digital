# -*- coding: utf-8 -*-
"""
Servicio de Predicción de Deserción Estudiantil
==============================================

Este servicio integra el modelo de Machine Learning entrenado para:
- Realizar predicciones de deserción para estudiantes
- Asignar estudiantes a cohortes de riesgo
- Generar seguimientos temporales
- Crear alertas automáticas
- Realizar comparaciones de intervenciones
"""

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.utils import timezone
import logging

from prototipo.models import (
    Estudiante, RegistroAcademico, PrediccionDesercion,
    SeguimientoEstudiante, CohorteEstudiantil, AlertaPrediccion,
    ComparacionIntervenciones
)

logger = logging.getLogger(__name__)


class ServicioPrediccionDesercion:
    """
    Servicio principal para predicciones de deserción estudiantil.
    """

    def __init__(self):
        """Inicializa el servicio de predicción"""
        self.modelo = None
        self.scaler = None
        self.label_encoder = None
        self.info_modelo = None
        self.modelo_cargado = False
        self.ruta_modelos = Path(__file__).parent.parent / 'ml_models'

        # Cargar modelo automáticamente
        try:
            self.cargar_modelo()
        except Exception as e:
            logger.error(f"Error al cargar modelo: {e}")

    def cargar_modelo(self):
        """Carga el modelo de ML y sus componentes"""
        try:
            logger.info("Cargando modelo de deserción estudiantil...")

            # Verificar que existan los archivos
            archivos_necesarios = {
                'modelo': self.ruta_modelos / 'mejor_modelo.pkl',
                'scaler': self.ruta_modelos / 'scaler.pkl',
                'encoder': self.ruta_modelos / 'label_encoder.pkl',
                'info': self.ruta_modelos / 'info_modelo.pkl'
            }

            for nombre, ruta in archivos_necesarios.items():
                if not ruta.exists():
                    raise FileNotFoundError(f"No se encontró {nombre} en {ruta}")

            # Cargar componentes
            self.modelo = joblib.load(archivos_necesarios['modelo'])
            self.scaler = joblib.load(archivos_necesarios['scaler'])
            self.label_encoder = joblib.load(archivos_necesarios['encoder'])
            self.info_modelo = joblib.load(archivos_necesarios['info'])

            self.modelo_cargado = True
            logger.info("Modelo cargado exitosamente")
            logger.info(f"Tipo: {self.info_modelo.get('nombre_modelo', 'Desconocido')}")
            logger.info(f"Accuracy: {self.info_modelo.get('accuracy', 0):.4f}")

        except Exception as e:
            logger.error(f"Error al cargar modelo: {e}")
            raise

    def verificar_modelo_cargado(self):
        """Verifica que el modelo esté cargado"""
        if not self.modelo_cargado:
            raise RuntimeError("El modelo no está cargado. Llama a cargar_modelo() primero.")

    def preparar_datos_estudiante(self, estudiante, semestre_academico=None):
        """
        Prepara los datos de un estudiante para la predicción.
        Adapta datos del estudiante al formato de 34 características del modelo UCI.

        Args:
            estudiante: Instancia del modelo Estudiante
            semestre_academico: Semestre específico (opcional)

        Returns:
            np.array: Array con 34 características en el orden correcto
        """
        # Obtener registros académicos
        registros = RegistroAcademico.objects.filter(estudiante=estudiante)

        if semestre_academico:
            registros = registros.filter(
                asignatura__semestre__lte=semestre_academico
            )

        if not registros.exists():
            raise ValueError(f"No hay registros académicos para el estudiante {estudiante.nombre}")

        # Calcular métricas básicas
        notas = list(registros.values_list('promedio_notas', flat=True))
        asistencias = list(registros.values_list('porcentaje_asistencia', flat=True))
        usos_plataforma = list(registros.values_list('porcentaje_uso_plataforma', flat=True))

        promedio_notas = np.mean(notas)
        asistencia_promedio = np.mean(asistencias)
        uso_plataforma_promedio = np.mean(usos_plataforma)

        total_materias = registros.count()
        materias_aprobadas = registros.filter(promedio_notas__gte=4.0).count()

        # Dividir registros por semestre (1 y 2)
        sem1_registros = list(registros.filter(asignatura__semestre__in=[1, 2]))[:8]  # Primeros 2 semestres
        sem2_registros = list(registros.filter(asignatura__semestre__in=[3]))[:7]     # Tercer semestre

        # Métricas semestre 1
        sem1_notas = [r.promedio_notas for r in sem1_registros]
        sem1_aprobadas = sum(1 for r in sem1_registros if r.promedio_notas >= 4.0)
        sem1_inscritas = len(sem1_registros)
        sem1_promedio = np.mean(sem1_notas) if sem1_notas else promedio_notas

        # Métricas semestre 2
        sem2_notas = [r.promedio_notas for r in sem2_registros]
        sem2_aprobadas = sum(1 for r in sem2_registros if r.promedio_notas >= 4.0)
        sem2_inscritas = len(sem2_registros)
        sem2_promedio = np.mean(sem2_notas) if sem2_notas else promedio_notas

        # Mapear edad (ajustar al rango del dataset: 17-70, promedio 23)
        edad = 20 + (promedio_notas - 4.0)  # Estimación basada en rendimiento
        edad = max(17, min(35, edad))

        # Crear array con las 34 características en el orden del dataset UCI
        # Orden exacto: [0-Marital, 1-AppMode, 2-AppOrder, 3-Course, 4-Daytime, 5-PrevQual,
        #                6-Nacionality, 7-MotherQual, 8-FatherQual, 9-MotherOcc, 10-FatherOcc,
        #                11-Displaced, 12-EdSpecialNeeds, 13-Debtor, 14-TuitionFees, 15-Gender,
        #                16-Scholarship, 17-Age, 18-International, 19-CU1Credit, 20-CU1Enrolled,
        #                21-CU1Eval, 22-CU1Approved, 23-CU1Grade, 24-CU1NoEval, 25-CU2Credit,
        #                26-CU2Enrolled, 27-CU2Eval, 28-CU2Approved, 29-CU2Grade, 30-CU2NoEval,
        #                31-Unemployment, 32-Inflation, 33-GDP]
        caracteristicas = np.array([
            1,  # 0. Marital status (1=single)
            1,  # 1. Application mode
            1,  # 2. Application order
            9500 if not hasattr(estudiante, 'carrera') else estudiante.carrera.id,  # 3. Course
            1,  # 4. Daytime/evening attendance
            promedio_notas * 2.8,  # 5. Previous qualification (grade)
            1,  # 6. Nacionality
            int(min(40, max(1, promedio_notas * 6))),  # 7. Mother's qualification
            int(min(40, max(1, promedio_notas * 5.5))),  # 8. Father's qualification
            int(min(190, max(0, asistencia_promedio * 1.5))),  # 9. Mother's occupation
            int(min(190, max(0, asistencia_promedio * 1.4))),  # 10. Father's occupation
            0,  # 11. Displaced
            0,  # 12. Educational special needs
            1 if asistencia_promedio < 70 else 0,  # 13. Debtor
            0 if asistencia_promedio < 70 else 1,  # 14. Tuition fees up to date
            1,  # 15. Gender
            1 if promedio_notas > 5.5 else 0,  # 16. Scholarship holder
            edad,  # 17. Age at enrollment
            0,  # 18. International
            0,  # 19. Curricular units 1st sem (credited)
            sem1_inscritas,  # 20. Curricular units 1st sem (enrolled)
            sem1_inscritas,  # 21. Curricular units 1st sem (evaluations)
            sem1_aprobadas,  # 22. Curricular units 1st sem (approved)
            sem1_promedio,  # 23. Curricular units 1st sem (grade) - CLAVE
            0,  # 24. Curricular units 1st sem (without evaluations)
            0,  # 25. Curricular units 2nd sem (credited)
            sem2_inscritas,  # 26. Curricular units 2nd sem (enrolled)
            sem2_inscritas,  # 27. Curricular units 2nd sem (evaluations)
            sem2_aprobadas,  # 28. Curricular units 2nd sem (approved) - CLAVE
            sem2_promedio,  # 29. Curricular units 2nd sem (grade) - CLAVE
            0,  # 30. Curricular units 2nd sem (without evaluations)
            7.8,  # 31. Unemployment rate
            6.5,  # 32. Inflation rate
            1.2  # 33. GDP
        ], dtype=float)

        return caracteristicas

    def predecir_estudiante(self, estudiante, semestre_academico, guardar=True):
        """
        Realiza una predicción de deserción para un estudiante.

        Args:
            estudiante: Instancia del modelo Estudiante
            semestre_academico: Semestre en el que se realiza la predicción
            guardar: Si True, guarda la predicción en la base de datos

        Returns:
            dict: Resultados de la predicción
        """
        self.verificar_modelo_cargado()

        try:
            # Preparar datos (ahora retorna array de 34 características)
            caracteristicas = self.preparar_datos_estudiante(estudiante, semestre_academico)
            caracteristicas = caracteristicas.reshape(1, -1)

            # Normalizar
            caracteristicas_normalizadas = self.scaler.transform(caracteristicas)

            # Predecir
            prediccion_numerica = self.modelo.predict(caracteristicas_normalizadas)[0]
            probabilidades = self.modelo.predict_proba(caracteristicas_normalizadas)[0]

            # Convertir predicción
            prediccion_texto = self.label_encoder.inverse_transform([prediccion_numerica])[0]

            # Mapear probabilidades
            prob_dict = {}
            for i, clase in enumerate(self.label_encoder.classes_):
                prob_dict[clase] = float(probabilidades[i])

            # Calcular nivel de riesgo
            prob_desercion = prob_dict.get('Dropout', 0.0)
            nivel_riesgo = self._calcular_nivel_riesgo(prob_desercion)

            # Asignar cohorte
            cohorte = self._asignar_cohorte(prob_desercion)

            # Calcular métricas para guardar
            registros = RegistroAcademico.objects.filter(estudiante=estudiante)
            if semestre_academico:
                registros = registros.filter(asignatura__semestre__lte=semestre_academico)

            notas = list(registros.values_list('promedio_notas', flat=True))
            asistencias = list(registros.values_list('porcentaje_asistencia', flat=True))
            usos_plataforma = list(registros.values_list('porcentaje_uso_plataforma', flat=True))

            promedio_notas = float(np.mean(notas))
            asistencia_promedio = float(np.mean(asistencias))
            uso_plataforma_promedio = float(np.mean(usos_plataforma))
            materias_aprobadas = registros.filter(promedio_notas__gte=4.0).count()
            total_materias = registros.count()

            resultado = {
                'estudiante': estudiante,
                'semestre_academico': semestre_academico,
                'prediccion': prediccion_texto,
                'probabilidad_desercion': prob_desercion,
                'probabilidad_graduacion': prob_dict.get('Graduate', 0.0),
                'probabilidad_inscrito': prob_dict.get('Enrolled', 0.0),
                'nivel_riesgo': nivel_riesgo,
                'cohorte': cohorte,
                'datos_utilizados': {
                    'promedio_general': promedio_notas,
                    'asistencia_promedio': asistencia_promedio,
                    'uso_plataforma_promedio': uso_plataforma_promedio,
                    'materias_aprobadas': materias_aprobadas,
                    'materias_inscritas': total_materias,
                    'tasa_aprobacion': float(materias_aprobadas / total_materias) if total_materias > 0 else 0
                }
            }

            # Guardar predicción si se solicita
            if guardar:
                try:
                    self._guardar_prediccion(resultado)
                except Exception as e:
                    logger.error(f"Error guardando predicción: {e}")
                    import traceback
                    traceback.print_exc()
                    raise

            logger.info(f"Predicción exitosa para {estudiante.nombre}: {prediccion_texto} ({prob_desercion:.2%})")

            return resultado

        except Exception as e:
            logger.error(f"Error en predicción para {estudiante.nombre}: {e}")
            raise

    def _calcular_nivel_riesgo(self, probabilidad_desercion):
        """Calcula el nivel de riesgo basado en la probabilidad de deserción"""
        if probabilidad_desercion >= 0.70:
            return 'critico'
        elif probabilidad_desercion >= 0.50:
            return 'alto'
        elif probabilidad_desercion >= 0.30:
            return 'medio'
        else:
            return 'bajo'

    def _asignar_cohorte(self, probabilidad_desercion):
        """Asigna una cohorte basada en la probabilidad de deserción"""
        if probabilidad_desercion >= 0.70:
            return 1  # Crítico
        elif probabilidad_desercion >= 0.50:
            return 2  # Alto
        else:
            return 3  # Medio-Bajo

    def _guardar_prediccion(self, resultado):
        """Guarda la predicción en la base de datos"""
        datos = resultado['datos_utilizados']

        prediccion = PrediccionDesercion.objects.create(
            estudiante=resultado['estudiante'],
            semestre_academico=resultado['semestre_academico'],
            prediccion=resultado['prediccion'],
            probabilidad_desercion=resultado['probabilidad_desercion'],
            probabilidad_graduacion=resultado['probabilidad_graduacion'],
            probabilidad_inscrito=resultado['probabilidad_inscrito'],
            nivel_riesgo=resultado['nivel_riesgo'],
            cohorte=resultado['cohorte'],
            promedio_notas=datos['promedio_general'],
            asistencia_promedio=datos['asistencia_promedio'],
            uso_plataforma=datos['uso_plataforma_promedio'],
            materias_aprobadas=datos['materias_aprobadas'],
            materias_inscritas=datos['materias_inscritas']
        )

        # Actualizar o crear seguimiento
        self._actualizar_seguimiento(resultado['estudiante'])

        # Generar alertas si es necesario
        self._generar_alertas(prediccion)

        return prediccion

    def _actualizar_seguimiento(self, estudiante):
        """Actualiza el seguimiento del estudiante"""
        seguimiento, created = SeguimientoEstudiante.objects.get_or_create(
            estudiante=estudiante
        )
        seguimiento.actualizar_seguimiento()

    def _generar_alertas(self, prediccion):
        """Genera alertas automáticas basadas en la predicción"""
        # Alerta por riesgo crítico
        if prediccion.nivel_riesgo == 'critico':
            AlertaPrediccion.objects.create(
                prediccion=prediccion,
                tipo_alerta='riesgo_critico',
                prioridad='critica',
                titulo=f'Riesgo Crítico - {prediccion.estudiante.nombre}',
                descripcion=f'Probabilidad de deserción: {prediccion.probabilidad_desercion:.1%}',
                accion_sugerida='Intervención urgente individual requerida'
            )

        # Alerta por cambio de cohorte (si existe predicción anterior)
        predicciones_anteriores = PrediccionDesercion.objects.filter(
            estudiante=prediccion.estudiante,
            semestre_academico__lt=prediccion.semestre_academico
        ).order_by('-semestre_academico')

        if predicciones_anteriores.exists():
            ultima_anterior = predicciones_anteriores.first()

            # Si empeoró de cohorte
            if prediccion.cohorte < ultima_anterior.cohorte:
                AlertaPrediccion.objects.create(
                    prediccion=prediccion,
                    tipo_alerta='cambio_cohorte',
                    prioridad='alta',
                    titulo=f'Cambio de Cohorte - {prediccion.estudiante.nombre}',
                    descripcion=f'Pasó de Cohorte {ultima_anterior.cohorte} a Cohorte {prediccion.cohorte}',
                    accion_sugerida='Revisar factores que causaron el cambio'
                )

            # Si mejoró significativamente
            cambio_prob = prediccion.probabilidad_desercion - ultima_anterior.probabilidad_desercion
            if cambio_prob <= -0.15:
                AlertaPrediccion.objects.create(
                    prediccion=prediccion,
                    tipo_alerta='mejora_significativa',
                    prioridad='baja',
                    titulo=f'Mejora Significativa - {prediccion.estudiante.nombre}',
                    descripcion=f'Reducción de riesgo: {abs(cambio_prob):.1%}',
                    accion_sugerida='Documentar factores de éxito para replicar'
                )

            # Si empeoró significativamente
            elif cambio_prob >= 0.15:
                AlertaPrediccion.objects.create(
                    prediccion=prediccion,
                    tipo_alerta='deterioro_significativo',
                    prioridad='alta',
                    titulo=f'Deterioro Significativo - {prediccion.estudiante.nombre}',
                    descripcion=f'Aumento de riesgo: {cambio_prob:.1%}',
                    accion_sugerida='Evaluación inmediata de la situación del estudiante'
                )

    def predecir_multiples_estudiantes(self, estudiantes_ids, semestre_academico):
        """
        Realiza predicciones para múltiples estudiantes.

        Args:
            estudiantes_ids: Lista de IDs de estudiantes
            semestre_academico: Semestre en el que se realiza la predicción

        Returns:
            dict: Resumen de las predicciones realizadas
        """
        resultados = {
            'exitosas': 0,
            'fallidas': 0,
            'errores': [],
            'predicciones': []
        }

        for est_id in estudiantes_ids:
            try:
                estudiante = Estudiante.objects.get(id_estudiante=est_id)
                resultado = self.predecir_estudiante(estudiante, semestre_academico, guardar=True)
                # Solo guardar datos serializables en el resultado
                resultados['predicciones'].append({
                    'estudiante_id': est_id,
                    'prediccion': resultado['prediccion'],
                    'probabilidad_desercion': resultado['probabilidad_desercion'],
                    'nivel_riesgo': resultado['nivel_riesgo'],
                    'cohorte': resultado['cohorte']
                })
                resultados['exitosas'] += 1
            except Exception as e:
                resultados['fallidas'] += 1
                resultados['errores'].append({
                    'estudiante_id': est_id,
                    'error': str(e)
                })
                logger.error(f"Error prediciendo estudiante {est_id}: {e}")

        return resultados

    def obtener_cohorte(self, numero_cohorte, semestre_academico):
        """
        Obtiene información de una cohorte específica.

        Args:
            numero_cohorte: Número de la cohorte (1, 2, 3)
            semestre_academico: Semestre académico

        Returns:
            dict: Información de la cohorte y sus estudiantes
        """
        predicciones = PrediccionDesercion.objects.filter(
            cohorte=numero_cohorte,
            semestre_academico=semestre_academico
        ).select_related('estudiante').order_by('-probabilidad_desercion')

        estudiantes = []
        for pred in predicciones:
            estudiantes.append({
                'estudiante_id': pred.estudiante.id_estudiante,
                'nombre': pred.estudiante.nombre,
                'probabilidad_desercion': pred.probabilidad_desercion,
                'nivel_riesgo': pred.nivel_riesgo,
                'prediccion': pred.get_prediccion_display(),
                'promedio_notas': pred.promedio_notas,
                'asistencia': pred.asistencia_promedio
            })

        return {
            'cohorte': numero_cohorte,
            'semestre': semestre_academico,
            'total_estudiantes': len(estudiantes),
            'estudiantes': estudiantes
        }

    def obtener_seguimiento_estudiante(self, estudiante_id):
        """
        Obtiene el seguimiento temporal completo de un estudiante.

        Args:
            estudiante_id: ID del estudiante

        Returns:
            dict: Información del seguimiento temporal
        """
        try:
            estudiante = Estudiante.objects.get(id_estudiante=estudiante_id)
            predicciones = PrediccionDesercion.objects.filter(
                estudiante=estudiante
            ).order_by('semestre_academico')

            if not predicciones.exists():
                return {
                    'estudiante_id': estudiante_id,
                    'nombre': estudiante.nombre,
                    'tiene_predicciones': False,
                    'mensaje': 'No hay predicciones para este estudiante'
                }

            # Preparar datos para gráfico
            semestres = []
            probabilidades_desercion = []
            cohortes = []
            niveles_riesgo = []

            for pred in predicciones:
                semestres.append(pred.semestre_academico)
                probabilidades_desercion.append(pred.probabilidad_desercion)
                cohortes.append(pred.cohorte)
                niveles_riesgo.append(pred.nivel_riesgo)

            # Calcular tendencia
            if len(probabilidades_desercion) >= 2:
                cambio_total = probabilidades_desercion[-1] - probabilidades_desercion[0]
                if cambio_total >= 0.15:
                    tendencia = 'deterioro_significativo'
                elif cambio_total >= 0.05:
                    tendencia = 'deterioro_leve'
                elif cambio_total <= -0.15:
                    tendencia = 'mejora_significativa'
                elif cambio_total <= -0.05:
                    tendencia = 'mejora_leve'
                else:
                    tendencia = 'estable'
            else:
                tendencia = 'sin_datos_suficientes'
                cambio_total = 0

            return {
                'estudiante_id': estudiante_id,
                'nombre': estudiante.nombre,
                'tiene_predicciones': True,
                'total_semestres': len(semestres),
                'semestres': semestres,
                'probabilidades_desercion': probabilidades_desercion,
                'cohortes': cohortes,
                'niveles_riesgo': niveles_riesgo,
                'tendencia': tendencia,
                'cambio_total': cambio_total,
                'ultimo_nivel_riesgo': niveles_riesgo[-1] if niveles_riesgo else 'desconocido'
            }

        except Estudiante.DoesNotExist:
            return {
                'error': f'Estudiante con ID {estudiante_id} no encontrado'
            }

    def inicializar_cohortes(self, semestre_academico):
        """
        Inicializa las cohortes para un semestre específico.

        Args:
            semestre_academico: Semestre académico

        Returns:
            list: Lista de cohortes creadas
        """
        definiciones_cohortes = {
            1: {
                'nombre': 'Cohorte 1 - Riesgo Crítico',
                'descripcion': 'Estudiantes con riesgo crítico de deserción (≥70%)',
                'acciones': [
                    'Intervención urgente individual',
                    'Seguimiento semanal',
                    'Apoyo académico intensivo',
                    'Contacto con familia'
                ],
                'umbral_min': 0.70,
                'umbral_max': 1.0,
                'color': '#FF0000'
            },
            2: {
                'nombre': 'Cohorte 2 - Riesgo Alto',
                'descripcion': 'Estudiantes con riesgo alto de deserción (50-70%)',
                'acciones': [
                    'Seguimiento quincenal',
                    'Tutorías personalizadas',
                    'Evaluación de necesidades',
                    'Plan de mejora académica'
                ],
                'umbral_min': 0.50,
                'umbral_max': 0.70,
                'color': '#FF8800'
            },
            3: {
                'nombre': 'Cohorte 3 - Riesgo Medio-Bajo',
                'descripcion': 'Estudiantes con riesgo medio a bajo (<50%)',
                'acciones': [
                    'Seguimiento mensual',
                    'Monitoreo preventivo',
                    'Apoyo grupal',
                    'Refuerzo académico general'
                ],
                'umbral_min': 0.0,
                'umbral_max': 0.50,
                'color': '#FFCC00'
            }
        }

        cohortes_creadas = []

        for numero, definicion in definiciones_cohortes.items():
            cohorte, created = CohorteEstudiantil.objects.update_or_create(
                numero_cohorte=numero,
                semestre_academico=semestre_academico,
                defaults={
                    'nombre': definicion['nombre'],
                    'descripcion': definicion['descripcion'],
                    'acciones_recomendadas': definicion['acciones'],
                    'umbral_min': definicion['umbral_min'],
                    'umbral_max': definicion['umbral_max'],
                    'color': definicion['color']
                }
            )

            # Actualizar estadísticas
            cohorte.actualizar_estadisticas()
            cohortes_creadas.append(cohorte)

        logger.info(f"Cohortes inicializadas para semestre {semestre_academico}")
        return cohortes_creadas


# Instancia global del servicio
servicio_prediccion = ServicioPrediccionDesercion()
