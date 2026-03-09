"""
Paper models for uploaded question papers.
"""
from django.db import models
from django.conf import settings
from apps.core.models import SoftDeleteModel


class Paper(SoftDeleteModel):
    """Uploaded question paper model."""

    class ProcessingStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='papers'
    )

    title = models.CharField(max_length=255)
    year = models.CharField(max_length=50, blank=True)
    exam_type = models.CharField(max_length=100, blank=True)

    file = models.FileField(upload_to='papers/')
    file_hash = models.CharField(max_length=64, blank=True)
    page_count = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING
    )
    processing_error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    status_detail = models.CharField(max_length=255, blank=True)
    questions_extracted = models.PositiveIntegerField(default=0)
    questions_classified = models.PositiveIntegerField(default=0)
    progress_percent = models.PositiveIntegerField(default=0)
    processing_started_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Timestamp when processing started (for speed tracking)'
    )

    raw_text = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # New fields for Gemini pipeline
    correction_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of module corrections applied by the validator'
    )
    processing_log = models.TextField(
        blank=True,
        help_text='Detailed processing log as JSON string'
    )

    # Gemini-extracted metadata
    detected_subject_code = models.CharField(max_length=50, blank=True)
    detected_subject_name = models.CharField(max_length=255, blank=True)
    detected_exam_year = models.PositiveIntegerField(null=True, blank=True)
    detected_exam_month = models.CharField(max_length=50, blank=True)

    # Extraction quality score (0-110, shown as percentage)
    extraction_quality_score = models.PositiveIntegerField(
        default=0,
        help_text='Quality score from extraction (0-110). Below 60 means needs review.'
    )

    class Meta:
        verbose_name = 'Paper'
        verbose_name_plural = 'Papers'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.year})" if self.year else self.title

    def get_question_count(self):
        return self.questions.count() if hasattr(self, 'questions') else 0


class PaperPage(models.Model):
    """Individual page from a paper."""

    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name='pages'
    )
    page_number = models.PositiveIntegerField()
    text_content = models.TextField(blank=True)
    image = models.ImageField(upload_to='paper_pages/', null=True, blank=True)

    class Meta:
        ordering = ['page_number']
        unique_together = ['paper', 'page_number']

    def __str__(self):
        return f"Page {self.page_number} of {self.paper.title}"
