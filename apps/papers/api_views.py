"""API views for paper processing and status."""
from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.shortcuts import get_object_or_404
from apps.papers.models import Paper
from apps.subjects.models import Subject


class StartProcessingView(View):
    """Manually trigger processing for a paper or all papers in a subject."""
    
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        paper_id = request.POST.get('paper_id')
        subject_id = request.POST.get('subject_id')
        
        if paper_id:
            # Process single paper SYNCHRONOUSLY (no Django-Q required)
            paper = get_object_or_404(Paper, id=paper_id)
            
            if paper.status == Paper.ProcessingStatus.PROCESSING:
                return JsonResponse({
                    'success': False,
                    'message': 'Paper is already being processed'
                })
            
            # Process IMMEDIATELY (synchronous)
            try:
                from apps.analysis.pipeline import AnalysisPipeline
                
                paper.status = Paper.ProcessingStatus.PROCESSING
                paper.status_detail = 'Starting analysis...'
                paper.progress_percent = 0
                paper.processing_started_at = timezone.now()
                paper.save()
                
                # Run analysis synchronously
                pipeline = AnalysisPipeline(llm_client=None)
                pipeline.analyze_paper(paper)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Processing complete: {paper.title}',
                    'paper_id': str(paper.id)
                })
            except Exception as e:
                paper.status = Paper.ProcessingStatus.FAILED
                paper.processing_error = str(e)
                paper.status_detail = f'Error: {str(e)}'
                paper.save()
                
                return JsonResponse({
                    'success': False,
                    'message': f'Processing failed: {str(e)}'
                })
            
        elif subject_id:
            # Queue all pending papers for processing
            subject = get_object_or_404(Subject, id=subject_id)
            pending_papers = subject.papers.filter(status=Paper.ProcessingStatus.PENDING)
            
            if not pending_papers.exists():
                return JsonResponse({
                    'success': False,
                    'message': 'No pending papers to process'
                })
            
            # Mark all papers as queued with start time
            now = timezone.now()
            for p in pending_papers:
                p.status = Paper.ProcessingStatus.PROCESSING
                p.status_detail = 'Queued for processing...'
                p.progress_percent = 0
                p.processing_started_at = now
                p.save()
            count = pending_papers.count()
            
            # Start background processing in a separate thread
            import threading
            from apps.papers.background_processor import process_subject_papers
            
            thread = threading.Thread(target=process_subject_papers, args=(subject_id,))
            thread.daemon = True
            thread.start()
            
            return JsonResponse({
                'success': True,
                'message': f'Started processing {count} paper(s). Processing will begin shortly.',
                'count': count,
                'processing_started': True
            })
        
        return JsonResponse({
            'success': False,
            'message': 'Missing paper_id or subject_id'
        }, status=400)


class PaperStatusView(View):
    """Get real-time status of paper processing with speed feedback."""

    def get(self, request, paper_id):
        paper = get_object_or_404(Paper, id=paper_id)

        # Calculate elapsed time
        elapsed_seconds = None
        speed_indicator = None
        if paper.processing_started_at and paper.status == Paper.ProcessingStatus.PROCESSING:
            elapsed = (timezone.now() - paper.processing_started_at).total_seconds()
            elapsed_seconds = round(elapsed, 1)
            # Speed indicator based on elapsed time
            if elapsed < 10:
                speed_indicator = 'fast'
            elif elapsed < 30:
                speed_indicator = 'medium'
            else:
                speed_indicator = 'slow'

        # Get timing data from processing log if available
        timings = None
        if paper.processing_log:
            try:
                import json
                log_data = json.loads(paper.processing_log)
                timings = log_data.get('timings')
            except (json.JSONDecodeError, ValueError):
                pass

        return JsonResponse({
            'id': str(paper.id),
            'title': paper.title,
            'status': paper.status,
            'status_detail': paper.status_detail,
            'progress_percent': paper.progress_percent,
            'questions_extracted': paper.questions_extracted,
            'questions_classified': paper.questions_classified,
            'error': paper.processing_error if paper.status == Paper.ProcessingStatus.FAILED else None,
            'elapsed_seconds': elapsed_seconds,
            'speed_indicator': speed_indicator,
            'timings': timings,
        })


class SubjectStatusView(View):
    """Get status of all papers in a subject with speed feedback."""

    def get(self, request, subject_id):
        subject = get_object_or_404(Subject, id=subject_id)
        papers = subject.papers.all()

        papers_data = []
        completed_times = []
        now = timezone.now()

        for paper in papers:
            elapsed_seconds = None
            speed_indicator = None

            if paper.processing_started_at:
                if paper.status == Paper.ProcessingStatus.PROCESSING:
                    elapsed = (now - paper.processing_started_at).total_seconds()
                    elapsed_seconds = round(elapsed, 1)
                    if elapsed < 10:
                        speed_indicator = 'fast'
                    elif elapsed < 30:
                        speed_indicator = 'medium'
                    else:
                        speed_indicator = 'slow'
                elif paper.status == Paper.ProcessingStatus.COMPLETED and paper.processed_at:
                    elapsed = (paper.processed_at - paper.processing_started_at).total_seconds()
                    elapsed_seconds = round(elapsed, 1)
                    completed_times.append(elapsed)

            papers_data.append({
                'id': str(paper.id),
                'title': paper.title,
                'status': paper.status,
                'status_detail': paper.status_detail,
                'progress_percent': paper.progress_percent,
                'questions_extracted': paper.questions_extracted,
                'questions_classified': paper.questions_classified,
                'error': paper.processing_error if paper.status == Paper.ProcessingStatus.FAILED else None,
                'elapsed_seconds': elapsed_seconds,
                'speed_indicator': speed_indicator,
            })

        # Calculate overall stats
        total = papers.count()
        completed = papers.filter(status=Paper.ProcessingStatus.COMPLETED).count()
        processing = papers.filter(status=Paper.ProcessingStatus.PROCESSING).count()
        pending = papers.filter(status=Paper.ProcessingStatus.PENDING).count()
        failed = papers.filter(status=Paper.ProcessingStatus.FAILED).count()

        # Speed stats
        avg_time = round(sum(completed_times) / len(completed_times), 1) if completed_times else None
        papers_per_minute = round(60.0 / avg_time * len(completed_times), 1) if avg_time and avg_time > 0 else None
        est_remaining = None
        if avg_time and processing > 0:
            est_remaining = round(avg_time * processing / 4, 1)  # divide by worker count

        return JsonResponse({
            'subject_id': str(subject.id),
            'subject_name': subject.name,
            'papers': papers_data,
            'stats': {
                'total': total,
                'completed': completed,
                'processing': processing,
                'pending': pending,
                'failed': failed,
            },
            'speed': {
                'avg_completion_time': avg_time,
                'papers_per_minute': papers_per_minute,
                'est_remaining_seconds': est_remaining,
            }
        })
