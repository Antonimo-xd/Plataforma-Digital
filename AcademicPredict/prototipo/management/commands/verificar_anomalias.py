from django.core.management.base import BaseCommand
from prototipo.models import *

class Command(BaseCommand):
    help = 'Verifica el estado actual de las anomalías'

    def handle(self, *args, **options):
        self.stdout.write("🔍 VERIFICACIÓN DE ANOMALÍAS")
        self.stdout.write("=" * 40)
        
        # Contar todas las anomalías
        total = DeteccionAnomalia.objects.count()
        self.stdout.write(f"Total anomalías: {total}")
        
        if total == 0:
            self.stdout.write("❌ No hay anomalías en la base de datos")
            return
        
        # Por estado
        self.stdout.write("\n📊 Por estado:")
        for codigo, nombre in DeteccionAnomalia.ESTADOS:
            count = DeteccionAnomalia.objects.filter(estado=codigo).count()
            self.stdout.write(f"  {nombre}: {count}")
        
        # Por tipo
        self.stdout.write("\n🎯 Por tipo:")
        for codigo, nombre in DeteccionAnomalia.TIPOS_ANOMALIA:
            count = DeteccionAnomalia.objects.filter(tipo_anomalia=codigo).count()
            if count > 0:
                self.stdout.write(f"  {nombre}: {count}")
        
        # Por prioridad
        self.stdout.write("\n⚡ Por prioridad:")
        for i in range(1, 6):
            count = DeteccionAnomalia.objects.filter(prioridad=i).count()
            if count > 0:
                self.stdout.write(f"  Prioridad {i}: {count}")
        
        # Últimas 5 anomalías
        self.stdout.write("\n🕒 Últimas 5 anomalías:")
        ultimas = DeteccionAnomalia.objects.order_by('-fecha_deteccion')[:5]
        for anomalia in ultimas:
            self.stdout.write(f"  - {anomalia.estudiante.nombre}: {anomalia.get_tipo_anomalia_display()} (Prioridad {anomalia.prioridad})")
        
        self.stdout.write(f"\n✅ Verificación completada")