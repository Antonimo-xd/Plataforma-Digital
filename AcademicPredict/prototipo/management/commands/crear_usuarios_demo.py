from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from prototipo.models import Carrera, InstanciaApoyo

User = get_user_model()

class Command(BaseCommand):
    help = 'Crea usuarios de demostración para el sistema'

    def handle(self, *args, **options):
        # Crear carrera de ejemplo
        carrera, created = Carrera.objects.get_or_create(
            codigo='INFO',
            defaults={
                'nombre': 'Ingeniería en Informática'
            }
        )
        
        # Crear usuarios demo
        usuarios_demo = [
            {
                'username': 'admin',
                'email': 'admin@universidad.cl',
                'first_name': 'Administrador',
                'last_name': 'Sistema',
                'rol': 'admin',
                'is_superuser': True,
                'is_staff': True
            },
            {
                'username': 'analista',
                'email': 'analista@universidad.cl',
                'first_name': 'María',
                'last_name': 'González',
                'rol': 'analista_cpa'
            },
            {
                'username': 'coordinador',
                'email': 'coordinador@universidad.cl',
                'first_name': 'Juan',
                'last_name': 'Pérez',
                'rol': 'coordinador_cpa'
            },
            {
                'username': 'coord_carrera',
                'email': 'coord.carrera@universidad.cl',
                'first_name': 'Ana',
                'last_name': 'Martínez',
                'rol': 'coordinador_carrera'
            }
        ]
        
        for user_data in usuarios_demo:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults=user_data
            )
            
            if created:
                user.set_password('demo123')  # Contraseña por defecto
                user.save()
                
                # Asignar carrera al coordinador de carrera
                if user.rol == 'coordinador_carrera':
                    carrera.coordinador = user
                    carrera.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'Usuario creado: {user.username} ({user.get_rol_display()})')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Usuario ya existe: {user.username}')
                )
        
        # Crear instancias de apoyo de ejemplo
        instancias_apoyo = [
            {
                'nombre': 'Tutoría Académica de Matemáticas',
                'tipo': 'tutoria',
                'contacto': 'Prof. Carlos López',
                'email': 'tutoria.matematicas@universidad.cl',
                'telefono': '+56 9 1234 5678',
                'descripcion': 'Apoyo académico en matemáticas y álgebra'
            },
            {
                'nombre': 'Clínica de Aprendizaje',
                'tipo': 'clinica',
                'contacto': 'Dra. Laura Silva',
                'email': 'clinica.aprendizaje@universidad.cl',
                'telefono': '+56 9 8765 4321',
                'descripcion': 'Apoyo para estudiantes con dificultades de aprendizaje'
            },
            {
                'nombre': 'Psicopedagogía',
                'tipo': 'psicopedagogia',
                'contacto': 'Psic. Roberto Vega',
                'email': 'psicopedagogia@universidad.cl',
                'telefono': '+56 9 5555 5555',
                'descripcion': 'Apoyo psicopedagógico integral'
            }
        ]
        
        for instancia_data in instancias_apoyo:
            instancia, created = InstanciaApoyo.objects.get_or_create(
                nombre=instancia_data['nombre'],
                defaults=instancia_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Instancia de apoyo creada: {instancia.nombre}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('\n¡Usuarios y datos de demostración creados exitosamente!')
        )
        self.stdout.write('Credenciales de acceso:')
        self.stdout.write('- admin / demo123 (Aministrador)')
        self.stdout.write('- analista / demo123 (Analista CPA)')
        self.stdout.write('- coordinador / demo123 (Coordinador CPA)')
        self.stdout.write('- coord_carrera / demo123 (Coordinador de Carrera)')
