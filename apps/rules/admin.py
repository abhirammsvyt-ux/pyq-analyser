from django.contrib import admin
from .models import ClassificationRule


@admin.register(ClassificationRule)
class ClassificationRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'rule_type', 'is_active', 'is_validated', 'priority')
    list_filter = ('rule_type', 'is_active', 'is_validated')
    search_fields = ('name', 'natural_language')
