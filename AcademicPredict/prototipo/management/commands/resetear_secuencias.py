from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Resetea las secuencias de IDs en PostgreSQL'

    def handle(self, *args, **options):
        self.stdout.write("🔄 Reseteando secuencias de PostgreSQL...")
        
        with connection.cursor() as cursor:
            # Obtener todas las secuencias de la aplicación
            cursor.execute("""
                SELECT sequence_name 
                FROM information_schema.sequences 
                WHERE sequence_schema = 'public' 
                AND sequence_name LIKE 'prototipo_%_id_seq'
            """)
            
            secuencias = cursor.fetchall()
            
            for secuencia in secuencias:
                seq_name = secuencia[0]
                try:
                    cursor.execute(f"ALTER SEQUENCE {seq_name} RESTART WITH 1")
                    self.stdout.write(f"✅ Secuencia {seq_name} reseteada")
                except Exception as e:
                    self.stdout.write(f"⚠️ Error con {seq_name}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS("🎉 Secuencias reseteadas exitosamente")
        )