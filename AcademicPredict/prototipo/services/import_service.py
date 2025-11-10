import pandas as pd
from io import StringIO
from django.db import transaction
from prototipo.models import Estudiante, Asignatura, RegistroAcademico, Carrera
import logging

logger = logging.getLogger(__name__)

CARRERA_ALIASES = {
    'informatica': 'Ingeniería en Informática',
    # Puedes agregar más alias si los descubres:
    # 'comercial': 'Ingeniería Comercial',
    # 'ing. informatica': 'Ingeniería en Informática',
}

class ImportService:
    """
    Servicio centralizado para importación de datos académicos
    
    🎓 APRENDIZAJE: Los servicios encapsulan lógica compleja
    - Reutilizables en vistas, APIs, comandos
    - Fáciles de testear
    - Mantienen las vistas simples
    """
    
    @staticmethod
    def detectar_encoding(archivo):
        """Detecta el encoding del archivo"""
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                contenido = archivo.read()
                archivo.seek(0)
                if isinstance(contenido, bytes):
                    contenido.decode(encoding)
                return encoding
            except (UnicodeDecodeError, AttributeError):
                archivo.seek(0)
                continue
        return 'utf-8'
    
    @staticmethod
    def leer_archivo(archivo):
        """
        Lee archivo CSV o Excel y retorna DataFrame
        
        Returns:
            tuple: (DataFrame, encoding_usado, errores)
        """
        errores = []
        
        try:
            # Detectar tipo de archivo
            if archivo.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(archivo)
                encoding = 'excel'
            else:
                # Detectar encoding para CSV
                encoding = ImportService.detectar_encoding(archivo)
                contenido = archivo.read()
                archivo.seek(0)
                
                if isinstance(contenido, bytes):
                    contenido_str = contenido.decode(encoding)
                else:
                    contenido_str = contenido
            
                df = pd.read_csv(StringIO(contenido_str))
            
            # Limpiar nombres de columnas
            df.columns = df.columns.str.strip()
            
            return df, encoding, errores
            
        except Exception as e:
            errores.append(f'Error leyendo archivo: {str(e)}')
            return None, None, errores
    
    @staticmethod
    def procesar_estudiantes(archivo):
        """
        Procesa archivo de estudiantes
        
        Formato esperado:
        - IdEstudiante (int)
        - Nombre (str)
        - Carrera (str)
        - Ingreso_año (int)
        
        Returns:
            dict: {
                'importados': int,
                'errores': list,
                'advertencias': list
            }
        """
        resultado = {
            'importados': 0,
            'errores': [],
            'advertencias': []
        }
        
        # Leer archivo
        df, encoding, errores = ImportService.leer_archivo(archivo)
        if errores:
            resultado['errores'].extend(errores)
            return resultado
        
        if encoding:
            resultado['advertencias'].append(f'Archivo leído con encoding: {encoding}')
        
        # Validar columnas requeridas
        columnas_requeridas = ['IdEstudiante', 'Nombre', 'Carrera', 'Ingreso_año']
        columnas_faltantes = [
            col for col in columnas_requeridas 
            if col not in df.columns
        ]
        
        if columnas_faltantes:
            resultado['errores'].append(
                f'Columnas faltantes: {", ".join(columnas_faltantes)}'
            )
            return resultado
        
        # Cache de carreras para optimizar
        carreras_cache = {}
        
        # Procesar cada fila
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Validar datos básicos
                    if pd.isna(row['IdEstudiante']) or pd.isna(row['Nombre']):
                        resultado['errores'].append(
                            f'Fila {index + 2}: Datos incompletos'
                        )
                        continue
                    
                    id_estudiante = int(row['IdEstudiante'])
                    nombre = str(row['Nombre']).strip()
                    ingreso_año = int(row['Ingreso_año'])
                    
                    carrera_nombre = str(row['Carrera']).strip()
                    carrera_nombre_normalizado = CARRERA_ALIASES.get(
                        carrera_nombre.lower(), # Clave: 'informatica'
                        carrera_nombre          # Valor por defecto: el mismo que venía
                    )
                    # Validar año de ingreso
                    if ingreso_año < 1900 or ingreso_año > 2030:
                        resultado['errores'].append(
                            f'Fila {index + 2}: Año de ingreso inválido ({ingreso_año})'
                        )
                        continue
                    
                    # Obtener o crear carrera
                    if carrera_nombre_normalizado not in carreras_cache:
                        carrera, created = Carrera.objects.get_or_create(
                            nombre=carrera_nombre_normalizado
                        )
                        carreras_cache[carrera_nombre_normalizado] = carrera
                        if created:
                            resultado['advertencias'].append(
                                f'Carrera creada: {carrera_nombre_normalizado}'
                            )
                    
                    carrera = carreras_cache[carrera_nombre_normalizado]
                    
                    # Crear o actualizar estudiante
                    estudiante, created = Estudiante.objects.update_or_create(
                        id_estudiante=id_estudiante,
                        defaults={
                            'nombre': nombre,
                            'carrera': carrera,
                            'ingreso_año': ingreso_año
                        }
                    )
                    
                    resultado['importados'] += 1
                    
                    if not created:
                        resultado['advertencias'].append(
                            f'Estudiante {id_estudiante} actualizado'
                        )
                    
                except ValueError as e:
                    resultado['errores'].append(
                        f'Fila {index + 2}: Datos inválidos - {str(e)}'
                    )
                except Exception as e:
                    resultado['errores'].append(
                        f'Fila {index + 2}: Error inesperado - {str(e)}'
                    )
                    logger.error(f"Error procesando fila {index}: {str(e)}")
        
        return resultado
    
    @staticmethod
    def procesar_asignaturas(archivo):
        """
        Procesa archivo de asignaturas
        
        Formato esperado:
        - Id_Asignatura (int)
        - NombreAsignatura (str)
        - Semestre (int: 1-8)
        """
        resultado = {
            'importados': 0,
            'errores': [],
            'advertencias': []
        }
        
        # Leer archivo
        df, encoding, errores = ImportService.leer_archivo(archivo)
        if errores:
            resultado['errores'].extend(errores)
            return resultado
        
        if encoding:
            resultado['advertencias'].append(f'Encoding: {encoding}')
        
        # Validar columnas
        columnas_requeridas = ['Id_Asignatura', 'NombreAsignatura', 'Semestre']

        columnas_faltantes = [
            col for col in columnas_requeridas 
            if col not in df.columns
        ]
        
        if columnas_faltantes:
            resultado['errores'].append(
                f'Columnas faltantes: {", ".join(columnas_faltantes)}'
            )
            return resultado
        
        # Procesar
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    if pd.isna(row['Id_Asignatura']) or pd.isna(row['NombreAsignatura']):
                        resultado['errores'].append(
                            f'Fila {index + 2}: Datos incompletos'
                        )
                        continue
                    
                    id_asignatura = int(row['Id_Asignatura'])
                    nombre = str(row['NombreAsignatura']).strip()
                    semestre = int(row['Semestre'])
                    
                    # Validar semestre
                    if semestre < 1 or semestre > 12:
                        resultado['errores'].append(
                            f'Fila {index + 2}: Semestre inválido ({semestre})'
                        )
                        continue
                    
                    # Crear o actualizar
                    asignatura, created = Asignatura.objects.update_or_create(
                        id_asignatura=id_asignatura,
                        defaults={
                            'nombre': nombre,
                            'semestre': semestre
                        }
                    )
                    
                    resultado['importados'] += 1
                    
                    if not created:
                        resultado['advertencias'].append(
                            f'Asignatura {id_asignatura} actualizada'
                        )
                    
                except Exception as e:
                    resultado['errores'].append(
                        f'Fila {index + 2}: {str(e)}'
                    )
        
        return resultado
    
    @staticmethod
    def procesar_registros(archivo):
        """
        Procesa archivo de registros académicos
        
        Formato esperado:
        - Id_Registro (int)
        - Id_Estudiante (int)
        - Id_asignatura (int)
        - Nota1, Nota2, Nota3, Nota4 (float: 1.0-7.0)
        - porcentaje_asistencia (float: 0-100)
        - porcentaje_uso_plataforma (float: 0-100)
        - promedio_notas (float: 1.0-7.0)
        """
        resultado = {
            'importados': 0,
            'errores': [],
            'advertencias': []
        }
        
        # Leer archivo
        df, encoding, errores = ImportService.leer_archivo(archivo)
        if errores:
            resultado['errores'].extend(errores)
            return resultado
        
        if encoding:
            resultado['advertencias'].append(f'Archivo leído con encoding: {encoding}')

        # Validar columnas
        columnas_requeridas = [
            'Id_Registro','Id_Estudiante', 'Id_asignatura',
            'Nota1', 'Nota2', 'Nota3', 'Nota4',
            '% de Asistencia',     
            '% de Uso de plataforma', 
            'PromedioNotas'
        ]
        
        columnas_faltantes = [
            col for col in columnas_requeridas 
            if col not in df.columns
        ]
        
        if columnas_faltantes:
            resultado['errores'].append(
                f'Columnas faltantes: {", ".join(columnas_faltantes)}'
            )
            return resultado
        
        # Cache para optimizar consultas
        estudiantes_cache = {}
        asignaturas_cache = {}
        
        # Procesar
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    if pd.isna(row['Id_Registro']) or pd.isna(row['Id_Estudiante']) or pd.isna(row['Id_asignatura']):
                        resultado['errores'].append(
                            f'Fila {index + 2}: Datos incompletos'
                        )
                        continue
                    
                    id_registro = int(row['Id_Registro'])
                    id_estudiante = int(row['Id_Estudiante'])
                    id_asignatura = int(row['Id_asignatura'])
                    
                    # Buscar estudiante (con cache)
                    if id_estudiante not in estudiantes_cache:
                        try:
                            estudiantes_cache[id_estudiante] = \
                                Estudiante.objects.get(id_estudiante=id_estudiante)
                        except Estudiante.DoesNotExist:
                            resultado['errores'].append(
                                f'Fila {index + 2}: Estudiante {id_estudiante} no existe'
                            )
                            continue
                    
                    estudiante = estudiantes_cache[id_estudiante]
                    
                    # Buscar asignatura (con cache)
                    if id_asignatura not in asignaturas_cache:
                        try:
                            asignaturas_cache[id_asignatura] = \
                                Asignatura.objects.get(id_asignatura=id_asignatura)
                        except Asignatura.DoesNotExist:
                            resultado['errores'].append(
                                f'Fila {index + 2}: Asignatura {id_asignatura} no existe'
                            )
                            continue
                    
                    asignatura = asignaturas_cache[id_asignatura]
                    
                    # Validar y obtener notas
                    notas = []
                    for i in range(1, 5):
                        nota = row.get(f'Nota{i}')
                        if pd.isna(nota):
                            nota = 1.0  # Valor por defecto
                        else:
                            nota = float(nota)
                            if nota < 1.0 or nota > 7.0:
                                resultado['advertencias'].append(
                                    f'Fila {index + 2}: Nota{i} fuera de rango ({nota}), ajustada'
                                )
                                nota = max(1.0, min(7.0, nota))
                        notas.append(nota)
                    
                    # Validar asistencia y uso de plataforma
                    asistencia = float(row['% de Asistencia'])
                    uso_plataforma = float(row['% de Uso de plataforma'])
                    
                    if not (0 <= asistencia <= 100):
                        resultado['advertencias'].append(
                            f'Fila {index + 2}: % de Asistencia fuera de rango ({asistencia}%)'
                        )
                        asistencia = max(0, min(100, asistencia))
                    
                    if not (0 <= uso_plataforma <= 100):
                        resultado['advertencias'].append(
                            f'Fila {index + 2}: % de Uso de plataforma fuera de rango ({uso_plataforma}%)'
                        )
                        uso_plataforma = max(0, min(100, uso_plataforma))
                    
                    # Calcular promedio
                    if pd.isna(row['PromedioNotas']):
                        promedio_leido = 1.0 # Valor por defecto si está vacío
                        resultado['advertencias'].append(
                            f'Fila {index + 2}: PromedioNotas vacío, se usó 1.0'
                        )
                    else:
                        promedio_leido = float(row['PromedioNotas'])
                        if promedio_leido < 1.0 or promedio_leido > 7.0:
                            resultado['advertencias'].append(
                                f'Fila {index + 2}: PromedioNotas fuera de rango ({promedio_leido}), ajustado'
                            )
                            promedio_leido = max(1.0, min(7.0, promedio_leido))

                    # Crear o actualizar registro
                    registro, created = RegistroAcademico.objects.update_or_create(
                        estudiante=estudiante,
                        asignatura=asignatura,
                        defaults={
                            'nota1': notas[0],
                            'nota2': notas[1],
                            'nota3': notas[2],
                            'nota4': notas[3],
                            'promedio_notas': promedio_leido,
                            'porcentaje_asistencia': asistencia,
                            'porcentaje_uso_plataforma': uso_plataforma
                        }
                    )
                    resultado['importados'] += 1

                    if not created:
                        resultado['advertencias'].append(
                            f'Registro {id_registro} actualizado'
                        )
                    
                except Exception as e:
                    resultado['errores'].append(
                        f'Fila {index + 2}: {str(e)}'
                    )
                    logger.error(f"Error en fila {index}: {str(e)}")
        
        return resultado
    
    @staticmethod
    def validar_integridad_datos():
        """
        Valida la integridad de los datos después de importar
        
        Returns:
            dict: Reporte de inconsistencias encontradas
        """
        problemas = []
        
        # Verificar estudiantes sin registros
        from django.db.models import Count
        estudiantes_sin_registros = Estudiante.objects.annotate(
            num_registros=Count('registroacademico')
        ).filter(num_registros=0)
        
        if estudiantes_sin_registros.exists():
            problemas.append(
                f'{estudiantes_sin_registros.count()} estudiantes sin registros académicos'
            )
        
        # Verificar registros con promedios inconsistentes
        registros = RegistroAcademico.objects.all()
        for registro in registros:
            promedio_calculado = (
                registro.nota1 + registro.nota2 + 
                registro.nota3 + registro.nota4
            ) / 4
            
            diferencia = abs(promedio_calculado - registro.promedio)
            if diferencia > 0.1:  # Tolerancia de 0.1
                problemas.append(
                    f'Registro {registro.id}: Promedio inconsistente '
                    f'(esperado: {promedio_calculado:.2f}, guardado: {registro.promedio:.2f})'
                )
        
        # Verificar carreras sin coordinador
        carreras_sin_coordinador = Carrera.objects.filter(coordinador__isnull=True)
        if carreras_sin_coordinador.exists():
            problemas.append(
                f'{carreras_sin_coordinador.count()} carreras sin coordinador asignado'
            )
        
        return {
            'valido': len(problemas) == 0,
            'problemas': problemas,
            'total_problemas': len(problemas)
        }