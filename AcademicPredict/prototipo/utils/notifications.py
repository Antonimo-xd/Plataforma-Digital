from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)

def enviar_notificacion_derivacion(derivacion):
    """
    Envía notificación cuando se crea una derivación
    
    Args:
        derivacion: Instancia de Derivacion
        
    🎓 APRENDIZAJE: Las notificaciones deben ser asíncronas en producción
    - Usar Celery o Django Q para no bloquear la respuesta
    - Manejar errores sin afectar el flujo principal
    """
    try:
        # Email al responsable de la instancia de apoyo
        asunto = f'Nueva derivación: {derivacion.deteccion_anomalia.estudiante.nombre}'
        
        contexto = {
            'derivacion': derivacion,
            'estudiante': derivacion.deteccion_anomalia.estudiante,
            'anomalia': derivacion.deteccion_anomalia,
            'url_detalle': f"{settings.SITE_URL}/derivaciones/{derivacion.id}/"
        }
        
        mensaje_html = render_to_string(
            'emails/nueva_derivacion.html', 
            contexto
        )
        
        destinatarios = [derivacion.instancia_apoyo.responsable.email]
        
        send_mail(
            subject=asunto,
            message='',  # Texto plano como fallback
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=destinatarios,
            html_message=mensaje_html,
            fail_silently=True  # No romper si falla el email
        )
        
        logger.info(f"Notificación enviada para derivación {derivacion.id}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación: {str(e)}")

def enviar_notificacion_cambio_estado(anomalia, nuevo_estado):
    """
    Notifica cambio de estado de anomalía
    
    Args:
        anomalia: DeteccionAnomalia
        nuevo_estado: Nuevo estado
    """
    # Si es resuelta, notificar al coordinador de carrera
    if nuevo_estado == 'resuelta':
        coordinador = anomalia.estudiante.carrera.coordinador
        if coordinador and coordinador.email:
            enviar_email_resolucion(anomalia, coordinador)

def enviar_notificaciones_email(alertas, deteccion_anomalia):
    """
    Envía emails para alertas automáticas
    
    Args:
        alertas: QuerySet de AlertaAutomatica
        deteccion_anomalia: DeteccionAnomalia relacionada
    """
    for alerta in alertas:
        try:
            destinatarios = obtener_destinatarios_alerta(alerta)
            
            contexto = {
                'alerta': alerta,
                'anomalia': deteccion_anomalia,
                'estudiante': deteccion_anomalia.estudiante
            }
            
            mensaje = render_to_string(
                'emails/alerta_automatica.html',
                contexto
            )
            
            send_mail(
                subject=f'⚠️ Alerta: {alerta.tipo}',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=destinatarios,
                html_message=mensaje,
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Error en alerta {alerta.id}: {str(e)}")

def obtener_destinatarios_alerta(alerta):
    """Determina a quién enviar la alerta según su tipo"""
    destinatarios = []
    
    if alerta.nivel_criticidad == 'alta':
        # Alertas críticas van al coordinador CPA
        from prototipo.models import Usuario
        coordinadores = Usuario.objects.filter(rol='coordinador_cpa')
        destinatarios.extend([c.email for c in coordinadores if c.email])
    
    # Siempre incluir al coordinador de la carrera
    coordinador_carrera = alerta.deteccion_anomalia.estudiante.carrera.coordinador
    if coordinador_carrera and coordinador_carrera.email:
        destinatarios.append(coordinador_carrera.email)
    
    return list(set(destinatarios))  # Eliminar duplicados  

def enviar_email_resolucion(anomalia, destinatario):
    """Notifica que una anomalía fue resuelta"""
    try:
        contexto = {
            'anomalia': anomalia,
            'estudiante': anomalia.estudiante
        }
        
        mensaje = render_to_string('emails/anomalia_resuelta.html', contexto)
        
        send_mail(
            subject=f'✅ Anomalía resuelta: {anomalia.estudiante.nombre}',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario.email],
            html_message=mensaje,
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Error enviando email de resolución: {str(e)}")
