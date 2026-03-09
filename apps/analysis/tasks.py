"""
Background tasks for paper analysis using threads.
"""
import threading
import logging
from apps.papers.models import Paper
from apps.subjects.models import Subject

logger = logging.getLogger(__name__)


def analyze_paper_task(paper_id: str):
    """Analyze a paper synchronously."""
    from .pipeline import AnalysisPipeline

    try:
        paper = Paper.objects.get(id=paper_id)
        paper.status = Paper.ProcessingStatus.PROCESSING
        paper.save()

        pipeline = AnalysisPipeline()
        pipeline.analyze_paper(paper)

    except Paper.DoesNotExist:
        pass
    except Exception as e:
        try:
            paper.status = Paper.ProcessingStatus.FAILED
            paper.processing_error = str(e)
            paper.save()
        except Exception:
            pass
        logger.error(f"Paper analysis failed: {e}", exc_info=True)


def analyze_subject_topics_task(subject_id: str):
    """Run topic clustering for a subject."""
    from apps.analytics.clustering import TopicClusteringService

    try:
        subject = Subject.objects.get(id=subject_id)
        service = TopicClusteringService(subject)
        return service.analyze_subject()
    except Subject.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Topic analysis failed for subject {subject_id}: {e}")


def queue_paper_analysis(paper: Paper):
    """Queue a paper for background analysis via thread."""
    thread = threading.Thread(
        target=analyze_paper_task,
        args=(str(paper.id),),
        daemon=True,
    )
    thread.start()


def queue_topic_analysis(subject: Subject):
    """Queue topic clustering analysis via thread."""
    thread = threading.Thread(
        target=analyze_subject_topics_task,
        args=(str(subject.id),),
        daemon=True,
    )
    thread.start()
