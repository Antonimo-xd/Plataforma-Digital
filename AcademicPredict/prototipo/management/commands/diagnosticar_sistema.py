from django.core.management.base import BaseCommand
from prototipo.models import *
from prototipo.utils import ejecutar_deteccion_anomalias

class Command(BaseCommand):
    help = 'Diagnostica problemas del sistema CPA'

    def handle(self, *args, **options):
        self.stdout.write("🔍 DIAGNÓSTICO DEL SISTEMA CPA")
        self.stdout.write("=" * 50)
        
        # 1. Verificar datos básicos
        self.verificar_datos_basicos()
        
        # 2. Verificar criterios
        self.verificar_criterios()
        
        # 3. Probar análisis
        self.probar_analisis()
        
        # 4. Verificar anomalías
        self.verificar_anomalias()

    def verificar_datos_basicos(self):
        self.stdout.write("\n📊 DATOS BÁSICOS:")
        
        estudiantes = Estudiante.objects.filter(activo=True).count()
        self.stdout.write(f"✓ Estudiantes activos: {estudiantes}")
        
        registros = RegistroAcademico.objects.count()
        self.stdout.write(f"✓ Registros académicos: {registros}")
        
        asignaturas = Asignatura.objects.count()
        self.stdout.write(f"✓ Asignaturas: {asignaturas}")
        
        carreras = Carrera.objects.count()
        self.stdout.write(f"✓ Carreras: {carreras}")
        
        # Verificar distribución
        if estudiantes > 0:
            registros_por_estudiante = registros / estudiantes
            self.stdout.write(f"✓ Promedio registros/estudiante: {registros_por_estudiante:.1f}")
            
            if registros_por_estudiante < 3:
                self.stdout.write("⚠️  PROBLEMA: Pocos registros por estudiante (<3)")
        
        if estudiantes < 10:
            self.stdout.write("❌ PROBLEMA: Muy pocos estudiantes (<10)")
        if registros < 30:
            self.stdout.write("❌ PROBLEMA: Muy pocos registros (<30)")

    def verificar_criterios(self):
        self.stdout.write("\n⚙️  CRITERIOS:")
        
        criterios = CriterioAnomalia.objects.filter(activo=True)
        self.stdout.write(f"✓ Criterios activos: {criterios.count()}")
        
        for criterio in criterios:
            self.stdout.write(f"  - {criterio.nombre}")
            self.stdout.write(f"    Carrera: {criterio.carrera or 'Todas'}")
            self.stdout.write(f"    Contaminación: {criterio.contamination_rate}")
            
            # Verificar ejecuciones
            ejecuciones = criterio.ejecucionanalisis_set.count()
            ejecuciones_exitosas = criterio.ejecucionanalisis_set.filter(exitoso=True).count()
            self.stdout.write(f"    Ejecuciones: {ejecuciones} ({ejecuciones_exitosas} exitosas)")

    def probar_analisis(self):
        self.stdout.write("\n🧪 PRUEBA DE ANÁLISIS:")
        
        criterio = CriterioAnomalia.objects.filter(activo=True).first()
        if not criterio:
            self.stdout.write("❌ No hay criterios activos para probar")
            return
        
        usuario = Usuario.objects.filter(is_superuser=True).first()
        if not usuario:
            self.stdout.write("❌ No hay usuario administrador")
            return
        
        self.stdout.write(f"Probando criterio: {criterio.nombre}")
        
        try:
            resultado = ejecutar_deteccion_anomalias(criterio, usuario)
            
            if resultado['exitoso']:
                self.stdout.write(f"✅ Análisis exitoso: {resultado['anomalias_detectadas']} anomalías")
            else:
                self.stdout.write(f"❌ Error en análisis: {resultado['error']}")
                
        except Exception as e:
            self.stdout.write(f"❌ Excepción en análisis: {str(e)}")

    def verificar_anomalias(self):
        self.stdout.write("\n🚨 ANOMALÍAS:")
        
        total_anomalias = DeteccionAnomalia.objects.count()
        self.stdout.write(f"✓ Total anomalías: {total_anomalias}")
        
        anomalias_activas = DeteccionAnomalia.objects.filter(
            estado__in=['detectado', 'en_revision', 'intervencion_activa']
        ).count()
        self.stdout.write(f"✓ Anomalías activas: {anomalias_activas}")
        
        # Por criterio
        for criterio in CriterioAnomalia.objects.filter(activo=True):
            count = DeteccionAnomalia.objects.filter(criterio_usado=criterio).count()
            self.stdout.write(f"  - {criterio.nombre}: {count} anomalías")