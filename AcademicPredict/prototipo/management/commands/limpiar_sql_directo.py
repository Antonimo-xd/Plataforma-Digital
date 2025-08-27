from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Limpieza rápida usando SQL directo en PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma la ejecución'
        )

    def handle(self, *args, **options):
        if not options['confirmar']:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️ Esto ejecutará SQL directo en PostgreSQL.\n'
                    'Usa --confirmar para continuar.'
                )
            )
            return

        self.stdout.write("🐘 Ejecutando limpieza SQL directa...")

        with connection.cursor() as cursor:
            try:
                # Deshabilitar restricciones temporalmente
                cursor.execute("SET session_replication_role = replica;")
                
                # Lista de tablas en orden de eliminación
                tablas = [
                    'prototipo_alertaautomatica_destinatarios',
                    'prototipo_alertaautomatica',
                    'prototipo_derivacion',
                    'prototipo_deteccionanomalia',
                    'prototipo_ejecucionanalisis',
                    'prototipo_asignaturacritica',
                    'prototipo_registroacademico',
                    'prototipo_criterioanomalia',
                    'prototipo_instanciaapoyo',
                    'prototipo_asignatura',
                    'prototipo_estudiante',
                    'prototipo_carrera',
                ]
                
                for tabla in tablas:
                    try:
                        cursor.execute(f"TRUNCATE TABLE {tabla} RESTART IDENTITY CASCADE;")
                        self.stdout.write(f"✅ Tabla {tabla} limpiada")
                    except Exception as e:
                        self.stdout.write(f"⚠️ {tabla}: {str(e)}")
                
                # Rehabilitar restricciones
                cursor.execute("SET session_replication_role = DEFAULT;")
                
                self.stdout.write(
                    self.style.SUCCESS(
                        "🎉 Limpieza SQL directa completada"
                    )
                )
                
            except Exception as e:
                cursor.execute("SET session_replication_role = DEFAULT;")
                self.stdout.write(
                    self.style.ERROR(f"❌ Error en limpieza SQL: {str(e)}")
                )
                raise