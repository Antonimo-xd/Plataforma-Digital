# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class Usuario(AbstractUser):
    ROLES = [
        ('analista_cpa', 'Analista CPA'),
        ('coordinador_cpa', 'Coordinador CPA'),
        ('coordinador_carrera', 'Coordinador de Carrera'),
        ('admin', 'Administrador'),
    ]
    rol = models.CharField(max_length=20, choices=ROLES)
    telefono = models.CharField(max_length=15, blank=True)
    
    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"

class Carrera(models.Model):
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=10, unique=True)
    coordinador = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return self.nombre

class Estudiante(models.Model):
    id_estudiante = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=200)
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE)
    ingreso_año = models.IntegerField()
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.nombre} - {self.carrera.nombre}"

class Asignatura(models.Model):
    id_asignatura = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=300)
    semestre = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(8)])
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f"{self.nombre} - Semestre {self.semestre}"

class RegistroAcademico(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    nota1 = models.FloatField(validators=[MinValueValidator(1.0), MaxValueValidator(7.0)])
    nota2 = models.FloatField(validators=[MinValueValidator(1.0), MaxValueValidator(7.0)])
    nota3 = models.FloatField(validators=[MinValueValidator(1.0), MaxValueValidator(7.0)])
    nota4 = models.FloatField(validators=[MinValueValidator(1.0), MaxValueValidator(7.0)])
    promedio_notas = models.FloatField()
    porcentaje_asistencia = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    porcentaje_uso_plataforma = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    fecha_registro = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['estudiante', 'asignatura']
    
    def save(self, *args, **kwargs):
        # Calcular promedio automáticamente
        self.promedio_notas = round((self.nota1 + self.nota2 + self.nota3 + self.nota4) / 4, 2)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.asignatura.nombre}: {self.promedio_notas}"

class CriterioAnomalia(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE, null=True, blank=True)
    semestre = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(8)])
    
    # Parámetros del modelo
    contamination_rate = models.FloatField(default=0.1, validators=[MinValueValidator(0.01), MaxValueValidator(0.5)])
    n_estimators = models.IntegerField(default=100, validators=[MinValueValidator(10), MaxValueValidator(500)])
    
    # Umbrales personalizables
    umbral_promedio_min = models.FloatField(default=3.0)
    umbral_asistencia_min = models.FloatField(default=70.0)
    umbral_uso_plataforma_min = models.FloatField(default=60.0)
    umbral_variacion_notas = models.FloatField(default=1.5)
    
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    creado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.nombre} - {self.carrera.nombre if self.carrera else 'General'}"

class DeteccionAnomalia(models.Model):
    """
    Modelo para almacenar detecciones de anomalías académicas
    """
    TIPOS_ANOMALIA = [
        ('bajo_rendimiento', 'Bajo Rendimiento'),
        ('baja_asistencia', 'Baja Asistencia'),
        ('alta_variabilidad', 'Alta Variabilidad'),
        ('uso_ineficiente_plataforma', 'Uso Ineficiente de Plataforma'),
        ('cambio_drastico_semestre', 'Cambio Drástico entre Semestres'),
        ('multiple', 'Múltiples Factores'),
    ]
    
    ESTADOS = [
        ('detectado', 'Detectado'),
        ('en_revision', 'En Revisión'),
        ('intervencion_activa', 'Intervención Activa'),
        ('resuelto', 'Resuelto'),
        ('falso_positivo', 'Falso Positivo'),
    ]
    
    NIVELES_CRITICIDAD = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
    ]
    
    # ✅ CORREGIDO: Estados coinciden con ESTADOS arriba
    TRANSICIONES_ESTADO = {
        'detectado': ['en_revision', 'falso_positivo'],  # ← Cambiado
        'en_revision': ['resuelto', 'intervencion_activa', 'falso_positivo'],  # ← Cambiado
        'intervencion_activa': ['resuelto'],  # ← Cambiado
        'resuelto': [],
        'falso_positivo': []
    }

    tipo_anomalia = models.CharField(max_length=30, choices=TIPOS_ANOMALIA)
    score_anomalia = models.FloatField()  # Score del Isolation Forest
    confianza = models.FloatField()  # Nivel de confianza de la detección
    promedio_general = models.FloatField()
    asistencia_promedio = models.FloatField()
    uso_plataforma_promedio = models.FloatField()
    variacion_notas = models.FloatField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='detectado')
    prioridad = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    fecha_deteccion = models.DateTimeField(default=timezone.now)
    fecha_ultima_actualizacion = models.DateTimeField(auto_now=True)
    observaciones = models.TextField(blank=True)
    criterio_usado = models.ForeignKey(CriterioAnomalia, on_delete=models.SET_NULL, null=True)
    revisado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    nivel_criticidad = models.CharField(
        max_length=10,
        choices=NIVELES_CRITICIDAD,
        default='media',
        help_text='Nivel de criticidad: baja, media o alta'
    )
    
    class Meta:
        verbose_name = "Detección de Anomalía"
        verbose_name_plural = "Detecciones de Anomalías"
        ordering = ['-fecha_deteccion']  # ✅ Solo una vez
    
    def __str__(self):
        # ✅ Solo un __str__, el más completo
        return f"{self.estudiante.nombre} - {self.get_tipo_anomalia_display()} ({self.get_estado_display()})"

    def es_transicion_valida(self, nuevo_estado):
        """Valida si el cambio de estado es permitido"""
        estados_permitidos = self.TRANSICIONES_ESTADO.get(self.estado, [])
        return nuevo_estado in estados_permitidos

    def actualizar_estado(self, nuevo_estado, observaciones='', usuario=None):
        """
        Actualiza el estado de la anomalía con validaciones
        
        🎓 NOTA: Cambié el nombre de actualizar_anomalia_estado a actualizar_estado
        para que sea más simple de usar
        """
        if not self.es_transicion_valida(nuevo_estado):
            raise ValueError(
                f"No se puede cambiar de '{self.estado}' a '{nuevo_estado}'"
            )
        
        # Guardar estado anterior para auditoría
        estado_anterior = self.estado
        
        # Actualizar
        self.estado = nuevo_estado
        self.observaciones = observaciones
        self.fecha_ultima_actualizacion = timezone.now()  # ✅ Corregido campo
        
        if usuario:
            self.revisado_por = usuario  # ✅ Corregido nombre de campo
        
        self.save()
        
        # Registrar en log de auditoría
        self.registrar_cambio_estado(estado_anterior, nuevo_estado, usuario)
        
        return True

    def registrar_cambio_estado(self, estado_anterior, estado_nuevo, usuario):
        """Registra el cambio de estado en log de auditoría"""
        # Aquí podrías crear un modelo LogCambioEstado si quieres
        # trazabilidad completa
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Anomalía {self.id}: {estado_anterior} → {estado_nuevo} "
            f"por {usuario.get_full_name() if usuario else 'Sistema'}"
        )
    
    def puede_ser_derivada(self):
        """Verifica si la anomalía puede ser derivada"""
        return self.estado in ['detectado', 'en_revision', 'intervencion_activa']
    
    def es_critica(self):
        """Verifica si la anomalía es de nivel crítico"""
        return self.nivel_criticidad == 'alta'
    
    def dias_sin_atencion(self):
        """Calcula días transcurridos sin atención"""
        return (timezone.now() - self.fecha_deteccion).days

class InstanciaApoyo(models.Model):
    TIPOS_APOYO = [
        ('tutoria', 'Tutoría Académica'),
        ('clinica', 'Clínica de Aprendizaje'),
        ('psicopedagogia', 'Psicopedagogía'),
        ('orientacion', 'Orientación Estudiantil'),
        ('bienestar', 'Bienestar Estudiantil'),
    ]
    
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPOS_APOYO)
    contacto = models.CharField(max_length=200)
    email = models.EmailField()
    telefono = models.CharField(max_length=15, blank=True)
    descripcion = models.TextField()
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

class Derivacion(models.Model):
    ESTADOS_DERIVACION = [
        ('pendiente', 'Pendiente'),
        ('enviada', 'Enviada'),
        ('recibida', 'Recibida por Instancia'),
        ('en_proceso', 'En Proceso'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    
    deteccion_anomalia = models.ForeignKey(DeteccionAnomalia, on_delete=models.CASCADE)
    instancia_apoyo = models.ForeignKey(InstanciaApoyo, on_delete=models.CASCADE)
    
    fecha_derivacion = models.DateTimeField(default=timezone.now)
    derivado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    
    estado = models.CharField(max_length=15, choices=ESTADOS_DERIVACION, default='pendiente')
    motivo = models.TextField()
    observaciones_derivacion = models.TextField(blank=True)
    respuesta_instancia = models.TextField(blank=True)
    
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    fecha_seguimiento = models.DateTimeField(null=True, blank=True)
    
    PRIORIDADES_DERIVACION = [
        (1, 'Baja'),
        (2, 'Normal'),
        (3, 'Alta'),
        (4, 'Urgente'),
        (5, 'Crítica'),
    ]
    prioridad = models.IntegerField(
        choices=PRIORIDADES_DERIVACION, 
        default=2,
        help_text="Prioridad específica de la derivación"
    )
    
    # Campo para observaciones de seguimiento
    observaciones_seguimiento = models.TextField(
        blank=True,
        help_text="Observaciones y seguimiento de la derivación"
    )
    
    def __str__(self):
        return f"{self.deteccion_anomalia.estudiante.nombre} -> {self.instancia_apoyo.nombre}"

class AlertaAutomatica(models.Model):
    TIPOS_ALERTA = [
        ('nueva_anomalia', 'Nueva Anomalía Detectada'),
        ('anomalia_critica', 'Anomalía Crítica'),
        ('asignatura_critica', 'Asignatura con Múltiples Anomalías'),
        ('seguimiento_vencido', 'Seguimiento Vencido'),
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPOS_ALERTA)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    
    deteccion_relacionada = models.ForeignKey(DeteccionAnomalia, on_delete=models.CASCADE, null=True, blank=True)
    asignatura_relacionada = models.ForeignKey(Asignatura, on_delete=models.CASCADE, null=True, blank=True)
    
    destinatarios = models.ManyToManyField(Usuario)
    
    fecha_creacion = models.DateTimeField(default=timezone.now)
    leida = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.titulo}"

class EjecucionAnalisis(models.Model):
    criterio_usado = models.ForeignKey(CriterioAnomalia, on_delete=models.CASCADE)
    ejecutado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    
    fecha_ejecucion = models.DateTimeField(default=timezone.now)
    
    total_estudiantes_analizados = models.IntegerField()
    anomalias_detectadas = models.IntegerField()
    porcentaje_anomalias = models.FloatField()
    
    parametros_modelo = models.JSONField()  # Almacenar parámetros del Isolation Forest
    metricas_modelo = models.JSONField()    # Almacenar métricas de rendimiento
    
    tiempo_ejecucion = models.FloatField()  # En segundos
    exitoso = models.BooleanField(default=True)
    mensaje_error = models.TextField(blank=True)
    
    def __str__(self):
        return f"Análisis {self.fecha_ejecucion.strftime('%Y-%m-%d %H:%M')} - {self.anomalias_detectadas} anomalías"

# Modelo auxiliar para análisis de asignaturas críticas
class AsignaturaCritica(models.Model):
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    semestre_analizado = models.CharField(max_length=10)  # ej: "2024-1"
    total_estudiantes = models.IntegerField()
    estudiantes_anomalos = models.IntegerField()
    porcentaje_anomalias = models.FloatField()
    
    # Métricas agregadas
    promedio_general_asignatura = models.FloatField()
    asistencia_promedio_asignatura = models.FloatField()
    uso_plataforma_promedio = models.FloatField()
    
    fecha_analisis = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['asignatura', 'semestre_analizado']
        ordering = ['-porcentaje_anomalias']
    
    def __str__(self):
        return f"{self.asignatura.nombre} - {self.porcentaje_anomalias:.1f}% anomalías"
    
# ===============================================================================
# MODELOS PARA PREDICCIÓN DE DESERCIÓN ESTUDIANTIL
# ===============================================================================


class PrediccionDesercion(models.Model):
    """
    Modelo para almacenar las predicciones de deserción de estudiantes.
    Utiliza el modelo de Machine Learning entrenado.
    """
    ESTADOS_PREDICCION = [
        ('Dropout', 'Deserción'),
        ('Enrolled', 'Inscrito'),
        ('Graduate', 'Graduado'),
    ]

    NIVELES_RIESGO = [
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto'),
        ('critico', 'Crítico'),
    ]

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='predicciones')
    semestre_academico = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Semestre en el que se realizó la predicción"
    )

    # Predicción del modelo
    prediccion = models.CharField(max_length=10, choices=ESTADOS_PREDICCION)

    # Probabilidades
    probabilidad_desercion = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    probabilidad_graduacion = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    probabilidad_inscrito = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )

    # Nivel de riesgo calculado
    nivel_riesgo = models.CharField(max_length=10, choices=NIVELES_RIESGO)

    # Cohorte asignada
    cohorte = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text="1=Crítico, 2=Alto, 3=Medio-Bajo"
    )

    # Métricas usadas para la predicción
    promedio_notas = models.FloatField()
    asistencia_promedio = models.FloatField()
    uso_plataforma = models.FloatField()
    materias_aprobadas = models.IntegerField()
    materias_inscritas = models.IntegerField()

    # Metadatos
    fecha_prediccion = models.DateTimeField(default=timezone.now)
    modelo_version = models.CharField(max_length=50, default="v1.0")

    class Meta:
        verbose_name = "Predicción de Deserción"
        verbose_name_plural = "Predicciones de Deserción"
        ordering = ['-fecha_prediccion', '-probabilidad_desercion']
        indexes = [
            models.Index(fields=['estudiante', 'semestre_academico']),
            models.Index(fields=['cohorte', 'nivel_riesgo']),
        ]

    def __str__(self):
        return f"{self.estudiante.nombre} - S{self.semestre_academico} - {self.get_prediccion_display()} ({self.probabilidad_desercion:.1%})"

    def es_riesgo_alto(self):
        """Verifica si el estudiante está en riesgo alto o crítico"""
        return self.nivel_riesgo in ['alto', 'critico']

    def obtener_color_riesgo(self):
        """Retorna el color asociado al nivel de riesgo"""
        colores = {
            'bajo': '#4CAF50',
            'medio': '#FFCC00',
            'alto': '#FF8800',
            'critico': '#FF0000'
        }
        return colores.get(self.nivel_riesgo, '#999999')

class SeguimientoEstudiante(models.Model):
    """
    Modelo para el seguimiento temporal de un estudiante a través de los semestres.
    Permite visualizar la evolución del riesgo de deserción.
    """
    estudiante = models.OneToOneField(Estudiante, on_delete=models.CASCADE, related_name='seguimiento')

    # Historial de predicciones (JSON)
    historial_predicciones = models.JSONField(
        default=list,
        help_text="Lista de predicciones por semestre"
    )

    # Tendencia general
    tendencia = models.CharField(
        max_length=30,
        choices=[
            ('mejora_significativa', 'Mejora Significativa'),
            ('mejora_leve', 'Mejora Leve'),
            ('estable', 'Estable'),
            ('deterioro_leve', 'Deterioro Leve'),
            ('deterioro_significativo', 'Deterioro Significativo'),
            ('sin_datos_suficientes', 'Sin Datos Suficientes'),
        ],
        default='sin_datos_suficientes'
    )

    # Cambio total en probabilidad de deserción
    cambio_total_riesgo = models.FloatField(default=0.0)

    # Estado actual
    ultimo_nivel_riesgo = models.CharField(max_length=10, blank=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    # Alertas generadas
    tiene_alertas_activas = models.BooleanField(default=False)
    total_alertas = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Seguimiento de Estudiante"
        verbose_name_plural = "Seguimientos de Estudiantes"

    def __str__(self):
        return f"Seguimiento: {self.estudiante.nombre}"

    def actualizar_seguimiento(self):
        """Actualiza el seguimiento con la última predicción"""
        predicciones = PrediccionDesercion.objects.filter(
            estudiante=self.estudiante
        ).order_by('semestre_academico')

        if predicciones.count() < 2:
            self.tendencia = 'sin_datos_suficientes'
            self.cambio_total_riesgo = 0.0
        else:
            primera = predicciones.first()
            ultima = predicciones.last()

            self.cambio_total_riesgo = ultima.probabilidad_desercion - primera.probabilidad_desercion

            # Determinar tendencia
            if self.cambio_total_riesgo >= 0.15:
                self.tendencia = 'deterioro_significativo'
            elif self.cambio_total_riesgo >= 0.05:
                self.tendencia = 'deterioro_leve'
            elif self.cambio_total_riesgo <= -0.15:
                self.tendencia = 'mejora_significativa'
            elif self.cambio_total_riesgo <= -0.05:
                self.tendencia = 'mejora_leve'
            else:
                self.tendencia = 'estable'

            self.ultimo_nivel_riesgo = ultima.nivel_riesgo

        # Actualizar historial
        hist_list = []
        for pred in predicciones.values('semestre_academico', 'probabilidad_desercion', 'cohorte', 'prediccion', 'fecha_prediccion'):
            # Convertir datetime a string para JSON serialization
            pred_dict = dict(pred)
            if 'fecha_prediccion' in pred_dict and pred_dict['fecha_prediccion']:
                pred_dict['fecha_prediccion'] = pred_dict['fecha_prediccion'].isoformat()
            hist_list.append(pred_dict)
        self.historial_predicciones = hist_list

        self.save()

class CohorteEstudiantil(models.Model):
    """
    Modelo para agrupar estudiantes en cohortes según su riesgo de deserción.
    """
    COHORTES = [
        (1, 'Cohorte 1 - Riesgo Crítico'),
        (2, 'Cohorte 2 - Riesgo Alto'),
        (3, 'Cohorte 3 - Riesgo Medio-Bajo'),
    ]

    nombre = models.CharField(max_length=100)
    numero_cohorte = models.IntegerField(choices=COHORTES)
    semestre_academico = models.IntegerField()

    # Descripción y acciones recomendadas
    descripcion = models.TextField()
    acciones_recomendadas = models.JSONField(default=list)

    # Umbrales de probabilidad
    umbral_min = models.FloatField()
    umbral_max = models.FloatField()

    # Color para visualización
    color = models.CharField(max_length=7, default='#999999')

    # Estadísticas
    total_estudiantes = models.IntegerField(default=0)
    porcentaje_total = models.FloatField(default=0.0)

    # Metadatos
    fecha_creacion = models.DateTimeField(default=timezone.now)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cohorte Estudiantil"
        verbose_name_plural = "Cohortes Estudiantiles"
        unique_together = ['numero_cohorte', 'semestre_academico']
        ordering = ['numero_cohorte']

    def __str__(self):
        return f"{self.nombre} - Semestre {self.semestre_academico}"

    def obtener_estudiantes(self):
        """Retorna los estudiantes que pertenecen a esta cohorte"""
        return PrediccionDesercion.objects.filter(
            cohorte=self.numero_cohorte,
            semestre_academico=self.semestre_academico
        ).select_related('estudiante')

    def actualizar_estadisticas(self):
        """Actualiza las estadísticas de la cohorte"""
        estudiantes = self.obtener_estudiantes()
        self.total_estudiantes = estudiantes.count()

        total_semestre = PrediccionDesercion.objects.filter(
            semestre_academico=self.semestre_academico
        ).count()

        if total_semestre > 0:
            self.porcentaje_total = (self.total_estudiantes / total_semestre) * 100

        self.save()

class AlertaPrediccion(models.Model):
    """
    Modelo para alertas generadas automáticamente basadas en las predicciones.
    """
    TIPOS_ALERTA = [
        ('riesgo_critico', 'Riesgo Crítico Detectado'),
        ('deterioro_significativo', 'Deterioro Significativo'),
        ('cambio_cohorte', 'Cambio de Cohorte'),
        ('mejora_significativa', 'Mejora Significativa'),
    ]

    PRIORIDADES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]

    prediccion = models.ForeignKey(PrediccionDesercion, on_delete=models.CASCADE, related_name='alertas')
    tipo_alerta = models.CharField(max_length=30, choices=TIPOS_ALERTA)
    prioridad = models.CharField(max_length=10, choices=PRIORIDADES)

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    accion_sugerida = models.TextField()

    # Estado
    activa = models.BooleanField(default=True)
    fecha_generacion = models.DateTimeField(default=timezone.now)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    revisada_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Alerta de Predicción"
        verbose_name_plural = "Alertas de Predicción"
        ordering = ['-fecha_generacion', '-prioridad']

    def __str__(self):
        return f"{self.titulo} - {self.prediccion.estudiante.nombre}"

    def marcar_como_revisada(self, usuario):
        """Marca la alerta como revisada"""
        self.fecha_revision = timezone.now()
        self.revisada_por = usuario
        self.activa = False
        self.save()

class ComparacionIntervenciones(models.Model):
    """
    Modelo para comparar el estado de un estudiante antes y después de intervenciones.
    """
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='comparaciones')

    # Predicciones a comparar
    prediccion_antes = models.ForeignKey(
        PrediccionDesercion,
        on_delete=models.CASCADE,
        related_name='comparaciones_como_antes'
    )
    prediccion_despues = models.ForeignKey(
        PrediccionDesercion,
        on_delete=models.CASCADE,
        related_name='comparaciones_como_despues'
    )

    # Cambios detectados
    cambio_probabilidad = models.FloatField()
    cambio_cohorte = models.IntegerField()

    # Clasificación del cambio
    clasificacion = models.CharField(
        max_length=30,
        choices=[
            ('mejora_significativa', 'Mejora Significativa'),
            ('mejora_leve', 'Mejora Leve'),
            ('estable', 'Estable'),
            ('deterioro_leve', 'Deterioro Leve'),
            ('deterioro_significativo', 'Deterioro Significativo'),
        ]
    )

    # Intervención realizada
    intervencion_descripcion = models.TextField(blank=True)
    tipo_intervencion = models.CharField(max_length=100, blank=True)

    # Metadatos
    fecha_comparacion = models.DateTimeField(default=timezone.now)
    creada_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Comparación de Intervención"
        verbose_name_plural = "Comparaciones de Intervenciones"
        ordering = ['-fecha_comparacion']

    def __str__(self):
        return f"Comparación: {self.estudiante.nombre} - S{self.prediccion_antes.semestre_academico} vs S{self.prediccion_despues.semestre_academico}"

