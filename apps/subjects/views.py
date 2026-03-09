"""
Views for subject and module management.
"""
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404

from apps.core.mixins import OwnerRequiredMixin, HTMXResponseMixin
from .models import Subject, Module
from .forms import SubjectForm, ModuleForm


class SubjectListView(LoginRequiredMixin, ListView):
    """List all subjects for the current user."""
    
    model = Subject
    template_name = 'subjects/subject_list.html'
    context_object_name = 'subjects'
    
    def get_queryset(self):
        return Subject.objects.filter(user=self.request.user).prefetch_related('modules')


class SubjectDetailView(OwnerRequiredMixin, DetailView):
    """View subject details with modules."""
    
    model = Subject
    template_name = 'subjects/subject_detail.html'
    context_object_name = 'subject'
    
    def get_queryset(self):
        return Subject.objects.filter(user=self.request.user).prefetch_related('modules')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get paper processing status counts
        papers = self.object.papers.all()
        context['papers_pending'] = papers.filter(status='pending').count()
        context['papers_processing'] = papers.filter(status='processing').count()
        context['papers_completed'] = papers.filter(status='completed').count()
        context['papers_failed'] = papers.filter(status='failed').count()
        context['papers_total'] = papers.count()
        context['questions_count'] = sum(p.get_question_count() for p in papers)
        # Check if any papers are being processed
        context['has_processing'] = context['papers_pending'] > 0 or context['papers_processing'] > 0
        return context


class SubjectCreateView(LoginRequiredMixin, CreateView):
    """Create a new subject."""
    
    model = Subject
    form_class = SubjectForm
    template_name = 'subjects/subject_form.html'
    
    def get_success_url(self):
        return reverse_lazy('subjects:detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, f'Subject "{form.instance.name}" created successfully!')
        return super().form_valid(form)


class SubjectUpdateView(OwnerRequiredMixin, UpdateView):
    """Update an existing subject."""
    
    model = Subject
    form_class = SubjectForm
    template_name = 'subjects/subject_form.html'
    
    def get_queryset(self):
        return Subject.objects.filter(user=self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('subjects:detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'Subject "{form.instance.name}" updated successfully!')
        return super().form_valid(form)


class SubjectDeleteView(OwnerRequiredMixin, DeleteView):
    """Delete a subject (soft delete)."""
    
    model = Subject
    template_name = 'subjects/subject_confirm_delete.html'
    success_url = reverse_lazy('subjects:list')
    
    def get_queryset(self):
        return Subject.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        self.object.soft_delete()
        messages.success(self.request, f'Subject "{self.object.name}" deleted.')
        return super().form_valid(form)


# Module Views

class ModuleCreateView(LoginRequiredMixin, CreateView):
    """Create a new module for a subject."""
    
    model = Module
    form_class = ModuleForm
    template_name = 'subjects/module_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.subject = get_object_or_404(
            Subject, pk=kwargs['subject_pk'], user=request.user
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subject'] = self.subject
        return context
    
    def get_success_url(self):
        return reverse_lazy('subjects:detail', kwargs={'pk': self.subject.pk})
    
    def form_valid(self, form):
        form.instance.subject = self.subject
        messages.success(self.request, f'Module "{form.instance.name}" added!')
        return super().form_valid(form)


class ModuleUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing module."""
    
    model = Module
    form_class = ModuleForm
    template_name = 'subjects/module_form.html'
    
    def get_queryset(self):
        return Module.objects.filter(subject__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subject'] = self.object.subject
        return context
    
    def get_success_url(self):
        return reverse_lazy('subjects:detail', kwargs={'pk': self.object.subject.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'Module "{form.instance.name}" updated!')
        return super().form_valid(form)


class ModuleDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a module."""
    
    model = Module
    template_name = 'subjects/module_confirm_delete.html'
    
    def get_queryset(self):
        return Module.objects.filter(subject__user=self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('subjects:detail', kwargs={'pk': self.object.subject.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'Module "{self.object.name}" deleted.')
        return super().form_valid(form)
