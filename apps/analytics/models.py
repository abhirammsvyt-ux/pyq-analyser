"""
Analytics models for topic clustering and repetition analysis.
"""
from django.db import models
from apps.core.models import BaseModel


class TopicCluster(BaseModel):
    """
    Represents a cluster of similar questions grouped as a topic.
    Used for repetition analysis and priority assignment.
    """

    class PriorityTier(models.IntegerChoices):
        TIER_1 = 1, 'Top Priority (5+ exams)'
        TIER_2 = 2, 'High Priority (3-4 exams)'
        TIER_3 = 3, 'Medium Priority (2 exams)'
        TIER_4 = 4, 'Low Priority (1 exam)'

    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='topic_clusters'
    )

    module = models.ForeignKey(
        'subjects.Module',
        on_delete=models.CASCADE,
        related_name='topic_clusters',
        null=True,
        blank=True
    )

    topic_name = models.CharField(max_length=500)
    normalized_key = models.CharField(max_length=500, db_index=True)
    representative_text = models.TextField(blank=True)

    frequency_count = models.PositiveIntegerField(default=0)
    years_appeared = models.JSONField(default=list, blank=True)
    total_marks = models.PositiveIntegerField(default=0)
    question_count = models.PositiveIntegerField(default=0)

    priority_tier = models.IntegerField(
        choices=PriorityTier.choices,
        default=PriorityTier.TIER_4,
    )

    cluster_id = models.CharField(max_length=100, blank=True)

    part_a_count = models.PositiveIntegerField(default=0)
    part_b_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Topic Cluster'
        verbose_name_plural = 'Topic Clusters'
        ordering = ['-frequency_count', 'topic_name']
        indexes = [
            models.Index(fields=['subject', 'module']),
            models.Index(fields=['priority_tier']),
            models.Index(fields=['-frequency_count']),
        ]

    def __str__(self):
        return f"{self.topic_name} ({self.get_priority_tier_display()})"

    def calculate_priority_tier(self):
        """Calculate and set priority tier based on frequency count.
        Tier 1: 5+ years, Tier 2: 3-4 years, Tier 3: 2 years, Tier 4: 1 year.
        """
        if self.frequency_count >= 5:
            self.priority_tier = self.PriorityTier.TIER_1
        elif self.frequency_count >= 3:
            self.priority_tier = self.PriorityTier.TIER_2
        elif self.frequency_count >= 2:
            self.priority_tier = self.PriorityTier.TIER_3
        else:
            self.priority_tier = self.PriorityTier.TIER_4

    def get_questions(self):
        return self.questions.all()

    def get_tier_label(self):
        tier_map = {
            self.PriorityTier.TIER_1: 'Top Priority',
            self.PriorityTier.TIER_2: 'High Priority',
            self.PriorityTier.TIER_3: 'Medium Priority',
            self.PriorityTier.TIER_4: 'Low Priority',
        }
        return tier_map.get(self.priority_tier, 'Unknown')
