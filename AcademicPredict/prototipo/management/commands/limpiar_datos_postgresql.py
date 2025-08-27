from django.core.management.base import BaseCommand
from django.db import transaction
from prototipo.models import *

class Command(BaseCommand):
    help = 'Limpia todos los datos del sistema CPA en PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma que quieres eliminar todos los datos'
        )
        parser.add_argument(
            '--mantener-usuarios',
            action='store_true',
            help='Mantiene los usuarios del sistema'
        )

    def handle(self, *args, **options):
        if not options['confirmar']:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️ Este comando eliminará TODOS los datos de PostgreSQL.\n'
                    'Usa --confirmar para ejecutar.\n'
                    'Usa --mantener-usuarios para conservar usuarios.'
                )
            )
            return

        self.stdout.write("🐘 Iniciando limpieza de PostgreSQL en Supabase...")

        try:
            with transaction.atomic():
                # Eliminar en orden para evitar problemas de foreign keys
                
                # 1. Alertas automáticas (si existen)
                try:
                    count = AlertaAutomatica.objects.count()
                    if count > 0:
                        # Primero limpiar relaciones many-to-many
                        for alerta in AlertaAutomatica.objects.all():
                            alerta.destinatarios.clear()
                        AlertaAutomatica.objects.all().delete()
                        self.stdout.write(f"✅ Eliminadas {count} alertas automáticas")
                except Exception as e:
                    self.stdout.write(f"ℹ️ Alertas: {str(e)}")

                # 2. Derivaciones
                count = Derivacion.objects.count()
                Derivacion.objects.all().delete()
                self.stdout.write(f"✅ Eliminadas {count} derivaciones")

                # 3. Detecciones de anomalías
                count = DeteccionAnomalia.objects.count()
                DeteccionAnomalia.objects.all().delete()
                self.stdout.write(f"✅ Eliminadas {count} detecciones de anomalías")

                # 4. Ejecuciones de análisis
                count = EjecucionAnalisis.objects.count()
                EjecucionAnalisis.objects.all().delete()
                self.stdout.write(f"✅ Eliminadas {count} ejecuciones de análisis")

                # 5. Asignaturas críticas (si existen)
                try:
                    count = AsignaturaCritica.objects.count()
                    AsignaturaCritica.objects.all().delete()
                    self.stdout.write(f"✅ Eliminadas {count} asignaturas críticas")
                except Exception as e:
                    self.stdout.write(f"ℹ️ Asignaturas críticas: {str(e)}")

                # 6. Registros académicos
                count = RegistroAcademico.objects.count()
                RegistroAcademico.objects.all().delete()
                self.stdout.write(f"✅ Eliminados {count} registros académicos")

                # 7. Criterios de anomalía
                count = CriterioAnomalia.objects.count()
                CriterioAnomalia.objects.all().delete()
                self.stdout.write(f"✅ Eliminados {count} criterios de anomalía")

                # 8. Instancias de apoyo
                count = InstanciaApoyo.objects.count()
                InstanciaApoyo.objects.all().delete()
                self.stdout.write(f"✅ Eliminadas {count} instancias de apoyo")

                # 9. Asignaturas
                count = Asignatura.objects.count()
                Asignatura.objects.all().delete()
                self.stdout.write(f"✅ Eliminadas {count} asignaturas")

                # 10. Estudiantes
                count = Estudiante.objects.count()
                Estudiante.objects.all().delete()
                self.stdout.write(f"✅ Eliminados {count} estudiantes")

                # 11. Carreras
                count = Carrera.objects.count()
                Carrera.objects.all().delete()
                self.stdout.write(f"✅ Eliminadas {count} carreras")

                # 12. Usuarios (opcional)
                if not options['mantener_usuarios']:
                    # Eliminar usuarios no superusuarios
                    count = Usuario.objects.filter(is_superuser=False).count()
                    Usuario.objects.filter(is_superuser=False).delete()
                    self.stdout.write(f"✅ Eliminados {count} usuarios (mantenidos superusuarios)")
                else:
                    self.stdout.write("ℹ️ Usuarios mantenidos")

                self.stdout.write(
                    self.style.SUCCESS(
                        "🎉 Limpieza de PostgreSQL completada exitosamente."
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Error durante la limpieza: {str(e)}"
                )
            )
            raise