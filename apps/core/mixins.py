"""
View mixins for common functionality across views.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View


class OwnerRequiredMixin(LoginRequiredMixin):
    """Mixin that ensures the user is the owner of the object."""
    
    owner_field = 'user'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.owner_field: self.request.user})


class HTMXResponseMixin:
    """Mixin for handling HTMX requests."""
    
    def is_htmx_request(self):
        return self.request.headers.get('HX-Request') == 'true'
    
    def get_template_names(self):
        if self.is_htmx_request() and hasattr(self, 'htmx_template_name'):
            return [self.htmx_template_name]
        return super().get_template_names()
