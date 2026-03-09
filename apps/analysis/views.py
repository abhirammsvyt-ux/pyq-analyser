"""Views for analysis app - includes processing log and manual correction."""
import json
import time
import logging
import traceback
from django.views.generic import DetailView, ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from .models import AnalysisJob
from apps.papers.models import Paper
from apps.subjects.models import Subject, Module
from apps.questions.models import Question
from apps.analysis.gemini_pipeline import (
    check_quota_available,
    should_stop_proactively,
    record_usage,
    DailyQuotaExhaustedError,
)

logger = logging.getLogger(__name__)

# KTU Module Mapping
KTU_MODULE_MAPPING = {
    1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5,
    11: 1, 12: 1, 13: 2, 14: 2, 15: 3, 16: 3, 17: 4, 18: 4, 19: 5, 20: 5,
}


class AnalysisJobListView(LoginRequiredMixin, ListView):
    model = AnalysisJob
    template_name = 'analysis/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 20

    def get_queryset(self):
        return AnalysisJob.objects.filter(
            paper__subject__user=self.request.user
        ).select_related('paper', 'paper__subject').order_by('-created_at')


class AnalysisStatusView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            job = AnalysisJob.objects.get(pk=pk, paper__subject__user=request.user)
            return JsonResponse({
                'status': job.status,
                'progress': job.progress,
                'status_detail': job.status_detail,
                'questions_extracted': job.questions_extracted,
                'questions_classified': job.questions_classified,
                'duplicates_found': job.duplicates_found,
                'error_message': job.error_message,
            })
        except AnalysisJob.DoesNotExist:
            return JsonResponse({'error': 'Job not found'}, status=404)


class AnalysisDetailView(LoginRequiredMixin, DetailView):
    model = AnalysisJob
    template_name = 'analysis/analysis_detail.html'
    context_object_name = 'job'

    def get_queryset(self):
        return AnalysisJob.objects.filter(paper__subject__user=self.request.user)


class ProcessingLogView(DetailView):
    """View processing log for a paper - shows what happened during extraction."""
    model = Paper
    template_name = 'analysis/processing_log.html'
    context_object_name = 'paper'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paper = self.object
        log_data = {}
        if paper.processing_log:
            try:
                log_data = json.loads(paper.processing_log)
            except (json.JSONDecodeError, ValueError):
                log_data = {'raw': paper.processing_log}
        context['log_data'] = log_data
        context['questions'] = paper.questions.all().order_by('question_number')
        return context


class ManualAnalyzeView(View):
    """Manually trigger paper analysis with quota-aware processing."""

    def post(self, request, subject_pk):
        subject = get_object_or_404(Subject, pk=subject_pk)

        pending_papers = list(subject.papers.filter(status='pending'))

        if not pending_papers:
            messages.info(request, 'No papers pending analysis.')
            return redirect('papers:processing_status', subject_pk=subject_pk)

        # Ensure modules exist
        if subject.modules.count() == 0:
            for i in range(1, 6):
                Module.objects.create(
                    subject=subject, name=f'Module {i}',
                    number=i, weightage=20
                )

        processed = 0
        failed = 0
        queued = 0
        total_questions = 0
        errors = []

        for i, paper in enumerate(pending_papers):
            # Check quota before each paper
            if should_stop_proactively():
                for p in pending_papers[i:]:
                    p.status_detail = (
                        'Queued - daily API quota approaching limit. '
                        'Will retry tomorrow or add new API keys.'
                    )
                    p.save()
                    queued += 1
                break

            try:
                paper.status = Paper.ProcessingStatus.PROCESSING
                paper.status_detail = 'Starting analysis...'
                paper.progress_percent = 0
                paper.save()

                from .pipeline import AnalysisPipeline
                pipeline = AnalysisPipeline()
                pipeline.analyze_paper(paper)

                total_questions += paper.questions.count()
                processed += 1

                # Record estimated usage
                record_usage(0, 5000)

                # 1-second gap between papers (reduced from 5s)
                if i < len(pending_papers) - 1:
                    time.sleep(1)

            except DailyQuotaExhaustedError as e:
                paper.status = Paper.ProcessingStatus.PENDING
                paper.status_detail = (
                    'Queued - daily API quota exhausted. '
                    'Try again after midnight Pacific Time.'
                )
                paper.save()
                queued += 1

                # Queue remaining papers
                for p in pending_papers[i+1:]:
                    p.status_detail = (
                        'Queued - daily API quota exhausted. '
                        'Try again after midnight Pacific Time.'
                    )
                    p.save()
                    queued += 1
                break

            except ImportError as e:
                module_name = str(e).replace("No module named ", "").strip("'\"")
                error_msg = (
                    f"Missing Python package: {module_name}. "
                    f"Install it with: pip install {module_name}"
                )
                paper.status = Paper.ProcessingStatus.FAILED
                paper.processing_error = error_msg
                paper.status_detail = f'Error: {error_msg[:200]}'
                paper.save()
                failed += 1
                errors.append(error_msg[:100])
                logger.error(f"Paper analysis failed (ImportError): {e}", exc_info=True)
            except Exception as e:
                tb_str = traceback.format_exc()
                error_msg = str(e)[:500]
                paper.status = Paper.ProcessingStatus.FAILED
                paper.processing_error = error_msg
                paper.status_detail = f'Error: {error_msg[:200]}'
                paper.save()
                failed += 1
                errors.append(str(e)[:100])
                logger.error(f"Paper analysis failed: {e}\n{tb_str}")

        # Run clustering after all papers
        if processed > 0:
            try:
                from apps.analytics.clustering import TopicClusteringService
                clustering = TopicClusteringService(subject)
                clustering.analyze_subject()
                msg = f'Analyzed {processed} paper(s). Extracted {total_questions} questions.'
                if queued > 0:
                    msg += f' {queued} paper(s) queued for tomorrow (daily quota reached).'
                messages.success(request, msg)
            except Exception as e:
                messages.success(request, f'Analyzed {processed} paper(s). Extracted {total_questions} questions.')
                messages.warning(request, f'Topic clustering issue: {str(e)[:100]}')
        elif queued > 0:
            messages.warning(
                request,
                f'Daily API quota exhausted. {queued} paper(s) queued for tomorrow. '
                f'Try again after midnight Pacific Time or add new API keys.'
            )

        if failed > 0:
            messages.error(request, f'{failed} paper(s) failed: {"; ".join(errors[:2])}')

        return redirect('papers:processing_status', subject_pk=subject_pk)


class ResetAndAnalyzeView(View):
    """Reset all papers to pending and re-run analysis."""

    def post(self, request, subject_pk):
        subject = get_object_or_404(Subject, pk=subject_pk)

        Question.objects.filter(paper__subject=subject).delete()

        from apps.analytics.models import TopicCluster
        TopicCluster.objects.filter(subject=subject).delete()

        papers = subject.papers.all()
        papers.update(
            status='pending', processing_error='',
            processing_log='', correction_count=0,
            progress_percent=0, status_detail='Reset - ready for reprocessing'
        )

        messages.info(request, f'Reset {papers.count()} paper(s). Click "Start Processing" to re-analyze.')
        return redirect('papers:processing_status', subject_pk=subject_pk)
