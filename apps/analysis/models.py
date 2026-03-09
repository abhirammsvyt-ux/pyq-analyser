"""Analysis models - stores analysis job state and API quota tracking."""
from django.db import models
from apps.core.models import BaseModel


class AnalysisJob(BaseModel):
    """Tracks analysis job status."""

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        EXTRACTING = 'extracting', 'Extracting Questions'
        CLASSIFYING = 'classifying', 'Classifying'
        ANALYZING = 'analyzing', 'Analyzing'
        EMBEDDING = 'embedding', 'Generating Embeddings'
        DETECTING = 'detecting', 'Detecting Duplicates'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    paper = models.ForeignKey(
        'papers.Paper',
        on_delete=models.CASCADE,
        related_name='analysis_jobs'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED
    )
    progress = models.PositiveIntegerField(default=0)  # 0-100
    status_detail = models.CharField(max_length=255, blank=True, default='')  # Detailed status message
    error_message = models.TextField(blank=True)

    # Statistics
    questions_extracted = models.PositiveIntegerField(default=0)
    questions_classified = models.PositiveIntegerField(default=0)
    duplicates_found = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Analysis Job'
        verbose_name_plural = 'Analysis Jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Analysis: {self.paper.title} ({self.get_status_display()})"


class APIQuotaTracker(models.Model):
    """Tracks daily API usage per Gemini key for quota management."""
    key_index = models.IntegerField(help_text="Index in GEMINI_API_KEYS list")
    date = models.DateField(help_text="Tracking date")
    tokens_used = models.IntegerField(default=0)
    requests_made = models.IntegerField(default=0)
    is_exhausted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('key_index', 'date')
        verbose_name = 'API Quota Tracker'
        verbose_name_plural = 'API Quota Trackers'

    def __str__(self):
        return f"Key {self.key_index} on {self.date}: {self.tokens_used} tokens, exhausted={self.is_exhausted}"
