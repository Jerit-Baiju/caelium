from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter()
def js_var(data, var_name):
    return mark_safe(f"const {var_name} = '{data}'")
    