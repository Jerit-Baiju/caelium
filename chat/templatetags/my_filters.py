import os

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter()
def js_var(data, var_name):
    if isinstance(data, bool):
        return mark_safe(f"var {var_name} = {str(data).lower()}")
    return mark_safe(f"var {var_name} = '{data}'")

@register.filter()
def env(key):
    return os.environ[key]
