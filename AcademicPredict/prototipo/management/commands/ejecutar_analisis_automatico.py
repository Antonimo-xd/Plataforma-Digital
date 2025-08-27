from django.core.management.base import BaseCommand
from django.utils import timezone
from prototipo.models import CriterioAnomalia, Usuario
from prototipo.utils import ejecutar_deteccion_anomalias
from datetime import timedelta

class Command(BaseCommand):
    help = 'Ejecuta análisis automático de anomalías'

    def add_arguments(self, parser):
        parser.add_argument(
            '--criterio-id',
            type=int,
            help='ID del criterio específico a ejecutar'
        )
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Ejecutar todos los criterios activos'
        )

    def handle(self, *args, **options):
        # Obtener usuario del sistema para las ejecuciones automáticas
        usuario_sistema = Usuario.objects.filter(
            is_superuser=True
        ).first()
        
        if not usuario_sistema:
            self.stdout.write(
                self.style.ERROR('No se encontró un usuario administrador para ejecutar el análisis')
            )
            return

        if options['criterio_id']:
            # Ejecutar criterio específico
            try:
                criterio = CriterioAnomalia.objects.get(
                    id=options['criterio_id'],
                    activo=True
                )
                self.ejecutar_criterio(criterio, usuario_sistema)
            except CriterioAnomalia.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Criterio con ID {options["criterio_id"]} no encontrado o inactivo')
                )
        
        elif options['todos']:
            # Ejecutar todos los criterios activos
            criterios = CriterioAnomalia.objects.filter(activo=True)
            
            if not criterios.exists():
                self.stdout.write(
                    self.style.WARNING('No hay criterios activos para ejecutar')
                )
                return
            
            for criterio in criterios:
                self.ejecutar_criterio(criterio, usuario_sistema)
        
        else:
            # Ejecutar criterios que no se han ejecutado en las últimas 24 horas
            fecha_limite = timezone.now() - timedelta(hours=24)
            
            criterios_pendientes = CriterioAnomalia.objects.filter(
                activo=True
            ).exclude(
                ejecucionanalisis__fecha_ejecucion__gte=fecha_limite
            )
            
            if not criterios_pendientes.exists():
                self.stdout.write(
                    self.style.SUCCESS('Todos los criterios están actualizados')
                )
                return
            
            for criterio in criterios_pendientes:
                self.ejecutar_criterio(criterio, usuario_sistema)

    def ejecutar_criterio(self, criterio, usuario):
        self.stdout.write(f'Ejecutando criterio: {criterio.nombre}...')
        
        resultado = ejecutar_deteccion_anomalias(criterio, usuario)
        
        if resultado['exitoso']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Criterio {criterio.nombre}: {resultado["anomalias_detectadas"]} anomalías detectadas'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f'✗ Error en criterio {criterio.nombre}: {resultado["error"]}'
                )
            )