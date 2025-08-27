from django.core.management.base import BaseCommand
from django.db import transaction
import pandas as pd
from prototipo.models import Estudiante, Asignatura, RegistroAcademico, Carrera
import os

class Command(BaseCommand):
    help = 'Importa datos desde archivos CSV a la base de datos'

    def add_arguments(self, parser):
        parser.add_argument('--estudiantes', type=str, help='Ruta al archivo CSV de estudiantes')
        parser.add_argument('--asignaturas', type=str, help='Ruta al archivo CSV de asignaturas')
        parser.add_argument('--registros', type=str, help='Ruta al archivo CSV de registros académicos')

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                if options['estudiantes']:
                    self.importar_estudiantes(options['estudiantes'])
                
                if options['asignaturas']:
                    self.importar_asignaturas(options['asignaturas'])
                
                if options['registros']:
                    self.importar_registros(options['registros'])
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error durante la importación: {str(e)}')
            )

    def importar_estudiantes(self, archivo):
        self.stdout.write(f'Importando estudiantes desde {archivo}...')
        
        if not os.path.exists(archivo):
            raise FileNotFoundError(f'Archivo no encontrado: {archivo}')
        
        df = pd.read_csv(archivo)
        importados = 0
        
        for _, row in df.iterrows():
            carrera, created = Carrera.objects.get_or_create(
                nombre=row['Carrera'],
                defaults={'codigo': row['Carrera'][:10]}
            )
            
            estudiante, created = Estudiante.objects.get_or_create(
                id_estudiante=row['IdEstudiante'],
                defaults={
                    'nombre': row['Nombre'],
                    'carrera': carrera,
                    'ingreso_año': row['Ingreso_año']
                }
            )
            
            if created:
                importados += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Importados {importados} estudiantes')
        )

    def importar_asignaturas(self, archivo):
        self.stdout.write(f'Importando asignaturas desde {archivo}...')
        
        df = pd.read_csv(archivo)
        importados = 0
        
        # Obtener la primera carrera disponible o crear una por defecto
        carrera = Carrera.objects.first()
        if not carrera:
            carrera = Carrera.objects.create(nombre='Informática', codigo='INFO')
        
        for _, row in df.iterrows():
            asignatura, created = Asignatura.objects.get_or_create(
                id_asignatura=row['Id_Asignatura'],
                defaults={
                    'nombre': row['NombreAsignatura'],
                    'semestre': row['Semestre'],
                    'carrera': carrera
                }
            )
            
            if created:
                importados += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Importadas {importados} asignaturas')
        )

    def importar_registros(self, archivo):
        self.stdout.write(f'Importando registros académicos desde {archivo}...')
        
        df = pd.read_csv(archivo)
        importados = 0
        errores = 0
        
        for _, row in df.iterrows():
            try:
                estudiante = Estudiante.objects.get(id_estudiante=row['Id_Estudiante'])
                asignatura = Asignatura.objects.get(id_asignatura=row['Id_asignatura'])
                
                registro, created = RegistroAcademico.objects.get_or_create(
                    estudiante=estudiante,
                    asignatura=asignatura,
                    defaults={
                        'nota1': row['Nota1'],
                        'nota2': row['Nota2'],
                        'nota3': row['Nota3'],
                        'nota4': row['Nota4'],
                        'porcentaje_asistencia': row['% de Asistencia'],
                        'porcentaje_uso_plataforma': row['% de Uso de plataforma']
                    }
                )
                
                if created:
                    importados += 1
                    
            except (Estudiante.DoesNotExist, Asignatura.DoesNotExist) as e:
                errores += 1
                self.stdout.write(
                    self.style.WARNING(f'Error en fila: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Importados {importados} registros académicos')
        )
        if errores > 0:
            self.stdout.write(
                self.style.WARNING(f'{errores} registros no pudieron ser importados')
            )