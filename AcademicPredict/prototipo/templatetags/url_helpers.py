# prototipo/templatetags/url_helpers.py
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag
def url_params(request, param_name, param_value):
    """
    Construye una URL manteniendo los parámetros GET existentes
    y actualiza/agrega el parámetro especificado.
    
    Uso en template:
    {% url_params request 'page' 2 %}
    """
    params = request.GET.copy()
    params[param_name] = param_value
    return urlencode(params)

@register.simple_tag
def url_params_exclude(request, *exclude_params):
    """
    Construye una URL manteniendo todos los parámetros GET 
    excepto los especificados.
    
    Uso en template:
    {% url_params_exclude request 'page' 'sort' %}
    """
    params = request.GET.copy()
    for param in exclude_params:
        params.pop(param, None)
    return urlencode(params)

@register.filter
def get_item(dictionary, key):
    """
    Obtiene un item de un diccionario.
    
    Uso en template:
    {{ mydict|get_item:key }}
    """
    return dictionary.get(key)

@register.filter
def split(value, separator):
    """
    Divide una cadena por el separador especificado.
    
    Uso en template:
    {{ "Juan Carlos Pérez"|split:" " }}
    """
    try:
        return str(value).split(separator)
    except (AttributeError, TypeError):
        return []

@register.filter
def initials(full_name):
    """
    Genera iniciales de un nombre completo.
    
    Uso en template:
    {{ "Juan Carlos Pérez"|initials }}  → "JP"
    """
    try:
        if not full_name:
            return "??"
        
        # Limpiar y dividir el nombre
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
    Genera un color de fondo basado en el nombre.
    
    Uso en template:
    {{ "Juan Pérez"|avatar_color }}
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

@register.filter
def mul(value, arg):
    """
    Multiplica el valor por el argumento.
    
    Uso en template:
    {{ 0.75|mul:100 }}  → 75.0
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """
    Divide value por arg.
    
    Uso en template:
    {{ 100|div:4 }}  → 25.0
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
    Resta arg de value.
    
    Uso en template:
    {{ 100|subtract:25 }}  → 75
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """
    Calcula el porcentaje de value respecto a total.
    
    Uso en template:
    {{ 25|percentage:100 }}  → 25.0
    """
    try:
        if total == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0

@register.filter
def progress_width(value, max_value=7.0):
    """
    Calcula el ancho de progress bar para escala de notas.
    
    Uso en template:
    {{ 5.5|progress_width }}  → 78.57 (para escala 1-7)
    """
    try:
        return (float(value) / float(max_value)) * 100
    except (ValueError, TypeError):
        return 0

@register.simple_tag
def query_params(**kwargs):
    """
    Construye parámetros de query string desde kwargs.
    
    Uso en template:
    {% query_params page=2 estado='activo' %}
    """
    return urlencode(kwargs)