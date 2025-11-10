from django.utils import timezone
from django.db.models import Count, Avg
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging

# Imports de modelos locales
from ..models import (DeteccionAnomalia, Estudiante, RegistroAcademico, Carrera, Asignatura, AlertaAutomatica, Derivacion, Usuario, CriterioAnomalia)
from .permissions import (puede_editar_derivacion, puede_cambiar_estado_derivacion, puede_añadir_seguimiento)

# ================================================================
# CONFIGURACIÓN DE LOGGING
# ================================================================
logger = logging.getLogger(__name__)

def determinar_nivel_criticidad(estudiante, datos_anomalia=None):
    """
    Determina el nivel de criticidad de una anomalía académica
    
    🎓 EDUCATIVO: Esta función debe retornar 'baja', 'media' o 'alta'
    para que coincida con el campo nivel_criticidad del modelo.
    
    Returns:
        str: 'baja', 'media' o 'alta'
    """
    try:
        print(f"🔍 Evaluando criticidad para: {estudiante.nombre}")
        
        # Obtener registros académicos
        registros = RegistroAcademico.objects.filter(estudiante=estudiante)
        
        if not registros.exists():
            logger.warning(f"Estudiante {estudiante.nombre} sin registros académicos")
            return 'media'  # ← Retornar texto, no número
        
        # Calcular métricas
        promedio_general = registros.aggregate(Avg('promedio_notas'))['promedio_notas__avg'] or 0
        asistencia_promedio = registros.aggregate(Avg('porcentaje_asistencia'))['porcentaje_asistencia__avg'] or 0
        uso_plataforma_promedio = registros.aggregate(Avg('porcentaje_uso_plataforma'))['porcentaje_uso_plataforma__avg'] or 0
        
        # Calcular variación de notas
        notas_todas = []
        for registro in registros:
            notas_todas.extend([
                registro.nota1, registro.nota2, 
                registro.nota3, registro.nota4
            ])
        
        import numpy as np
        variacion_notas = np.std(notas_todas) if notas_todas else 0
        
        # Contar asignaturas reprobadas
        asignaturas_reprobadas = registros.filter(promedio_notas__lt=4.0).count()
        total_asignaturas = registros.count()
        porcentaje_reprobacion = (asignaturas_reprobadas / total_asignaturas * 100) if total_asignaturas > 0 else 0
        
        # ================================================================
        # LÓGICA DE CRITICIDAD (retorna texto)
        # ================================================================
        
        puntos_criticidad = 0
        
        # Factor 1: Promedio general
        if promedio_general < 3.5:
            puntos_criticidad += 3
        elif promedio_general < 4.0:
            puntos_criticidad += 2
        elif promedio_general < 4.5:
            puntos_criticidad += 1
        
        # Factor 2: Asistencia
        if asistencia_promedio < 60:
            puntos_criticidad += 3
        elif asistencia_promedio < 75:
            puntos_criticidad += 2
        elif asistencia_promedio < 85:
            puntos_criticidad += 1
        
        # Factor 3: Uso de plataforma
        if uso_plataforma_promedio < 50:
            puntos_criticidad += 2
        elif uso_plataforma_promedio < 70:
            puntos_criticidad += 1
        
        # Factor 4: Variación de notas
        if variacion_notas > 1.5:
            puntos_criticidad += 2
        elif variacion_notas > 1.0:
            puntos_criticidad += 1
        
        # Factor 5: Reprobación
        if porcentaje_reprobacion > 50:
            puntos_criticidad += 3
        elif porcentaje_reprobacion > 30:
            puntos_criticidad += 2
        elif porcentaje_reprobacion > 10:
            puntos_criticidad += 1
        
        # ================================================================
        # DETERMINAR NIVEL SEGÚN PUNTOS (retorna texto)
        # ================================================================
        
        if puntos_criticidad >= 8:
            nivel = 'alta'
        elif puntos_criticidad >= 4:
            nivel = 'media'
        else:
            nivel = 'baja'
        
        print(f"✅ Criticidad determinada: {nivel} (puntos: {puntos_criticidad})")
        print(f"   - Promedio: {promedio_general:.2f}")
        print(f"   - Asistencia: {asistencia_promedio:.1f}%")
        print(f"   - Uso plataforma: {uso_plataforma_promedio:.1f}%")
        print(f"   - Variación notas: {variacion_notas:.2f}")
        print(f"   - Reprobación: {porcentaje_reprobacion:.1f}%")
        
        return nivel  # ← Retorna 'baja', 'media' o 'alta'
        
    except Exception as e:
        logger.error(f"❌ Error en determinar_nivel_criticidad: {str(e)}")
        print(f"❌ Error en determinar_nivel_criticidad: {str(e)}")
        return 'media'  # Valor por defecto en caso de error
    
def crear_alertas_automaticas(deteccion_anomalia):
    """
    🚨 Crea alertas automáticas basadas en una detección de anomalía
    """
    try:
        print(f"🚨 Creando alertas para anomalía: {deteccion_anomalia.id}")
        
        alertas_creadas = []
        estudiante = deteccion_anomalia.estudiante
        
        # ================================================================
        # ALERTA 2: ANOMALÍA CRÍTICA
        # ✅ CORRECCIÓN: Se quitó el campo 'destinatario'
        # ================================================================
        if deteccion_anomalia.prioridad >= 4:  # Urgente o Crítica
            alerta_critica = AlertaAutomatica.objects.create(
                tipo='anomalia_critica',
                titulo=f'⚠️ ANOMALÍA CRÍTICA: {estudiante.nombre}',
                mensaje=f'ATENCIÓN: Se detectó una anomalía crítica (prioridad {deteccion_anomalia.prioridad}) '
                        f'para {estudiante.nombre}. Requiere intervención inmediata.\n\n'
                        f'Tipo: {deteccion_anomalia.get_tipo_anomalia_display()}\n'
                        f'Score: {deteccion_anomalia.score_anomalia:.3f}\n'
                        f'Confianza: {deteccion_anomalia.confianza:.1f}%',
                deteccion_relacionada=deteccion_anomalia,
                # destinatario=None,  <-- ESTE CAMPO NO EXISTE
                activa=True,
                fecha_creacion=timezone.now()
            )
            alertas_creadas.append(alerta_critica)
            print(f"🚨 Alerta crítica creada para prioridad {deteccion_anomalia.prioridad}")
        
        # ================================================================
        # ALERTA 3: ASIGNATURA CRÍTICA
        # ================================================================
        registros_estudiante = RegistroAcademico.objects.filter(estudiante=estudiante)
        
        for registro in registros_estudiante:
            if registro.asignatura:
                anomalias_asignatura = DeteccionAnomalia.objects.filter(
                    estudiante__in=RegistroAcademico.objects.filter(
                        asignatura=registro.asignatura
                    ).values('estudiante'),
                    fecha_deteccion__gte=timezone.now() - timedelta(days=30)
                ).count()
                
                if anomalias_asignatura >= 5:
                    alerta_existente = AlertaAutomatica.objects.filter(
                        tipo='asignatura_critica',
                        asignatura_relacionada=registro.asignatura,
                        fecha_creacion__gte=timezone.now() - timedelta(days=7)
                    ).exists()
                    
                    if not alerta_existente:
                        # ✅ CORRECCIÓN: Se quitó el campo 'destinatario'
                        alerta_asignatura = AlertaAutomatica.objects.create(
                            tipo='asignatura_critica',
                            titulo=f'Asignatura crítica: {registro.asignatura.nombre}',
                            mensaje=f'La asignatura "{registro.asignatura.nombre}" presenta '
                                    f'{anomalias_asignatura} anomalías en los últimos 30 días. '
                                    f'Se recomienda revisar metodología y estrategias de enseñanza.',
                            asignatura_relacionada=registro.asignatura,
                            # destinatario=None,  <-- ESTE CAMPO NO EXISTE
                            activa=True,
                            fecha_creacion=timezone.now()
                        )
                        alertas_creadas.append(alerta_asignatura)
                        print(f"📚 Alerta de asignatura crítica creada: {registro.asignatura.nombre}")
        
        # ================================================================
        # ALERTA 4: SEGUIMIENTO VENCIDO
        # ================================================================
        derivaciones_vencidas = Derivacion.objects.filter(
            deteccion_anomalia__estudiante=estudiante,
            estado__in=['enviada', 'recibida'],
            fecha_derivacion__lte=timezone.now() - timedelta(days=7),
            fecha_seguimiento__isnull=True
        )
        
        for derivacion in derivaciones_vencidas:
            # ✅ CORRECCIÓN: Se quitó 'destinatario' del .create() y se usó .add()
            alerta_seguimiento = AlertaAutomatica.objects.create(
                tipo='seguimiento_vencido',
                titulo=f'Seguimiento vencido: {estudiante.nombre}',
                mensaje=f'La derivación de {estudiante.nombre} a {derivacion.instancia_apoyo.nombre} '
                        f'está pendiente de seguimiento desde hace más de 7 días.\n'
                        f'Fecha derivación: {derivacion.fecha_derivacion.strftime("%d/%m/%Y")}\n'
                        f'Estado actual: {derivacion.get_estado_display()}',
                deteccion_relacionada=deteccion_anomalia,
                # destinatario=derivacion.derivado_por,  <-- ESTE CAMPO NO EXISTE
                activa=True,
                fecha_creacion=timezone.now()
            )
            
            # Así se asigna un ManyToManyField después de crear el objeto
            if derivacion.derivado_por:
                alerta_seguimiento.destinatarios.add(derivacion.derivado_por)
                
            alertas_creadas.append(alerta_seguimiento)
            print(f"⏰ Alerta de seguimiento vencido creada")
        
        # ================================================================
        # ENVÍO DE NOTIFICACIONES POR EMAIL (Si está configurado)
        # ================================================================
        if hasattr(settings, 'EMAIL_HOST') and settings.EMAIL_HOST:
            try:
                enviar_notificaciones_email(alertas_creadas, deteccion_anomalia)
            except Exception as e:
                logger.warning(f"No se pudieron enviar emails: {str(e)}")
                print(f"⚠️ No se pudieron enviar emails: {str(e)}")
        
        print(f"✅ Se crearon {len(alertas_creadas)} alertas automáticas")
        logger.info(f"Creadas {len(alertas_creadas)} alertas para anomalía {deteccion_anomalia.id}")
        
        return alertas_creadas
        
    except Exception as e:
        logger.error(f"Error creando alertas automáticas: {str(e)}")
        print(f"❌ Error creando alertas automáticas: {str(e)}")
        raise  # Vuelve a lanzar el error para que el try/except de 'guardar_anomalias' lo capture

def detalle_derivacion_ajax(derivacion_id, usuario_solicitante):
    """
    📡 Obtiene detalles de una derivación para peticiones AJAX
    
    📚 EDUCATIVO: Esta función implementa el patrón de API interna para
    obtener datos estructurados que serán consumidos por JavaScript.
    Es común separar la lógica de obtención de datos de la presentación HTML.
    
    Args:
        derivacion_id (int): ID de la derivación a consultar
        usuario_solicitante (Usuario): Usuario que solicita la información
        
    Returns:
        dict: Datos estructurados de la derivación
        
    Raises:
        PermissionError: Si el usuario no tiene permisos
        Derivacion.DoesNotExist: Si la derivación no existe
    """
    try:
        print(f"📡 Obteniendo detalles de derivación {derivacion_id}")
        
        # ================================================================
        # PASO 1: VERIFICAR PERMISOS DE ACCESO
        # ================================================================
        derivacion = Derivacion.objects.select_related(
            'deteccion_anomalia__estudiante__carrera',
            'instancia_apoyo',
            'derivado_por'
        ).get(id=derivacion_id)
        
        # Verificar permisos según rol del usuario
        tiene_permiso = False
        
        if usuario_solicitante.rol in ['coordinador_cpa', 'analista_cpa']:
            # Los roles CPA pueden ver todas las derivaciones
            tiene_permiso = True
        elif usuario_solicitante.rol == 'coordinador_carrera':
            # Los coordinadores de carrera solo ven derivaciones de su carrera
            try:
                carrera_usuario = Carrera.objects.get(coordinador=usuario_solicitante)
                if derivacion.deteccion_anomalia.estudiante.carrera == carrera_usuario:
                    tiene_permiso = True
            except Carrera.DoesNotExist:
                pass
        elif derivacion.derivado_por == usuario_solicitante:
            # El usuario que creó la derivación puede verla
            tiene_permiso = True
        
        if not tiene_permiso:
            raise PermissionError(f"Usuario {usuario_solicitante.username} no tiene permisos para ver derivación {derivacion_id}")
        
        # ================================================================
        # PASO 2: OBTENER DATOS RELACIONADOS
        # ================================================================
        estudiante = derivacion.deteccion_anomalia.estudiante
        anomalia = derivacion.deteccion_anomalia
        
        # Obtener historial de cambios de estado (si existe un modelo de auditoria)
        historial_estados = []
        # TODO: Implementar sistema de auditoria para trackear cambios de estado
        
        # Obtener otras derivaciones del mismo estudiante
        otras_derivaciones = Derivacion.objects.filter(
            deteccion_anomalia__estudiante=estudiante
        ).exclude(id=derivacion_id).order_by('-fecha_derivacion')[:5]
        
        # Calcular tiempo transcurrido
        tiempo_transcurrido = timezone.now() - derivacion.fecha_derivacion
        dias_transcurridos = tiempo_transcurrido.days
        
        # Determinar urgencia basada en tiempo y prioridad
        urgencia = "normal"
        if derivacion.prioridad >= 4 and dias_transcurridos > 3:
            urgencia = "alta"
        elif derivacion.prioridad >= 3 and dias_transcurridos > 7:
            urgencia = "media"
        elif dias_transcurridos > 14:
            urgencia = "media"
        
        # ================================================================
        # PASO 3: ENSAMBLAR RESPUESTA ESTRUCTURADA
        # ================================================================
        detalles = {
            'derivacion': {
                'id': derivacion.id,
                'estado': derivacion.estado,
                'estado_display': derivacion.get_estado_display(),
                'prioridad': derivacion.prioridad,
                'prioridad_display': derivacion.get_prioridad_display(),
                'fecha_derivacion': derivacion.fecha_derivacion.isoformat(),
                'fecha_derivacion_formatted': derivacion.fecha_derivacion.strftime('%d/%m/%Y %H:%M'),
                'motivo': derivacion.motivo,
                'observaciones_derivacion': derivacion.observaciones_derivacion,
                'respuesta_instancia': derivacion.respuesta_instancia,
                'observaciones_seguimiento': derivacion.observaciones_seguimiento,
                'fecha_respuesta': derivacion.fecha_respuesta.isoformat() if derivacion.fecha_respuesta else None,
                'fecha_seguimiento': derivacion.fecha_seguimiento.isoformat() if derivacion.fecha_seguimiento else None,
                'dias_transcurridos': dias_transcurridos,
                'urgencia': urgencia
            },
            
            'estudiante': {
                'id': estudiante.id_estudiante,
                'nombre': estudiante.nombre,
                'carrera': estudiante.carrera.nombre,
                'ingreso_año': estudiante.ingreso_año,
                'activo': estudiante.activo
            },
            
            'anomalia': {
                'id': anomalia.id,
                'tipo': anomalia.tipo_anomalia,
                'tipo_display': anomalia.get_tipo_anomalia_display(),
                'prioridad': anomalia.prioridad,
                'score_anomalia': float(anomalia.score_anomalia),
                'confianza': float(anomalia.confianza),
                'fecha_deteccion': anomalia.fecha_deteccion.isoformat(),
                'estado': anomalia.estado,
                'estado_display': anomalia.get_estado_display()
            },
            
            'instancia_apoyo': {
                'id': derivacion.instancia_apoyo.id,
                'nombre': derivacion.instancia_apoyo.nombre,
                'tipo': derivacion.instancia_apoyo.tipo,
                'contacto': derivacion.instancia_apoyo.contacto,
                'email': derivacion.instancia_apoyo.email,
                'telefono': derivacion.instancia_apoyo.telefono,
                'activa': derivacion.instancia_apoyo.activa
            },
            
            'derivado_por': {
                'username': derivacion.derivado_por.username if derivacion.derivado_por else 'Sistema',
                'nombre_completo': f"{derivacion.derivado_por.first_name} {derivacion.derivado_por.last_name}".strip() if derivacion.derivado_por else 'Sistema Automático',
                'rol': derivacion.derivado_por.get_rol_display() if derivacion.derivado_por else 'Sistema'
            },
            
            'otras_derivaciones': [
                {
                    'id': d.id,
                    'instancia': d.instancia_apoyo.nombre,
                    'estado': d.get_estado_display(),
                    'fecha': d.fecha_derivacion.strftime('%d/%m/%Y')
                }
                for d in otras_derivaciones
            ],
            
            'acciones_disponibles': _calcular_acciones_disponibles(derivacion, usuario_solicitante),
            
            'metadatos': {
                'consultado_por': usuario_solicitante.username,
                'fecha_consulta': timezone.now().isoformat(),
                'permisos_usuario': {
                    'puede_editar': puede_editar_derivacion(derivacion, usuario_solicitante),
                    'puede_cambiar_estado': puede_cambiar_estado_derivacion(derivacion, usuario_solicitante),
                    'puede_añadir_seguimiento': puede_añadir_seguimiento(derivacion, usuario_solicitante)
                }
            }
        }
        
        print(f"✅ Detalles obtenidos para derivación {derivacion_id}")
        logger.info(f"Detalles de derivación {derivacion_id} consultados por {usuario_solicitante.username}")
        
        return detalles
        
    except Derivacion.DoesNotExist:
        logger.warning(f"Derivación {derivacion_id} no encontrada")
        raise Derivacion.DoesNotExist(f"Derivación con ID {derivacion_id} no existe")
    
    except Exception as e:
        logger.error(f"Error obteniendo detalles de derivación {derivacion_id}: {str(e)}")
        print(f"❌ Error en detalle_derivacion_ajax: {str(e)}")
        raise

# ================================================================
# FUNCIONES AUXILIARES PARA PERMISOS
# ================================================================

def _calcular_acciones_disponibles(derivacion, usuario):
    """
    🔐 Calcula qué acciones puede realizar el usuario sobre la derivación
    
    📚 EDUCATIVO: Esta función implementa lógica de autorización granular.
    En lugar de usar decoradores simples, verificamos permisos específicos
    para cada acción, permitiendo interfaces más dinámicas.
    """
    acciones = []
    
    # Acción: Ver detalles (ya verificado anteriormente)
    acciones.append('ver_detalles')
    
    # Acción: Editar derivación
    if puede_editar_derivacion(derivacion, usuario):
        acciones.append('editar')
    
    # Acción: Cambiar estado
    if puede_cambiar_estado_derivacion(derivacion, usuario):
        acciones.append('cambiar_estado')
    
    # Acción: Añadir seguimiento
    if puede_añadir_seguimiento(derivacion, usuario):
        acciones.append('añadir_seguimiento')
    
    # Acción: Generar reporte
    if usuario.rol in ['coordinador_cpa', 'analista_cpa']:
        acciones.append('generar_reporte')
    
    # Acción: Eliminar (solo coordinadores CPA y creador)
    if (usuario.rol == 'coordinador_cpa' or 
        (derivacion.derivado_por == usuario and derivacion.estado == 'pendiente')):
        acciones.append('eliminar')
    
    return acciones

# ================================================================
# FUNCIONES AUXILIARES PARA NOTIFICACIONES
# ================================================================

def enviar_notificaciones_email(alertas, deteccion_anomalia):
    """
    📧 Envía notificaciones por email para las alertas creadas
    
    📚 EDUCATIVO: Las notificaciones por email son un componente común
    en sistemas de gestión. Esta función encapsula la lógica de envío
    y permite personalizar el contenido según el tipo de alerta.
    """
    try:
        estudiante = deteccion_anomalia.estudiante
        
        # Obtener destinatarios según el tipo de alerta y rol
        destinatarios = []
        
        # Coordinadores CPA (reciben todas las notificaciones)
        coordinadores_cpa = Usuario.objects.filter(
            rol='coordinador_cpa', 
            is_active=True,
            email__isnull=False
        ).exclude(email='')
        
        for coordinador in coordinadores_cpa:
            if coordinador.email:
                destinatarios.append(coordinador.email)
        
        # Coordinador de carrera específica
        try:
            coordinador_carrera = estudiante.carrera.coordinador
            if coordinador_carrera and coordinador_carrera.email:
                destinatarios.append(coordinador_carrera.email)
        except:
            pass
        
        # Analistas CPA (para casos críticos)
        if deteccion_anomalia.prioridad >= 4:
            analistas = Usuario.objects.filter(
                rol='analista_cpa',
                is_active=True,
                email__isnull=False
            ).exclude(email='')
            
            for analista in analistas:
                if analista.email:
                    destinatarios.append(analista.email)
        
        # Eliminar duplicados
        destinatarios = list(set(destinatarios))
        
        if not destinatarios:
            print("⚠️ No hay destinatarios válidos para notificaciones")
            return
        
        # Preparar contenido del email
        asunto = f"CPA - Nueva anomalía detectada: {estudiante.nombre}"
        
        if deteccion_anomalia.prioridad >= 4:
            asunto = f"🚨 CPA CRÍTICO - {asunto}"
        
        mensaje = f"""
            Sistema de Detección de Anomalías Académicas - CPA

            Se ha detectado una nueva anomalía que requiere atención:

            ESTUDIANTE: {estudiante.nombre}
            CARRERA: {estudiante.carrera.nombre}
            TIPO DE ANOMALÍA: {deteccion_anomalia.get_tipo_anomalia_display()}
            PRIORIDAD: {deteccion_anomalia.prioridad}
            CONFIANZA: {deteccion_anomalia.confianza:.1f}%
            FECHA DETECCIÓN: {deteccion_anomalia.fecha_deteccion.strftime('%d/%m/%Y %H:%M')}

            ALERTAS GENERADAS:
            """
        
        for alerta in alertas:
            mensaje += f"- {alerta.titulo}\n"
        
        mensaje += f"""

            Para más detalles, ingrese al sistema CPA:
            {settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000'}

            Este es un mensaje automático del Sistema CPA.
            No responder a este email.
            """
        
        # Enviar email
        send_mail(
            asunto,
            mensaje,
            settings.DEFAULT_FROM_EMAIL,
            destinatarios,
            fail_silently=False,
        )
        
        print(f"📧 Notificaciones enviadas a {len(destinatarios)} destinatarios")
        logger.info(f"Emails enviados para anomalía {deteccion_anomalia.id}: {len(destinatarios)} destinatarios")
        
    except Exception as e:
        logger.error(f"Error enviando notificaciones email: {str(e)}")
        print(f"❌ Error enviando emails: {str(e)}")
        raise

# ================================================================
# FUNCIONES DE VALIDACIÓN Y UTILIDADES
# ================================================================

def validar_datos_estudiante(estudiante_data):
    """
    ✅ Valida que los datos del estudiante sean consistentes
    
    📚 EDUCATIVO: Las validaciones de integridad de datos son cruciales
    en sistemas académicos. Esta función verifica que los datos cumplan
    con las reglas de negocio antes de procesarlos.
    """
    errores = []
    
    # Validar campos requeridos
    campos_requeridos = ['nombre', 'carrera', 'id_estudiante']
    for campo in campos_requeridos:
        if not estudiante_data.get(campo):
            errores.append(f"Campo requerido faltante: {campo}")
    
    # Validar año de ingreso
    if estudiante_data.get('ingreso_año'):
        año_actual = timezone.now().year
        ingreso = estudiante_data['ingreso_año']
        if ingreso < 2000 or ingreso > año_actual + 1:
            errores.append(f"Año de ingreso inválido: {ingreso}")
    
    # Validar formato de ID estudiante
    id_estudiante = estudiante_data.get('id_estudiante')
    if id_estudiante and not str(id_estudiante).isdigit():
        errores.append("ID de estudiante debe ser numérico")
    
    return errores

def calcular_metricas_rendimiento(estudiante):
    """
    📊 Calcula métricas de rendimiento académico para un estudiante
    
    Returns:
        dict: Métricas calculadas del estudiante
    """
    try:
        registros = RegistroAcademico.objects.filter(estudiante=estudiante)
        
        if not registros.exists():
            return {
                'promedio_general': 0,
                'asistencia_promedio': 0,
                'uso_plataforma_promedio': 0,
                'asignaturas_cursadas': 0,
                'asignaturas_aprobadas': 0,
                'tasa_aprobacion': 0
            }
        
        metricas = registros.aggregate(
            promedio_general=Avg('promedio_notas'),
            asistencia_promedio=Avg('asistencia'),
            uso_plataforma_promedio=Avg('uso_plataforma')
        )
        
        asignaturas_cursadas = registros.count()
        asignaturas_aprobadas = registros.filter(promedio_notas__gte=4.0).count()
        tasa_aprobacion = (asignaturas_aprobadas / asignaturas_cursadas * 100) if asignaturas_cursadas > 0 else 0
        
        return {
            'promedio_general': round(metricas['promedio_general'] or 0, 2),
            'asistencia_promedio': round(metricas['asistencia_promedio'] or 0, 1),
            'uso_plataforma_promedio': round(metricas['uso_plataforma_promedio'] or 0, 1),
            'asignaturas_cursadas': asignaturas_cursadas,
            'asignaturas_aprobadas': asignaturas_aprobadas,
            'tasa_aprobacion': round(tasa_aprobacion, 1)
        }
        
    except Exception as e:
        logger.error(f"Error calculando métricas para {estudiante.nombre}: {str(e)}")
        return {}

def _calcular_asignaturas_criticas():
    """
    Función auxiliar para calcular asignaturas críticas
    
    🎓 EDUCATIVO: Separar cálculos complejos permite testing
    independiente y reutilización.
    """
    from django.db.models import Count, F
    
    asignaturas = Asignatura.objects.annotate(
        total_estudiantes=Count('registroacademico__estudiante', distinct=True),
        total_anomalias=Count('registroacademico__estudiante__deteccionanomalia', distinct=True)
    ).filter(
        total_estudiantes__gt=0
    ).annotate(
        porcentaje_anomalias=F('total_anomalias') * 100.0 / F('total_estudiantes')
    ).filter(
        porcentaje_anomalias__gte=20  # 20% o más
    ).order_by('-porcentaje_anomalias')[:10]
    
    return asignaturas

def _obtener_estadisticas_sistema():
    """Obtiene estadísticas básicas del sistema"""
    return {
        'estudiantes_activos': Estudiante.objects.filter(activo=True).count(),
        'registros_academicos': RegistroAcademico.objects.count(),
        'criterios_activos': CriterioAnomalia.objects.filter(activo=True).count(),
        'anomalias_total': DeteccionAnomalia.objects.count(),
        'anomalias_pendientes': DeteccionAnomalia.objects.filter(
            estado__in=['detectado', 'en_revision']
        ).count()
    }

def _determinar_estado_sistema(stats):
    """Determina el estado general del sistema"""
    if stats['criterios_activos'] == 0:
        return {'estado': 'error', 'mensaje': 'No hay criterios activos'}
    elif stats['estudiantes_activos'] < 10:
        return {'estado': 'warning', 'mensaje': 'Pocos estudiantes activos'}
    elif stats['anomalias_pendientes'] > stats['anomalias_total'] * 0.8:
        return {'estado': 'warning', 'mensaje': 'Muchas anomalías pendientes'}
    else:
        return {'estado': 'ok', 'mensaje': 'Sistema funcionando correctamente'}

