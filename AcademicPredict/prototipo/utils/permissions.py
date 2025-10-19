from django.contrib.auth.decorators import user_passes_test

def es_coordinador_cpa(user):
    """Verifica si el usuario es Coordinador CPA"""
    return user.is_authenticated and user.rol == 'coordinador_cpa'

def es_analista_cpa(user):
    """Verifica si el usuario es Analista CPA"""
    return user.is_authenticated and user.rol == 'analista_cpa'

def es_coordinador_carrera(user):
    """Verifica si el usuario es Coordinador de Carrera"""
    return user.is_authenticated and user.rol == 'coordinador_carrera'

def puede_ver_anomalias(user):
    """Verifica si el usuario puede ver anomalías"""
    return (es_coordinador_cpa(user) or 
            es_analista_cpa(user) or 
            es_coordinador_carrera(user))

def puede_administrar_sistema(user):
    """Verifica si el usuario puede administrar el sistema"""
    return user.is_authenticated and (
        user.is_superuser or 
        es_coordinador_cpa(user)
    )

def puede_ver_estadisticas(user):
    """Verifica si el usuario puede ver estadísticas"""
    return puede_ver_anomalias(user)

def puede_editar_derivacion(derivacion, usuario):
    """Verifica si el usuario puede editar una derivación"""
    return (es_coordinador_cpa(usuario) or 
            derivacion.usuario_creador == usuario)

def puede_cambiar_estado_derivacion(derivacion, usuario):
    """Verifica si el usuario puede cambiar estado de derivación"""
    if es_coordinador_cpa(usuario):
        return True
    if derivacion.instancia_apoyo.responsable == usuario:
        return True
    return False

def puede_añadir_seguimiento(derivacion, usuario):
    """Verifica si el usuario puede añadir seguimiento"""
    return (es_coordinador_cpa(usuario) or 
            es_analista_cpa(usuario) or
            derivacion.instancia_apoyo.responsable == usuario)