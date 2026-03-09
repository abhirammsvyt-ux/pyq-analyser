from django.contrib import admin
from .models import AnalysisJob


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = ('paper', 'status', 'progress', 'questions_extracted', 'created_at')
    list_filter = ('status',)
    search_fields = ('paper__title',)
