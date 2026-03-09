from django.contrib import admin
from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_number', 'paper', 'module', 'difficulty', 'bloom_level', 'is_duplicate')
    list_filter = ('difficulty', 'bloom_level', 'is_duplicate', 'module')
    search_fields = ('text', 'paper__title')
