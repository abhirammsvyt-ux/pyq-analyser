from django.contrib import admin
from .models import Subject, Module, ExamPattern


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'user', 'university', 'created_at')
    list_filter = ('university', 'created_at')
    search_fields = ('name', 'code', 'user__email')
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'number', 'subject', 'weightage')
    list_filter = ('subject',)
    search_fields = ('name', 'subject__name')


@admin.register(ExamPattern)
class ExamPatternAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'part_a_marks', 'part_b_marks')
    list_filter = ('subject',)
    search_fields = ('name', 'subject__name')
