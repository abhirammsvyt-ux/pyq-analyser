"""Background paper processing with parallel execution and quota-aware batch control."""
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import django
from django.db import close_old_connections

from apps.papers.models import Paper
from apps.subjects.models import Subject
from apps.analysis.pipeline import AnalysisPipeline
from apps.analysis.gemini_pipeline import (
    check_quota_available,
    should_stop_proactively,
    record_usage,
    DailyQuotaExhaustedError,
)

logger = logging.getLogger(__name__)

# 1-second gap between sequential API calls (reduced from 5s)
INTER_PAPER_DELAY = 1

# Rough estimate: ~5000 tokens per paper (text) or ~2000 per page (image)
ESTIMATED_TOKENS_PER_PAPER = 5000

# Max parallel workers for paper processing
MAX_WORKERS = 4


def _process_single_paper(paper_id: int) -> dict:
    """Process a single paper in a worker thread.

    Closes old DB connections at thread start to prevent cross-thread issues.
    Returns a result dict with status and details.
    """
    close_old_connections()

    result = {
        'paper_id': paper_id,
        'status': 'failed',
        'error': None,
    }

    try:
        paper = Paper.objects.get(id=paper_id)
        logger.info(f"[Worker] Processing paper: {paper.title} (id={paper_id})")

        pipeline = AnalysisPipeline()
        pipeline.analyze_paper(paper)

        # Record estimated usage
        record_usage(0, ESTIMATED_TOKENS_PER_PAPER)

        result['status'] = 'completed'
        result['title'] = paper.title
        logger.info(f"[Worker] Completed: {paper.title}")

    except DailyQuotaExhaustedError as e:
        logger.warning(f"[Worker] Daily quota exhausted for paper {paper_id}: {e}")
        try:
            paper = Paper.objects.get(id=paper_id)
            paper.status = Paper.ProcessingStatus.PENDING
            paper.status_detail = (
                'Queued - daily API quota exhausted. '
                'Try again after midnight Pacific Time.'
            )
            paper.save()
        except Exception:
            pass
        result['status'] = 'quota_exhausted'
        result['error'] = str(e)

    except Exception as e:
        logger.error(f"[Worker] Failed to process paper {paper_id}: {e}", exc_info=True)
        try:
            paper = Paper.objects.get(id=paper_id)
            paper.status = Paper.ProcessingStatus.FAILED
            paper.processing_error = str(e)[:500]
            paper.status_detail = f'Error: {str(e)[:200]}'
            paper.save()
        except Exception:
            pass
        result['status'] = 'failed'
        result['error'] = str(e)

    return result


def process_subject_papers(subject_id):
    """Process all pending papers for a subject with parallel execution.

    - Uses ThreadPoolExecutor with MAX_WORKERS (4) for parallel processing
    - Checks quota before submitting each batch
    - Each worker handles its own paper independently
    - Frontend polling picks up completions in real-time
    """
    try:
        subject = Subject.objects.get(id=subject_id)
        papers = list(subject.papers.filter(status=Paper.ProcessingStatus.PROCESSING))

        if not papers:
            logger.info(f"No papers to process for subject {subject_id}")
            return

        processed_count = 0
        queued_count = 0
        failed_count = 0

        # Pre-check: quota availability before submitting anything
        if should_stop_proactively():
            for p in papers:
                p.status = Paper.ProcessingStatus.PENDING
                p.status_detail = (
                    'Queued - daily API quota approaching limit. '
                    'Will retry tomorrow or add new API keys.'
                )
                p.save()
            logger.warning(
                f"Proactive stop: {len(papers)} papers queued. "
                f"Daily quota approaching 90% on all keys."
            )
            return

        if not check_quota_available():
            for p in papers:
                p.status = Paper.ProcessingStatus.PENDING
                p.status_detail = (
                    'Queued - daily API quota exhausted. '
                    'Try again after midnight Pacific Time or add new API keys.'
                )
                p.save()
            logger.warning(
                f"Quota exhausted: {len(papers)} papers queued for tomorrow."
            )
            return

        # Submit all papers to thread pool for parallel processing
        paper_ids = [p.id for p in papers]
        logger.info(
            f"Starting parallel processing: {len(paper_ids)} papers "
            f"with {min(MAX_WORKERS, len(paper_ids))} workers"
        )

        batch_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(paper_ids))) as executor:
            future_to_id = {
                executor.submit(_process_single_paper, pid): pid
                for pid in paper_ids
            }

            for future in as_completed(future_to_id):
                paper_id = future_to_id[future]
                try:
                    result = future.result()
                    if result['status'] == 'completed':
                        processed_count += 1
                    elif result['status'] == 'quota_exhausted':
                        queued_count += 1
                        # Cancel remaining futures is not easily possible,
                        # but subsequent workers will hit the same quota check
                    else:
                        failed_count += 1
                except Exception as exc:
                    logger.error(f"Paper {paper_id} generated exception: {exc}")
                    failed_count += 1

        batch_elapsed = round(time.perf_counter() - batch_start, 2)
        logger.info(
            f"Batch processing complete for subject {subject_id}: "
            f"{processed_count} processed, {queued_count} queued, {failed_count} failed "
            f"in {batch_elapsed}s"
        )

    except Subject.DoesNotExist:
        logger.error(f"Subject {subject_id} not found")
    except Exception as e:
        logger.error(f"Background processing failed: {e}", exc_info=True)
