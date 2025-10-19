from django import template
from urllib.parse import urlencode

register = template.Library()

# ================================================================
# FILTROS MATEMÁTICOS (Esenciales para el sistema)
# ================================================================

@register.filter
def mul(value, arg):
    """
    Multiplica el valor por el argumento
    
    Uso en template:
    {{ 0.75|mul:100 }}  → 75.0
    
    Educativo: Usado para convertir decimales a porcentajes
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """
    Divide value por arg
    
    Uso en template:
    {{ 100|div:4 }}  → 25.0
    
    Educativo: Útil para calcular promedios y ratios
    """
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """
    Resta arg de value
    
    Uso en template:
    {{ 100|subtract:25 }}  → 75
    
    Educativo: Para cálculos de diferencias en dashboards
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """
    Calcula el porcentaje de value respecto a total
    
    Uso en template:
    {{ 25|percentage:100 }}  → 25.0
    
    Educativo: FUNCIÓN CRÍTICA para mostrar estadísticas de anomalías
    """
    try:
        if total == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0

# ================================================================  
# FILTROS PARA UI/UX (Visualización de datos)
# ================================================================

@register.filter
def progress_width(value, max_value=7.0):
    """
    Calcula el ancho de progress bar para escala de notas
    
    Uso en template:
    {{ 5.5|progress_width }}  → 78.57 (para escala 1-7)
    
    Educativo: Visualización de notas académicas en barras de progreso
    """
    try:
        return (float(value) / float(max_value)) * 100
    except (ValueError, TypeError):
        return 0

@register.filter
def initials(full_name):
    """
    Genera iniciales de un nombre completo
    
    Uso en template:
    {{ "Juan Carlos Pérez"|initials }}  → "JP"
    
    Educativo: Para avatars de usuario en el dashboard
    """
    try:
        if not full_name:
            return "??"
        
        name_parts = str(full_name).strip().split()
        
        if len(name_parts) >= 2:
            # Primer nombre + primer apellido
            return (name_parts[0][0] + name_parts[-1][0]).upper()
        elif len(name_parts) == 1:
            # Solo un nombre, tomar las primeras 2 letras
            name = name_parts[0]
            if len(name) >= 2:
                return (name[0] + name[1]).upper()
            else:
                return (name[0] + name[0]).upper()
        else:
            return "??"
    except (IndexError, AttributeError):
        return "??"

@register.filter
def avatar_color(name):
    """
    Genera un color de fondo basado en el nombre
    
    Uso en template:
    {{ "Juan Pérez"|avatar_color }}  → "bg-primary"
    
    Educativo: Colores consistentes para avatars de usuario
    """
    colors = [
        'bg-primary', 'bg-secondary', 'bg-success', 'bg-danger',
        'bg-warning', 'bg-info', 'bg-dark'
    ]
    
    try:
        # Usar el hash del nombre para seleccionar color
        hash_value = sum(ord(char) for char in str(name))
        return colors[hash_value % len(colors)]
    except:
        return 'bg-secondary'

# ================================================================
# FILTROS PARA MANIPULACIÓN DE STRINGS
# ================================================================

@register.filter
def split(value, separator):
    """
    Divide una cadena por el separador especificado
    
    Uso en template:
    {{ "Juan Carlos Pérez"|split:" " }}
    
    Educativo: Útil para procesar nombres y datos estructurados
    """
    try:
        return str(value).split(separator)
    except (AttributeError, TypeError):
        return []

@register.filter
def get_item(dictionary, key):
    """
    Obtiene un item de un diccionario
    
    Uso en template:
    {{ mydict|get_item:key }}
    
    Educativo: Acceso dinámico a diccionarios en templates
    """
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None

# ================================================================
# SIMPLE TAGS PARA URLs (Funcionalidad crítica)
# ================================================================

@register.simple_tag
def url_params(request, param_name, param_value):
    """
    Construye una URL manteniendo los parámetros GET existentes
    y actualiza/agrega el parámetro especificado
    
    Uso en template:
    {% url_params request 'page' 2 %}
    
    Educativo: CRÍTICO para paginación con filtros en listados
    """
    try:
        params = request.GET.copy()
        params[param_name] = param_value
        return urlencode(params)
    except (AttributeError, TypeError):
        return ""

@register.simple_tag  
def url_params_exclude(request, *exclude_params):
    """
    Construye una URL manteniendo todos los parámetros GET 
    excepto los especificados
    
    Uso en template:
    {% url_params_exclude request 'page' 'sort' %}
    
    Educativo: Útil para limpiar filtros específicos
    """
    try:
        params = request.GET.copy()
        for param in exclude_params:
            params.pop(param, None)
        return urlencode(params)
    except (AttributeError, TypeError):
        return ""

@register.simple_tag
def query_params(**kwargs):
    """
    Construye parámetros de query string desde kwargs
    
    Uso en template:
    {% query_params page=2 estado='activo' %}
    
    Educativo: Construcción dinámica de URLs
    """
    try:
        return urlencode(kwargs)
    except (TypeError, AttributeError):
        return ""

# ================================================================
# FUNCIONES ESPECÍFICAS PARA EL SISTEMA ACADÉMICO
# ================================================================

@register.filter
def anomaly_priority_class(priority):
    """
    Devuelve clase CSS basada en prioridad de anomalía
    
    Uso en template:  
    {{ anomalia.prioridad|anomaly_priority_class }}
    
    Educativo: Función específica del dominio académico
    """
    priority_classes = {
        1: 'text-success',      # Baja
        2: 'text-info',         # Media-Baja  
        3: 'text-warning',      # Media
        4: 'text-danger',       # Alta
        5: 'text-danger fw-bold' # Crítica
    }
    
    try:
        return priority_classes.get(int(priority), 'text-muted')
    except (ValueError, TypeError):
        return 'text-muted'

@register.filter
def grade_color(grade):
    """
    Devuelve clase CSS basada en nota (escala 1-7 chilena)
    
    Uso en template:
    {{ registro.promedio_notas|grade_color }}
    
    Educativo: Visualización específica del sistema académico chileno
    """
    try:
        grade_float = float(grade)
        if grade_float >= 6.0:
            return 'text-success fw-bold'  # Excelente
        elif grade_float >= 5.0:
            return 'text-success'          # Buena
        elif grade_float >= 4.0:  
            return 'text-warning'          # Suficiente
        else:
            return 'text-danger'           # Insuficiente
    except (ValueError, TypeError):
        return 'text-muted'

@register.filter
def attendance_color(attendance):
    """
    Devuelve clase CSS basada en porcentaje de asistencia
    
    Uso en template:
    {{ registro.porcentaje_asistencia|attendance_color }}
    
    Educativo: Codificación visual para alertas de asistencia
    """
    try:
        attendance_float = float(attendance)
        if attendance_float >= 80:
            return 'text-success'      # Buena asistencia
        elif attendance_float >= 60:
            return 'text-warning'      # Asistencia regular
        else:
            return 'text-danger'       # Asistencia crítica
    except (ValueError, TypeError):
        return 'text-muted'

# ================================================================
# FUNCIONES DE ESTADO Y BADGES
# ================================================================

@register.filter
def status_badge_class(status):
    """
    Devuelve clase de badge Bootstrap según estado
    
    Uso en template:
    {{ anomalia.estado|status_badge_class }}
    
    Educativo: Mapeo de estados de negocio a clases CSS
    """
    status_classes = {
        'detectado': 'bg-warning text-dark',
        'en_revision': 'bg-info',
        'intervencion_activa': 'bg-primary',
        'resuelto': 'bg-success',
        'falso_positivo': 'bg-secondary',
        'pendiente': 'bg-warning text-dark',
        'completado': 'bg-success',
        'cancelado': 'bg-danger'
    }
    
    return status_classes.get(str(status).lower(), 'bg-secondary')

# ================================================================  
# FILTROS DE FORMATO Y PRESENTACIÓN
# ================================================================

@register.filter
def truncate_smart(value, length=50):
    """
    Trunca texto de forma inteligente en palabras completas
    
    Uso en template:
    {{ texto_largo|truncate_smart:30 }}
    
    Educativo: Presentación limpia de textos largos
    """
    try:
        text = str(value)
        if len(text) <= length:
            return text
        
        # Buscar el último espacio antes del límite
        truncated = text[:length]
        last_space = truncated.rfind(' ')
        
        if last_space > 0:
            return truncated[:last_space] + '...'
        else:
            return truncated + '...'
            
    except (TypeError, AttributeError):
        return value

@register.filter
def format_score(score):
    """
    Formatea score de anomalía para mostrar
    
    Uso en template:
    {{ anomalia.score_anomalia|format_score }}
    
    Educativo: Formato específico para scores de ML
    """
    try:
        score_float = float(score)
        if score_float >= 0.8:
            return f"{score_float:.3f} (Alto)"
        elif score_float >= 0.5:
            return f"{score_float:.3f} (Medio)"
        else:
            return f"{score_float:.3f} (Bajo)"
    except (ValueError, TypeError):
        return "N/A"