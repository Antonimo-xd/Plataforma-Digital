# urls.py (project urls)
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

@login_required
def redirect_to_dashboard(request):
    """
    Función que redirige al dashboard SOLO si el usuario está autenticado.
    El decorador @login_required se encarga de redirigir al login si no lo está.
    """
    return redirect('/cpa/')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Redirección de la raíz al dashboard (CON LOGIN REQUERIDO)
    path('', redirect_to_dashboard, name='home'),
    
    # Sistema de autenticación
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # URLs de la aplicación principal
    path('cpa/', include('prototipo.urls')),
]