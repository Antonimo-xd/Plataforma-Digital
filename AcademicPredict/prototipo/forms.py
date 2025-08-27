# forms.py
from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import *

class CriterioAnomaliaForm(forms.ModelForm):
    class Meta:
        model = CriterioAnomalia
        fields = [
            'nombre', 'descripcion', 'carrera', 'semestre',
            'contamination_rate', 'n_estimators',
            'umbral_promedio_min', 'umbral_asistencia_min',
            'umbral_uso_plataforma_min', 'umbral_variacion_notas'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Criterio Informática Semestre 1'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción del criterio y sus objetivos...'
            }),
            'carrera': forms.Select(attrs={'class': 'form-control'}),
            'semestre': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('', 'Todos los semestres'),
                (1, 'Semestre 1'), (2, 'Semestre 2'), (3, 'Semestre 3'), (4, 'Semestre 4'),
                (5, 'Semestre 5'), (6, 'Semestre 6'), (7, 'Semestre 7'), (8, 'Semestre 8')
            ]),
            'contamination_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'max': '0.5',
                'placeholder': '0.1 (10% esperado de anomalías)'
            }),
            'n_estimators': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '10',
                'max': '500',
                'placeholder': '100 (número de árboles)'
            }),
            'umbral_promedio_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '1.0',
                'max': '7.0',
                'placeholder': '3.0'
            }),
            'umbral_asistencia_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '70.0'
            }),
            'umbral_uso_plataforma_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '60.0'
            }),
            'umbral_variacion_notas': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '6.0',
                'placeholder': '1.5'
            }),
        }
        labels = {
            'nombre': 'Nombre del Criterio',
            'descripcion': 'Descripción',
            'carrera': 'Carrera (opcional)',
            'semestre': 'Semestre específico (opcional)',
            'contamination_rate': 'Tasa de Contaminación',
            'n_estimators': 'Número de Estimadores',
            'umbral_promedio_min': 'Promedio Mínimo Esperado',
            'umbral_asistencia_min': 'Asistencia Mínima Esperada (%)',
            'umbral_uso_plataforma_min': 'Uso Mínimo de Plataforma (%)',
            'umbral_variacion_notas': 'Variación Máxima de Notas Aceptable',
        }
        help_texts = {
            'contamination_rate': 'Proporción esperada de anomalías (0.01 = 1%, 0.1 = 10%)',
            'n_estimators': 'Número de árboles en el Isolation Forest (más árboles = mayor precisión)',
            'umbral_promedio_min': 'Promedio mínimo esperado en escala 1.0-7.0',
            'umbral_asistencia_min': 'Porcentaje mínimo de asistencia esperado',
            'umbral_uso_plataforma_min': 'Porcentaje mínimo de uso de plataforma esperado',
            'umbral_variacion_notas': 'Variación máxima aceptable entre notas del estudiante',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['carrera'].queryset = Carrera.objects.all()
        self.fields['carrera'].empty_label = "Todas las carreras"

class DerivacionForm(forms.ModelForm):
    class Meta:
        model = Derivacion
        fields = ['instancia_apoyo', 'motivo', 'observaciones_derivacion']
        widgets = {
            'instancia_apoyo': forms.Select(attrs={'class': 'form-control'}),
            'motivo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describa el motivo de la derivación y las acciones recomendadas...'
            }),
            'observaciones_derivacion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)...'
            }),
        }
        labels = {
            'instancia_apoyo': 'Instancia de Apoyo',
            'motivo': 'Motivo de la Derivación',
            'observaciones_derivacion': 'Observaciones Adicionales',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['instancia_apoyo'].queryset = InstanciaApoyo.objects.filter(activo=True)

class FiltroAnomaliasForm(forms.Form):
    busqueda = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre o ID de estudiante...'
        })
    )
    
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados')] + DeteccionAnomalia.ESTADOS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tipo_anomalia = forms.ChoiceField(
        choices=[('', 'Todos los tipos')] + DeteccionAnomalia.TIPOS_ANOMALIA,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    prioridad = forms.ChoiceField(
        choices=[('', 'Todas las prioridades')] + [(i, f'Prioridad {i}') for i in range(1, 6)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

class ActualizarEstadoAnomaliaForm(forms.Form):
    estado = forms.ChoiceField(
        choices=DeteccionAnomalia.ESTADOS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones sobre el cambio de estado...'
        })
    )

class InstanciaApoyoForm(forms.ModelForm):
    class Meta:
        model = InstanciaApoyo
        fields = ['nombre', 'tipo', 'contacto', 'email', 'telefono', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class CarreraForm(forms.ModelForm):
    class Meta:
        model = Carrera
        fields = ['nombre', 'codigo', 'coordinador']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'coordinador': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['coordinador'].queryset = Usuario.objects.filter(rol='coordinador_carrera')

class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = ['id_estudiante', 'nombre', 'carrera', 'ingreso_año']
        widgets = {
            'id_estudiante': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'carrera': forms.Select(attrs={'class': 'form-control'}),
            'ingreso_año': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class AsignaturaForm(forms.ModelForm):
    class Meta:
        model = Asignatura
        fields = ['id_asignatura', 'nombre', 'semestre', 'carrera']
        widgets = {
            'id_asignatura': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'semestre': forms.Select(attrs={'class': 'form-control'}, choices=[
                (i, f'Semestre {i}') for i in range(1, 9)
            ]),
            'carrera': forms.Select(attrs={'class': 'form-control'}),
        }

class RegistroAcademicoForm(forms.ModelForm):
    class Meta:
        model = RegistroAcademico
        fields = [
            'estudiante', 'asignatura', 'nota1', 'nota2', 'nota3', 'nota4',
            'porcentaje_asistencia', 'porcentaje_uso_plataforma'
        ]
        widgets = {
            'estudiante': forms.Select(attrs={'class': 'form-control'}),
            'asignatura': forms.Select(attrs={'class': 'form-control'}),
            'nota1': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '1.0', 'max': '7.0'}),
            'nota2': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '1.0', 'max': '7.0'}),
            'nota3': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '1.0', 'max': '7.0'}),
            'nota4': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '1.0', 'max': '7.0'}),
            'porcentaje_asistencia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '100'}),
            'porcentaje_uso_plataforma': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '100'}),
        }

class ImportarDatosForm(forms.Form):
    archivo_estudiantes = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls',
            'title': 'Seleccionar archivo de estudiantes'
        }),
        help_text='Archivo CSV o Excel con columnas: IdEstudiante, Nombre, Carrera, Ingreso_año'
    )
    
    archivo_asignaturas = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls',
            'title': 'Seleccionar archivo de asignaturas'
        }),
        help_text='Archivo CSV o Excel con columnas: Id_Asignatura, NombreAsignatura, Semestre'
    )
    
    archivo_registros = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls',
            'title': 'Seleccionar archivo de registros académicos'
        }),
        help_text='Archivo CSV o Excel con columnas: Id_Estudiante, Id_asignatura, Nota1, Nota2, Nota3, Nota4, % de Asistencia, % de Uso de plataforma'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validar que al menos un archivo fue subido
        archivos = [
            cleaned_data.get('archivo_estudiantes'),
            cleaned_data.get('archivo_asignaturas'),
            cleaned_data.get('archivo_registros')
        ]
        
        if not any(archivos):
            raise forms.ValidationError(
                'Debes seleccionar al menos un archivo para importar.'
            )
        
        # Validar tamaño de archivos (máximo 10MB cada uno)
        for campo, archivo in zip(['archivo_estudiantes', 'archivo_asignaturas', 'archivo_registros'], archivos):
            if archivo and archivo.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError(
                    f'El archivo {campo} es demasiado grande (máximo 10MB).'
                )
        
        return cleaned_data


class FiltroReporteForm(forms.Form):
    fecha_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    fecha_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    carrera = forms.ModelChoiceField(
        queryset=Carrera.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Todas las carreras"
    )
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados')] + DeteccionAnomalia.ESTADOS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tipo_anomalia = forms.ChoiceField(
        choices=[('', 'Todos los tipos')] + DeteccionAnomalia.TIPOS_ANOMALIA,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class ConfiguracionAlertasForm(forms.Form):
    alertas_criticas = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    alertas_nuevas_anomalias = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    alertas_asignaturas_criticas = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    alertas_seguimiento_vencido = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    umbral_critico_porcentaje = forms.FloatField(
        initial=20.0,
        min_value=5.0,
        max_value=50.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1'
        }),
        help_text='Porcentaje de anomalías en asignatura para considerarla crítica'
    )

class BusquedaAvanzadaForm(forms.Form):
    termino_busqueda = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar estudiantes, asignaturas...'
        })
    )
    
    campo_busqueda = forms.ChoiceField(
        choices=[
            ('todos', 'Todos los campos'),
            ('nombre_estudiante', 'Nombre del estudiante'),
            ('id_estudiante', 'ID del estudiante'),
            ('nombre_asignatura', 'Nombre de asignatura'),
            ('carrera', 'Carrera'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    rango_score_min = forms.FloatField(
        required=False,
        min_value=-1.0,
        max_value=1.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Score mínimo'
        })
    )
    
    rango_score_max = forms.FloatField(
        required=False,
        min_value=-1.0,
        max_value=1.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Score máximo'
        })
    )
    
    promedio_min = forms.FloatField(
        required=False,
        min_value=1.0,
        max_value=7.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'placeholder': 'Promedio mínimo'
        })
    )
    
    promedio_max = forms.FloatField(
        required=False,
        min_value=1.0,
        max_value=7.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'placeholder': 'Promedio máximo'
        })
    )
    
    asistencia_min = forms.FloatField(
        required=False,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'placeholder': 'Asistencia mínima %'
        })
    )
    
    incluir_resueltos = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Incluir anomalías resueltas'
    )

class ActualizacionMasivaForm(forms.Form):
    ACCIONES = [
        ('', 'Seleccionar acción'),
        ('cambiar_estado', 'Cambiar estado'),
        ('derivar_masivo', 'Derivar en masa'),
        ('actualizar_prioridad', 'Actualizar prioridad'),
        ('marcar_falso_positivo', 'Marcar como falso positivo'),
    ]
    
    accion = forms.ChoiceField(
        choices=ACCIONES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    nuevo_estado = forms.ChoiceField(
        choices=[('', 'Seleccionar estado')] + DeteccionAnomalia.ESTADOS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    nueva_prioridad = forms.ChoiceField(
        choices=[('', 'Seleccionar prioridad')] + [(i, f'Prioridad {i}') for i in range(1, 6)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    instancia_apoyo = forms.ModelChoiceField(
        queryset=InstanciaApoyo.objects.filter(activo=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Seleccionar instancia"
    )
    
    motivo_derivacion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Motivo de la derivación masiva...'
        })
    )
    
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones adicionales...'
        })
    )

class ConfiguracionModeloForm(forms.Form):
    """Formulario para configuración avanzada del modelo de detección"""
    
    # Parámetros del Isolation Forest
    n_estimators = forms.IntegerField(
        initial=100,
        min_value=10,
        max_value=500,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text='Número de árboles en el ensemble'
    )
    
    max_samples = forms.CharField(
        initial='auto',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Número de muestras para entrenar cada árbol (auto, entero o float)'
    )
    
    contamination = forms.FloatField(
        initial=0.1,
        min_value=0.01,
        max_value=0.5,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text='Proporción esperada de outliers'
    )
    
    max_features = forms.FloatField(
        initial=1.0,
        min_value=0.1,
        max_value=1.0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        help_text='Número de características para entrenar cada árbol'
    )
    
    bootstrap = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Si usar bootstrap para muestrear datos'
    )
    
    # Configuración de preprocesamiento
    aplicar_pca = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Aplicar reducción de dimensionalidad con PCA'
    )
    
    n_componentes_pca = forms.IntegerField(
        initial=10,
        min_value=2,
        max_value=50,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text='Número de componentes principales a conservar'
    )
    
    normalizar_datos = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Normalizar datos antes del entrenamiento'
    )
    
    # Configuración de características
    incluir_variaciones_temporales = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Incluir variaciones entre semestres'
    )
    
    peso_notas = forms.FloatField(
        initial=1.0,
        min_value=0.1,
        max_value=3.0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        help_text='Peso relativo de las características de notas'
    )
    
    peso_asistencia = forms.FloatField(
        initial=1.0,
        min_value=0.1,
        max_value=3.0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        help_text='Peso relativo de las características de asistencia'
    )
    
    peso_plataforma = forms.FloatField(
        initial=0.8,
        min_value=0.1,
        max_value=3.0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        help_text='Peso relativo de las características de uso de plataforma'
    )

class ValidacionDatosForm(forms.Form):
    """Formulario para configurar validaciones de calidad de datos"""
    
    verificar_notas_rango = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Verificar que las notas estén en rango 1.0-7.0'
    )
    
    verificar_asistencia_rango = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Verificar que la asistencia esté en rango 0-100%'
    )
    
    verificar_registros_duplicados = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Verificar registros duplicados estudiante-asignatura'
    )
    
    minimo_registros_estudiante = forms.IntegerField(
        initial=3,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text='Mínimo de registros requeridos por estudiante para análisis'
    )
    
    permitir_datos_faltantes = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Permitir análisis con datos faltantes (se llenarán con valores medios)'
    )
    
    umbral_datos_faltantes = forms.FloatField(
        initial=0.1,
        min_value=0.0,
        max_value=0.5,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text='Proporción máxima de datos faltantes permitida por estudiante'
    )

class NotificacionForm(forms.Form):
    """Formulario para configurar notificaciones personalizadas"""
    
    destinatarios = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text='Seleccionar usuarios que recibirán las notificaciones'
    )
    
    tipo_notificacion = forms.ChoiceField(
        choices=[
            ('email', 'Correo electrónico'),
            ('sistema', 'Notificación en sistema'),
            ('ambas', 'Ambas'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    frecuencia = forms.ChoiceField(
        choices=[
            ('inmediata', 'Inmediata'),
            ('diaria', 'Resumen diario'),
            ('semanal', 'Resumen semanal'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    incluir_estadisticas = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Incluir estadísticas generales en las notificaciones'
    )

class PerfilUsuarioForm(forms.ModelForm):
    """Formulario para editar perfil de usuario"""
    
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono',
        }

class FeedbackAnomaliaForm(forms.Form):
    """Formulario para feedback sobre la precisión de las detecciones"""
    
    VALORACIONES = [
        (1, 'Muy incorrecta'),
        (2, 'Incorrecta'),
        (3, 'Parcialmente correcta'),
        (4, 'Correcta'),
        (5, 'Muy correcta'),
    ]
    
    valoracion = forms.ChoiceField(
        choices=VALORACIONES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text='¿Qué tan precisa considera esta detección?'
    )
    
    comentarios = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Comentarios adicionales sobre la detección...'
        })
    )
    
    sugerir_mejoras = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Sugerencias para mejorar la detección...'
        })
    )
    