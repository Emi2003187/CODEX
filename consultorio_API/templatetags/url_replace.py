from django import template

register = template.Library()

@register.simple_tag
def url_replace(request, field, value):
    query = request.GET.copy()
    query[field] = value
    return query.urlencode()
