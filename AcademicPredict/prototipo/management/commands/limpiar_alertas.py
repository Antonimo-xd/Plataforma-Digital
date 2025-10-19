from datetime import timezone, timedelta
from models import AlertaAutomatica

def limpiar_alertas_antiguas():
    import logging
    logger = logging.getLogger(__name__)
    """
    🧹 Limpia alertas automáticas antiguas para mantener el sistema eficiente
    
    📚 EDUCATIVO: Las tareas de mantenimiento son importantes en sistemas
    que acumulan datos con el tiempo. Esta función puede ser llamada
    periódicamente por un cron job o tarea programada.
    """
    try:
        fecha_limite = timezone.now() - timedelta(days=30)
        
        # Eliminar alertas inactivas más antiguas de 30 días
        alertas_eliminadas = AlertaAutomatica.objects.filter(
            activa=False,
            fecha_creacion__lt=fecha_limite
        ).count()
        
        AlertaAutomatica.objects.filter(
            activa=False,
            fecha_creacion__lt=fecha_limite
        ).delete()
        
        # Marcar como inactivas las alertas resueltas más antiguas de 7 días
        fecha_limite_resueltas = timezone.now() - timedelta(days=7)
        alertas_desactivadas = AlertaAutomatica.objects.filter(
            activa=True,
            deteccion_relacionada__estado='resuelto',
            fecha_creacion__lt=fecha_limite_resueltas
        ).update(activa=False)
        
        print(f"🧹 Limpieza completada: {alertas_eliminadas} eliminadas, {alertas_desactivadas} desactivadas")
        logger.info(f"Limpieza de alertas: {alertas_eliminadas} eliminadas, {alertas_desactivadas} desactivadas")
        
        return {
            'alertas_eliminadas': alertas_eliminadas,
            'alertas_desactivadas': alertas_desactivadas
        }
        
    except Exception as e:
        logger.error(f"Error en limpieza de alertas: {str(e)}")
        print(f"❌ Error en limpieza: {str(e)}")
        raise
