"""
Global template context processors.
"""
from django.conf import settings


def global_context(request):
    """Add global context variables to all templates."""
    return {
        'APP_NAME': 'PYQ Analyzer',
        'APP_VERSION': '1.0.0',
        'DEBUG': settings.DEBUG,
    }
