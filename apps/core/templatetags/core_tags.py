"""
Custom template tags for the PYQ Analyzer.
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def icon(name, size=20, classes=''):
    """Render a Lucide icon."""
    return mark_safe(f'<i data-lucide="{name}" class="w-{size//4} h-{size//4} {classes}"></i>')


@register.filter
def percentage(value, total):
    """Calculate percentage."""
    if total == 0:
        return 0
    return round((value / total) * 100, 1)


@register.filter
def truncate_chars(value, max_length):
    """Truncate a string to max_length characters."""
    if len(str(value)) <= max_length:
        return value
    return str(value)[:max_length - 3] + '...'
