"""Views for rule management."""
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404

from apps.subjects.models import Subject
from .models import ClassificationRule
from .forms import RuleForm


class RuleListView(LoginRequiredMixin, ListView):
    """List rules for a subject."""
    
    model = ClassificationRule
    template_name = 'rules/rule_list.html'
    context_object_name = 'rules'
    
    def get_queryset(self):
        self.subject = get_object_or_404(
            Subject, pk=self.kwargs['subject_pk'], user=self.request.user
        )
        return ClassificationRule.objects.filter(subject=self.subject)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subject'] = self.subject
        return context


class RuleCreateView(LoginRequiredMixin, CreateView):
    """Create a new classification rule."""
    
    model = ClassificationRule
    form_class = RuleForm
    template_name = 'rules/rule_form.html'
    
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
        return reverse_lazy('rules:list', kwargs={'subject_pk': self.subject.pk})
    
    def form_valid(self, form):
        form.instance.subject = self.subject
        messages.success(self.request, f'Rule "{form.instance.name}" created!')
        return super().form_valid(form)


class RuleUpdateView(LoginRequiredMixin, UpdateView):
    """Update a classification rule."""
    
    model = ClassificationRule
    form_class = RuleForm
    template_name = 'rules/rule_form.html'
    
    def get_queryset(self):
        return ClassificationRule.objects.filter(subject__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subject'] = self.object.subject
        return context
    
    def get_success_url(self):
        return reverse_lazy('rules:list', kwargs={'subject_pk': self.object.subject.pk})
    
    def form_valid(self, form):
        # Reset validation when rule is updated
        form.instance.is_validated = False
        form.instance.compiled_code = ''
        messages.success(self.request, f'Rule "{form.instance.name}" updated!')
        return super().form_valid(form)


class RuleDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a classification rule."""
    
    model = ClassificationRule
    template_name = 'rules/rule_confirm_delete.html'
    
    def get_queryset(self):
        return ClassificationRule.objects.filter(subject__user=self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('rules:list', kwargs={'subject_pk': self.object.subject.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'Rule "{self.object.name}" deleted.')
        return super().form_valid(form)
