from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import pandas as pd
import time
import os
from io import StringIO
from prototipo.models import Estudiante, Asignatura, RegistroAcademico, Carrera


class Command(BaseCommand):
    help = '🚀 Importa TODOS los datos desde archivos CSV/Excel de forma OPTIMIZADA'

    def add_arguments(self, parser):
        parser.add_argument('--estudiantes', type=str, help='Ruta al archivo de estudiantes')
        parser.add_argument('--asignaturas', type=str, help='Ruta al archivo de asignaturas')
        parser.add_argument('--registros', type=str, help='Ruta al archivo de registros')
        parser.add_argument('--limpiar', action='store_true', help='Limpiar datos existentes antes de importar')
        parser.add_argument('--directorio', type=str, help='Directorio con archivos CSV (busca automáticamente)')

    def handle(self, *args, **options):
        """🎯 Función principal del comando"""
        inicio_total = time.time()
        
        self.stdout.write(self.style.SUCCESS('🚀 INICIANDO IMPORTACIÓN MASIVA OPTIMIZADA'))
        self.stdout.write('=' * 60)
        
        try:
            # 🧹 Limpiar datos si se solicita
            if options['limpiar']:
                self.limpiar_datos()
            
            # 📁 Determinar archivos a procesar
            archivos = self.determinar_archivos(options)
            
            if not any(archivos.values()):
                self.stdout.write(self.style.ERROR('❌ No se encontraron archivos para procesar'))
                return
            
            # 📊 Mostrar estado inicial
            self.mostrar_estado_bd("ANTES")
            
            # 🎯 Procesar archivos en orden correcto
            resultados = {}
            
            if archivos['estudiantes']:
                self.stdout.write('\n👥 PROCESANDO ESTUDIANTES...')
                resultados['estudiantes'] = self.procesar_estudiantes_optimizado(archivos['estudiantes'])
            
            if archivos['asignaturas']:
                self.stdout.write('\n📚 PROCESANDO ASIGNATURAS...')
                resultados['asignaturas'] = self.procesar_asignaturas_optimizado(archivos['asignaturas'])
            
            if archivos['registros']:
                self.stdout.write('\n📊 PROCESANDO REGISTROS...')
                resultados['registros'] = self.procesar_registros_optimizado(archivos['registros'])
            
            # 📈 Mostrar resultados finales
            self.mostrar_resultados_finales(resultados, inicio_total)
            self.mostrar_estado_bd("DESPUÉS")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error general: {str(e)}'))
            import traceback
            traceback.print_exc()

    def determinar_archivos(self, options):
        """📁 Determina qué archivos procesar"""
        archivos = {'estudiantes': None, 'asignaturas': None, 'registros': None}
        
        # Opción 1: Archivos especificados individualmente
        if options['estudiantes']:
            archivos['estudiantes'] = options['estudiantes']
        if options['asignaturas']:
            archivos['asignaturas'] = options['asignaturas']
        if options['registros']:
            archivos['registros'] = options['registros']
        
        # Opción 2: Buscar en directorio automáticamente
        elif options['directorio']:
            directorio = options['directorio']
            
            # Buscar archivos comunes
            posibles_nombres = {
                'estudiantes': ['estudiantes.csv', 'estudiantes.xlsx', 'students.csv'],
                'asignaturas': ['asignaturas.csv', 'asignaturas.xlsx', 'subjects.csv'],
                'registros': ['registros.csv', 'registros.xlsx', 'records.csv']
            }
            
            for tipo, nombres in posibles_nombres.items():
                for nombre in nombres:
                    ruta = os.path.join(directorio, nombre)
                    if os.path.exists(ruta):
                        archivos[tipo] = ruta
                        self.stdout.write(f'✅ Encontrado: {ruta}')
                        break
        
        # Opción 3: Buscar en directorio actual
        else:
            directorio_actual = os.getcwd()
            nombres_buscar = ['estudiantes.csv', 'asignaturas.csv', 'registros.csv']
            
            for nombre in nombres_buscar:
                ruta = os.path.join(directorio_actual, nombre)
                if os.path.exists(ruta):
                    tipo = nombre.split('.')[0]
                    archivos[tipo] = ruta
                    self.stdout.write(f'✅ Encontrado en directorio actual: {ruta}')
        
        return archivos

    def limpiar_datos(self):
        """🧹 Limpia todos los datos existentes"""
        self.stdout.write('🧹 LIMPIANDO DATOS EXISTENTES...')
        
        with transaction.atomic():
            registros_count = RegistroAcademico.objects.count()
            estudiantes_count = Estudiante.objects.count()
            asignaturas_count = Asignatura.objects.count()
            carreras_count = Carrera.objects.count()
            
            RegistroAcademico.objects.all().delete()
            Estudiante.objects.all().delete()
            Asignatura.objects.all().delete()
            Carrera.objects.all().delete()
            
            self.stdout.write(f'   🗑️  Eliminados: {registros_count} registros, {estudiantes_count} estudiantes')
            self.stdout.write(f'   🗑️  Eliminados: {asignaturas_count} asignaturas, {carreras_count} carreras')

    def mostrar_estado_bd(self, momento):
        """📊 Muestra estado actual de la BD"""
        estudiantes = Estudiante.objects.count()
        asignaturas = Asignatura.objects.count()
        registros = RegistroAcademico.objects.count()
        carreras = Carrera.objects.count()
        
        self.stdout.write(f'\n📊 ESTADO DE LA BD {momento}:')
        self.stdout.write(f'   🎓 Carreras: {carreras}')
        self.stdout.write(f'   👥 Estudiantes: {estudiantes}')
        self.stdout.write(f'   📚 Asignaturas: {asignaturas}')
        self.stdout.write(f'   📊 Registros: {registros}')

    def leer_archivo(self, ruta_archivo):
        """📖 Lee archivo CSV o Excel con manejo de encodings"""
        self.stdout.write(f'📖 Leyendo: {ruta_archivo}')
        
        if ruta_archivo.endswith(('.xlsx', '.xls')):
            return pd.read_excel(ruta_archivo)
        else:
            # Intentar diferentes encodings
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    df = pd.read_csv(ruta_archivo, encoding=encoding)
                    self.stdout.write(f'   ✅ Leído con encoding: {encoding}')
                    return df
                except UnicodeDecodeError:
                    continue
            raise Exception(f'No se pudo leer {ruta_archivo} con ningún encoding')

      def procesar_registros_optimizado(self, ruta_archivo):
      """📊 Procesa registros con SÚPER optimizaciones - VERSIÓN CORREGIDA"""
      inicio = time.time()
      resultado = {'importados': 0, 'errores': [], 'advertencias': []}
      
      try:
          df = self.leer_archivo(ruta_archivo)
          df.columns = df.columns.str.strip()
          
          # 🚀 OPTIMIZACIÓN CRÍTICA: Pre-cargar TODO
          self.stdout.write('🔄 Pre-cargando datos relacionados...')
          estudiantes_dict = {est.id_estudiante: est for est in Estudiante.objects.all()}
          asignaturas_dict = {asig.id_asignatura: asig for asig in Asignatura.objects.all()}
          registros_existentes = set(RegistroAcademico.objects.values_list('estudiante_id', 'asignatura_id'))
          
          self.stdout.write(f'   📚 {len(estudiantes_dict)} estudiantes cargados')
          self.stdout.write(f'   📖 {len(asignaturas_dict)} asignaturas cargadas')
          self.stdout.write(f'   📊 {len(registros_existentes)} registros existentes')
          
          registros_nuevos = []
          
          with transaction.atomic():
              for index, row in df.iterrows():
                  try:
                      id_estudiante = int(row['Id_Estudiante'])
                      id_asignatura = int(row['Id_asignatura'])
                      
                      # Búsqueda O(1)
                      estudiante = estudiantes_dict.get(id_estudiante)
                      asignatura = asignaturas_dict.get(id_asignatura)
                      
                      if not estudiante:
                          resultado['errores'].append(f'Estudiante {id_estudiante} no existe')
                          continue
                      
                      if not asignatura:
                          resultado['errores'].append(f'Asignatura {id_asignatura} no existe')
                          continue
                      
                      # Verificar si ya existe
                      if (estudiante.pk, asignatura.pk) in registros_existentes:
                          continue
                      
                      # Procesar notas
                      notas = []
                      for i in range(1, 5):
                          nota = float(row[f'Nota{i}']) if not pd.isna(row[f'Nota{i}']) else 1.0
                          notas.append(max(1.0, min(7.0, nota)))
                      
                      # 🔧 SOLUCIÓN: Calcular promedio manualmente
                      promedio_calculado = sum(notas) / len(notas)
                      
                      asistencia = max(0, min(100, float(row['% de Asistencia'])))
                      uso_plataforma = max(0, min(100, float(row['% de Uso de plataforma'])))
                      
                      # ✅ CREAR OBJETO CON PROMEDIO CALCULADO
                      registro = RegistroAcademico(
                          estudiante=estudiante,
                          asignatura=asignatura,
                          nota1=notas[0],
                          nota2=notas[1],
                          nota3=notas[2],
                          nota4=notas[3],
                          promedio_notas=promedio_calculado,  # ← AGREGADO MANUALMENTE
                          porcentaje_asistencia=asistencia,
                          porcentaje_uso_plataforma=uso_plataforma
                      )
                      
                      registros_nuevos.append(registro)
                      
                  except Exception as e:
                      resultado['errores'].append(f'Error en fila {index + 2}: {str(e)}')
              
              # 🚀 BULK CREATE en lotes
              if registros_nuevos:
                  BATCH_SIZE = 1000
                  total_creados = 0
                  
                  for i in range(0, len(registros_nuevos), BATCH_SIZE):
                      lote = registros_nuevos[i:i + BATCH_SIZE]
                      RegistroAcademico.objects.bulk_create(lote, ignore_conflicts=True)
                      total_creados += len(lote)
                      self.stdout.write(f'   📦 Lote {i//BATCH_SIZE + 1}: {len(lote)} registros')
                  
                  resultado['importados'] = total_creados
              
              tiempo = time.time() - inicio
              rendimiento = resultado['importados'] / tiempo if tiempo > 0 else 0
              self.stdout.write(f'✅ {resultado["importados"]} registros procesados en {tiempo:.2f}s')
              self.stdout.write(f'🚀 Rendimiento: {rendimiento:.1f} registros/segundo')
              
      except Exception as e:
          resultado['errores'].append(f'Error general: {str(e)}')
      
      return resultado

    def procesar_asignaturas_optimizado(self, ruta_archivo):
        """📚 Procesa asignaturas con optimizaciones"""
        inicio = time.time()
        resultado = {'importados': 0, 'errores': [], 'advertencias': []}
        
        try:
            df = self.leer_archivo(ruta_archivo)
            df.columns = df.columns.str.strip()
            
            # Validar columnas
            columnas_requeridas = ['Id_Asignatura', 'NombreAsignatura', 'Semestre']
            if not all(col in df.columns for col in columnas_requeridas):
                raise Exception(f'Columnas faltantes. Requeridas: {columnas_requeridas}')
            
            asignaturas_existentes = set(Asignatura.objects.values_list('id_asignatura', flat=True))
            asignaturas_nuevas = []
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        id_asignatura = int(row['Id_Asignatura'])
                        nombre = str(row['NombreAsignatura']).strip()
                        semestre = int(row['Semestre'])
                        
                        if semestre < 1 or semestre > 8:
                            resultado['errores'].append(f'Semestre inválido en fila {index + 2}: {semestre}')
                            continue
                        
                        if id_asignatura not in asignaturas_existentes:
                            asignaturas_nuevas.append(Asignatura(
                                id_asignatura=id_asignatura,
                                nombre=nombre,
                                semestre=semestre
                            ))
                        
                    except Exception as e:
                        resultado['errores'].append(f'Error en fila {index + 2}: {str(e)}')
                
                if asignaturas_nuevas:
                    Asignatura.objects.bulk_create(asignaturas_nuevas, ignore_conflicts=True)
                    resultado['importados'] = len(asignaturas_nuevas)
                
                tiempo = time.time() - inicio
                self.stdout.write(f'✅ {resultado["importados"]} asignaturas procesadas en {tiempo:.2f}s')
                
        except Exception as e:
            resultado['errores'].append(f'Error general: {str(e)}')
        
        return resultado

    def procesar_registros_optimizado(self, ruta_archivo):
        """📊 Procesa registros con SÚPER optimizaciones"""
        inicio = time.time()
        resultado = {'importados': 0, 'errores': [], 'advertencias': []}
        
        try:
            df = self.leer_archivo(ruta_archivo)
            df.columns = df.columns.str.strip()
            
            # 🚀 OPTIMIZACIÓN CRÍTICA: Pre-cargar TODO
            self.stdout.write('🔄 Pre-cargando datos relacionados...')
            estudiantes_dict = {est.id_estudiante: est for est in Estudiante.objects.all()}
            asignaturas_dict = {asig.id_asignatura: asig for asig in Asignatura.objects.all()}
            registros_existentes = set(RegistroAcademico.objects.values_list('estudiante_id', 'asignatura_id'))
            
            self.stdout.write(f'   📚 {len(estudiantes_dict)} estudiantes cargados')
            self.stdout.write(f'   📖 {len(asignaturas_dict)} asignaturas cargadas')
            self.stdout.write(f'   📊 {len(registros_existentes)} registros existentes')
            
            registros_nuevos = []
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        id_estudiante = int(row['Id_Estudiante'])
                        id_asignatura = int(row['Id_asignatura'])
                        
                        # Búsqueda O(1)
                        estudiante = estudiantes_dict.get(id_estudiante)
                        asignatura = asignaturas_dict.get(id_asignatura)
                        
                        if not estudiante:
                            resultado['errores'].append(f'Estudiante {id_estudiante} no existe')
                            continue
                        
                        if not asignatura:
                            resultado['errores'].append(f'Asignatura {id_asignatura} no existe')
                            continue
                        
                        # Verificar si ya existe
                        if (estudiante.pk, asignatura.pk) in registros_existentes:
                            continue
                        
                        # Procesar notas
                        notas = []
                        for i in range(1, 5):
                            nota = float(row[f'Nota{i}']) if not pd.isna(row[f'Nota{i}']) else 1.0
                            notas.append(max(1.0, min(7.0, nota)))
                        
                        asistencia = max(0, min(100, float(row['% de Asistencia'])))
                        uso_plataforma = max(0, min(100, float(row['% de Uso de plataforma'])))
                        
                        registros_nuevos.append(RegistroAcademico(
                            estudiante=estudiante,
                            asignatura=asignatura,
                            nota1=notas[0],
                            nota2=notas[1],
                            nota3=notas[2],
                            nota4=notas[3],
                            porcentaje_asistencia=asistencia,
                            porcentaje_uso_plataforma=uso_plataforma
                        ))
                        
                    except Exception as e:
                        resultado['errores'].append(f'Error en fila {index + 2}: {str(e)}')
                
                # 🚀 BULK CREATE en lotes
                if registros_nuevos:
                    BATCH_SIZE = 1000
                    total_creados = 0
                    
                    for i in range(0, len(registros_nuevos), BATCH_SIZE):
                        lote = registros_nuevos[i:i + BATCH_SIZE]
                        RegistroAcademico.objects.bulk_create(lote, ignore_conflicts=True)
                        total_creados += len(lote)
                        self.stdout.write(f'   📦 Lote {i//BATCH_SIZE + 1}: {len(lote)} registros')
                    
                    resultado['importados'] = total_creados
                
                tiempo = time.time() - inicio
                rendimiento = resultado['importados'] / tiempo if tiempo > 0 else 0
                self.stdout.write(f'✅ {resultado["importados"]} registros procesados en {tiempo:.2f}s')
                self.stdout.write(f'🚀 Rendimiento: {rendimiento:.1f} registros/segundo')
                
        except Exception as e:
            resultado['errores'].append(f'Error general: {str(e)}')
        
        return resultado

    def mostrar_resultados_finales(self, resultados, inicio_total):
        """📈 Muestra resumen final de la importación"""
        tiempo_total = time.time() - inicio_total
        total_importados = sum(r.get('importados', 0) for r in resultados.values())
        total_errores = sum(len(r.get('errores', [])) for r in resultados.values())
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('📈 RESUMEN FINAL DE IMPORTACIÓN')
        self.stdout.write('=' * 60)
        
        for tipo, resultado in resultados.items():
            if resultado:
                self.stdout.write(f'📊 {tipo.upper()}:')
                self.stdout.write(f'   ✅ Importados: {resultado["importados"]}')
                self.stdout.write(f'   ❌ Errores: {len(resultado["errores"])}')
                if resultado["errores"]:
                    for error in resultado["errores"][:3]:  # Mostrar solo primeros 3
                        self.stdout.write(f'      • {error}')
                    if len(resultado["errores"]) > 3:
                        self.stdout.write(f'      ... y {len(resultado["errores"]) - 3} errores más')
        
        self.stdout.write(f'\n🎯 TOTAL GENERAL:')
        self.stdout.write(f'   ✅ {total_importados} registros importados')
        self.stdout.write(f'   ❌ {total_errores} errores encontrados')
        self.stdout.write(f'   ⏱️  Tiempo total: {tiempo_total:.2f} segundos')
        self.stdout.write(f'   🚀 Rendimiento: {total_importados/tiempo_total:.1f} registros/segundo')
        
        if total_errores == 0:
            self.stdout.write(self.style.SUCCESS('\n🎉 ¡IMPORTACIÓN COMPLETADA EXITOSAMENTE!'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Importación completada con {total_errores} errores'))