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