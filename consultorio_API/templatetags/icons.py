from django import template
from django.utils.html import format_html
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def icon(name, size=20, css_class="icon"):
    src = static(f"icons/bootstrap/{name}.svg")
    return format_html('<img src="{}" width="{}" height="{}" class="{}" alt="{} icon">', src, size, size, css_class, name)
