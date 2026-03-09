"""
Admin configuration for analytics app.
"""
from django.contrib import admin
from .models import TopicCluster


@admin.register(TopicCluster)
class TopicClusterAdmin(admin.ModelAdmin):
    list_display = ('topic_name', 'subject', 'module', 'priority_tier', 'frequency_count', 'total_marks')
    list_filter = ('priority_tier', 'subject', 'module')
    search_fields = ('topic_name', 'subject__name', 'module__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('subject', 'module', 'topic_name', 'normalized_key')
        }),
        ('Statistics', {
            'fields': ('frequency_count', 'years_appeared', 'total_marks', 'priority_tier')
        }),
        ('Part Distribution', {
            'fields': ('part_a_count', 'part_b_count')
        }),
        ('Representative Text', {
            'fields': ('representative_text',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
