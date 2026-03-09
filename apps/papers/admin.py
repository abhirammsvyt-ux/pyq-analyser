from django.contrib import admin
from .models import Paper, PaperPage


class PaperPageInline(admin.TabularInline):
    model = PaperPage
    extra = 0
    readonly_fields = ('page_number',)


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'year', 'status', 'created_at')
    list_filter = ('status', 'subject', 'year')
    search_fields = ('title', 'subject__name')
    inlines = [PaperPageInline]
