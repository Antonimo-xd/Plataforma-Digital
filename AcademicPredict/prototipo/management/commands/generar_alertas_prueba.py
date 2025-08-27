from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from prototipo.models import *

class Command(BaseCommand):
    help = 'Genera alertas de prueba para verificar el sistema'

    def handle(self, *args, **options):
        self.stdout.write("🔔 Generando alertas de prueba...")
        
        # 1. Crear anomalías críticas
        estudiantes = Estudiante.objects.filter(activo=True)[:3]
        criterio = CriterioAnomalia.objects.filter(activo=True).first()
        
        if not criterio:
            self.stdout.write("❌ No hay criterios activos")
            return
        
        for estudiante in estudiantes:
            anomalia, created = DeteccionAnomalia.objects.get_or_create(
                estudiante=estudiante,
                criterio_usado=criterio,
                defaults={
                    'tipo_anomalia': 'bajo_rendimiento',
                    'score_anomalia': 85.5,
                    'confianza': 0.9,
                    'promedio_general': 3.2,
                    'asistencia_promedio': 45.0,
                    'uso_plataforma_promedio': 30.0,
                    'variacion_notas': 2.1,
                    'prioridad': 5,  # Crítica
                    'estado': 'detectado'
                }
            )
            
            if created:
                self.stdout.write(f"✅ Anomalía crítica creada: {estudiante.nombre}")
        
        # 2. Crear derivaciones pendientes
        anomalias = DeteccionAnomalia.objects.filter(prioridad__gte=4)[:2]
        instancia = InstanciaApoyo.objects.first()
        
        if instancia:
            for anomalia in anomalias:
                derivacion, created = Derivacion.objects.get_or_create(
                    deteccion_anomalia=anomalia,
                    instancia_apoyo=instancia,
                    defaults={
                        'motivo': 'Derivación de prueba para verificar alertas',
                        'estado': 'pendiente',
                        'derivado_por': Usuario.objects.filter(is_superuser=True).first()
                    }
                )
                
                if created:
                    self.stdout.write(f"✅ Derivación pendiente creada: {anomalia.estudiante.nombre}")
        
        self.stdout.write("🎉 Alertas de prueba generadas exitosamente")