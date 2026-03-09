"""
Analysis pipeline using Gemini API for KTU question paper extraction.
Replaces the old Tesseract/pdfplumber pipeline entirely.
All PDF reading is done exclusively through Gemini Vision API.
"""
import json
import logging
from django.utils import timezone

from apps.papers.models import Paper
from apps.questions.models import Question
from apps.analytics.clustering import TopicClusteringService
from .models import AnalysisJob
from .gemini_pipeline import process_paper, get_module_for_question

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """Orchestrates paper analysis using Gemini API exclusively."""

    def __init__(self, llm_client=None):
        pass  # No external clients needed; Gemini pipeline is self-contained

    def analyze_paper(self, paper: Paper) -> AnalysisJob:
        """Run complete analysis on a paper using Gemini pipeline."""
        job = AnalysisJob.objects.create(paper=paper)
        job.started_at = timezone.now()
        job.save()

        try:
            subject = paper.subject
            modules = {m.number: m for m in subject.modules.all()}

            # Step 1: Run Gemini pipeline
            job.status = AnalysisJob.Status.EXTRACTING
            job.progress = 5
            job.status_detail = 'Detecting PDF type...'
            job.save()

            paper.status = Paper.ProcessingStatus.PROCESSING
            paper.status_detail = 'Analyzing PDF with Gemini...'
            paper.progress_percent = 5
            paper.save()

            validated_data, processing_log = process_paper(
                paper.file.path, paper_id=str(paper.id)
            )

            # Store processing log
            paper.processing_log = json.dumps(processing_log, indent=2)
            paper.correction_count = processing_log.get('correction_count', 0)
            paper.page_count = processing_log.get('page_count', 0)

            # Store quality score
            quality_score = processing_log.get('quality_score', 0)
            paper.extraction_quality_score = quality_score

            # Store Gemini-detected metadata
            paper.detected_subject_code = validated_data.get('subject_code', '')
            paper.detected_subject_name = validated_data.get('subject_name', '')
            paper.detected_exam_year = validated_data.get('exam_year')
            paper.detected_exam_month = validated_data.get('exam_month', '')

            # Update year/exam_type if not already set
            if not paper.year and validated_data.get('exam_year'):
                paper.year = str(validated_data['exam_year'])
            if not paper.exam_type and validated_data.get('exam_month'):
                month = validated_data.get('exam_month', '')
                year_val = validated_data.get('exam_year', '')
                paper.exam_type = f"{month} {year_val}".strip()

            paper.progress_percent = 30
            paper.status_detail = f"Extracted {len(validated_data.get('questions', []))} questions"
            paper.save()

            questions_data = validated_data.get('questions', [])
            if not questions_data:
                raise Exception("No questions extracted from PDF by Gemini")

            job.questions_extracted = len(questions_data)
            job.progress = 40
            job.status = AnalysisJob.Status.CLASSIFYING
            job.status_detail = f'Saving {len(questions_data)} questions...'
            job.save()

            # Step 2: Delete existing questions for this paper (for reprocessing)
            Question.objects.filter(paper=paper).delete()

            # Step 3: Build Question objects for bulk_create
            question_objects = []
            skipped_count = 0
            for q_data in questions_data:
                q_number = q_data.get('q_number', 0)
                text = q_data.get('text', '')
                sub = q_data.get('sub', '')
                marks = q_data.get('marks', 0)
                part = q_data.get('part', '')
                needs_review = q_data.get('needs_review', False)

                # === UNIVERSAL SAVE GUARD ===
                # Guard 1: text must not be empty
                if not text or not str(text).strip():
                    logger.warning(
                        f"SAVE GUARD: Skipping Q{q_number} - empty text "
                        f"(paper={paper.id})"
                    )
                    skipped_count += 1
                    continue

                text = str(text).strip()

                # Guard 2: q_number must be 1-20
                if not (1 <= q_number <= 20):
                    logger.warning(
                        f"SAVE GUARD: Skipping question with q_number={q_number} "
                        f"(paper={paper.id})"
                    )
                    skipped_count += 1
                    continue

                # Guard 3: recompute module from q_number
                module_num = get_module_for_question(q_number)
                module = modules.get(module_num)

                # Guard 4: ensure marks is positive
                if not marks or marks <= 0:
                    if part == 'A' or (1 <= q_number <= 10):
                        marks = 3
                    elif sub == 'a':
                        marks = 8
                    elif sub == 'b':
                        marks = 6
                    else:
                        marks = 14

                # Guard 5: ensure part is A or B
                if part not in ('A', 'B'):
                    part = 'A' if 1 <= q_number <= 10 else 'B'

                # Guard 6: normalize sub
                if sub is None:
                    sub = ''

                question_objects.append(Question(
                    paper=paper,
                    question_number=str(q_number),
                    text=text,
                    marks=marks,
                    part=part,
                    sub_part=sub,
                    module=module,
                    needs_review=needs_review,
                ))

            if skipped_count > 0:
                logger.warning(
                    f"Save guards skipped {skipped_count} invalid questions "
                    f"for paper {paper.id}"
                )

            # Bulk create all questions in one DB operation (15-20x faster)
            created_questions = Question.objects.bulk_create(
                question_objects, ignore_conflicts=True
            )

            paper.questions_extracted = len(created_questions)
            paper.questions_classified = len(created_questions)
            paper.progress_percent = 70
            paper.status_detail = f'Saved {len(created_questions)} questions, building clusters...'
            paper.save()

            job.questions_classified = len(created_questions)
            job.progress = 70
            job.status = AnalysisJob.Status.ANALYZING
            job.status_detail = 'Building topic clusters...'
            job.save()

            # Step 4: Run topic clustering
            try:
                clustering_service = TopicClusteringService(subject)
                clustering_service.analyze_subject()
            except Exception as e:
                logger.error(f"Topic clustering failed: {e}", exc_info=True)

            # Step 5: Mark complete (or needs_review based on quality)
            if processing_log.get('needs_review'):
                paper.status = Paper.ProcessingStatus.COMPLETED
                paper.status_detail = (
                    f'Completed with low quality score ({quality_score}%). '
                    f'Manual review recommended.'
                )
            else:
                paper.status = Paper.ProcessingStatus.COMPLETED
                paper.status_detail = 'Analysis completed successfully'

            paper.processed_at = timezone.now()
            paper.progress_percent = 100
            paper.save()

            job.status = AnalysisJob.Status.COMPLETED
            job.progress = 100
            job.status_detail = 'Analysis completed successfully'
            job.completed_at = timezone.now()
            job.save()

            logger.info(f"Analysis completed: {len(created_questions)} questions created")
            return job

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)

            job.status = AnalysisJob.Status.FAILED
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save()

            paper.status = Paper.ProcessingStatus.FAILED
            paper.processing_error = str(e)
            paper.status_detail = f'Error: {str(e)[:200]}'
            paper.save()

            raise
