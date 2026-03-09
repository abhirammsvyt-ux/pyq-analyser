"""Views for question management including manual correction."""
from django.views.generic import ListView, DetailView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse

from .models import Question
from .forms import QuestionEditForm, QuestionTextEditForm
import csv


class QuestionListView(ListView):
    """List all questions for a paper or subject."""
    model = Question
    template_name = 'questions/question_list.html'
    context_object_name = 'questions'

    def get_queryset(self):
        qs = Question.objects.all().select_related('paper', 'module', 'paper__subject')

        paper_id = self.request.GET.get('paper')
        if paper_id:
            qs = qs.filter(paper_id=paper_id)

        subject_id = self.request.GET.get('subject')
        if subject_id:
            qs = qs.filter(paper__subject_id=subject_id)

        return qs.order_by('question_number')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paper_id = self.request.GET.get('paper')
        subject_id = self.request.GET.get('subject')
        if paper_id:
            from apps.papers.models import Paper
            context['paper'] = Paper.objects.filter(id=paper_id).first()
        if subject_id:
            from apps.subjects.models import Subject
            context['subject'] = Subject.objects.filter(id=subject_id).first()
        return context


class QuestionDetailView(DetailView):
    model = Question
    template_name = 'questions/question_detail.html'
    context_object_name = 'question'

    def get_queryset(self):
        return Question.objects.all().select_related('paper', 'module', 'duplicate_of')


class QuestionUpdateView(UpdateView):
    """Update question classification (module, difficulty, marks)."""
    model = Question
    form_class = QuestionEditForm
    template_name = 'questions/question_edit.html'

    def get_success_url(self):
        return reverse('questions:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        if 'module' in form.changed_data:
            form.instance.module_manually_set = True
        if 'difficulty' in form.changed_data:
            form.instance.difficulty_manually_set = True
        messages.success(self.request, 'Question updated successfully!')
        return super().form_valid(form)


class ManualCorrectionView(UpdateView):
    """Manual correction interface for editing extracted question text."""
    model = Question
    form_class = QuestionTextEditForm
    template_name = 'questions/manual_correction.html'

    def get_success_url(self):
        return reverse('questions:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        form.instance.needs_review = False  # Clear review flag after manual edit
        messages.success(self.request, 'Question text corrected successfully!')
        return super().form_valid(form)


class QuestionVerifyView(View):
    def post(self, request, pk):
        question = get_object_or_404(Question, pk=pk)
        question.module_manually_set = True
        question.needs_review = False
        question.save()
        messages.success(request, 'Question verified successfully!')
        return redirect('questions:detail', pk=pk)


class QuestionExportView(View):
    def get(self, request):
        paper_id = request.GET.get('paper')
        subject_id = request.GET.get('subject')

        qs = Question.objects.all().select_related('paper', 'module')

        if paper_id:
            qs = qs.filter(paper_id=paper_id)
        if subject_id:
            qs = qs.filter(paper__subject_id=subject_id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="questions_export.csv"'

        writer = csv.writer(response)
        writer.writerow(['Q#', 'Sub', 'Part', 'Text', 'Marks', 'Module', 'Paper', 'Year', 'Needs Review'])

        for q in qs:
            writer.writerow([
                q.question_number,
                q.sub_part,
                q.part,
                q.text[:500],
                q.marks,
                q.module.name if q.module else '',
                q.paper.title,
                q.paper.year,
                q.needs_review,
            ])

        return response
