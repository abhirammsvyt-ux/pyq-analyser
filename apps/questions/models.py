"""
Question models with full analysis fields.
"""
from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel


class Question(BaseModel):
    """Extracted question with all analysis fields."""

    class DifficultyLevel(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    class BloomLevel(models.TextChoices):
        REMEMBER = 'remember', 'Remember'
        UNDERSTAND = 'understand', 'Understand'
        APPLY = 'apply', 'Apply'
        ANALYZE = 'analyze', 'Analyze'
        EVALUATE = 'evaluate', 'Evaluate'
        CREATE = 'create', 'Create'

    class QuestionType(models.TextChoices):
        DEFINITION = 'definition', 'Definition'
        DERIVATION = 'derivation', 'Derivation'
        NUMERICAL = 'numerical', 'Numerical Problem'
        THEORY = 'theory', 'Theoretical'
        DIAGRAM = 'diagram', 'Diagram-based'
        COMPARISON = 'comparison', 'Comparison'
        SHORT_ANSWER = 'short_answer', 'Short Answer'
        LONG_ANSWER = 'long_answer', 'Long Answer'

    paper = models.ForeignKey(
        'papers.Paper',
        on_delete=models.CASCADE,
        related_name='questions'
    )

    question_number = models.CharField(max_length=20, blank=True)
    text = models.TextField()
    sub_questions = models.JSONField(default=list, blank=True)
    marks = models.PositiveIntegerField(null=True, blank=True)
    sub_part = models.CharField(max_length=5, blank=True, help_text='Empty for Part A, a or b for Part B sub-questions')

    images = models.JSONField(default=list, blank=True)

    module = models.ForeignKey(
        'subjects.Module',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions',
        db_index=True,
    )
    topics = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)

    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        blank=True,
    )

    difficulty = models.CharField(
        max_length=10,
        choices=DifficultyLevel.choices,
        blank=True
    )
    bloom_level = models.CharField(
        max_length=15,
        choices=BloomLevel.choices,
        blank=True
    )

    embedding = models.JSONField(null=True, blank=True)

    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates'
    )
    similarity_score = models.FloatField(null=True, blank=True)

    repetition_count = models.PositiveIntegerField(default=0)
    years_appeared = models.JSONField(default=list, blank=True)

    importance_score = models.FloatField(default=0.0)
    frequency_score = models.FloatField(default=0.0)

    topic_cluster = models.ForeignKey(
        'analytics.TopicCluster',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions'
    )

    part = models.CharField(max_length=1, blank=True, help_text='Part A or Part B', db_index=True)

    module_manually_set = models.BooleanField(default=False)
    difficulty_manually_set = models.BooleanField(default=False)

    # New field for Gemini pipeline
    needs_review = models.BooleanField(
        default=False,
        help_text='True if question text is suspiciously short or was flagged during validation'
    )

    class Meta:
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'
        ordering = ['question_number']
        constraints = [
            models.CheckConstraint(
                check=models.Q(marks__gt=0) | models.Q(marks__isnull=True),
                name='question_marks_positive',
            ),
        ]

    def clean(self):
        """Validate question data before saving."""
        super().clean()
        if not self.text or not str(self.text).strip():
            raise ValidationError({'text': 'Question text cannot be empty.'})
        # Validate q_number range if it looks numeric
        try:
            qn = int(self.question_number)
            if qn < 1 or qn > 20:
                raise ValidationError({
                    'question_number': 'Question number must be between 1 and 20.'
                })
        except (ValueError, TypeError):
            pass  # Non-numeric question numbers are allowed for flexibility

    def __str__(self):
        return f"Q{self.question_number}: {self.text[:50]}..."

    def get_confidence_color(self):
        """Return confidence indicator color: green, yellow, or red."""
        if self.needs_review:
            return 'red'
        if self.module_manually_set:
            return 'yellow'
        if self.text and len(self.text) >= 10:
            return 'green'
        return 'red'

    def get_similar_questions(self, threshold=0.8):
        if not self.embedding:
            return Question.objects.none()
        return Question.objects.none()
