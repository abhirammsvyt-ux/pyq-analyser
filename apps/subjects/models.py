"""
Subject and Module models.
"""
from django.db import models
from django.conf import settings
from apps.core.models import SoftDeleteModel


class Subject(SoftDeleteModel):
    """Subject model with customizable module configuration."""
    
    class UniversityType(models.TextChoices):
        KTU = 'KTU', 'KTU (APJ Abdul Kalam Technological University)'
        OTHER = 'OTHER', 'Other University'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subjects',
        null=True,
        blank=True  # Make optional for public access
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    
    # University classification
    university_type = models.CharField(
        max_length=10,
        choices=UniversityType.choices,
        default=UniversityType.KTU,
        help_text='KTU uses rule-based mapping, Other uses AI classification'
    )
    
    # Syllabus file (optional) - used for AI classification
    syllabus_file = models.FileField(
        upload_to='syllabi/',
        null=True,
        blank=True,
        help_text='Optional: Upload syllabus for better AI classification'
    )
    syllabus_text = models.TextField(
        blank=True,
        help_text='Extracted syllabus text for semantic matching'
    )
    
    # Additional metadata
    university = models.CharField(max_length=255, blank=True)
    exam_board = models.CharField(max_length=255, blank=True)
    year = models.CharField(max_length=50, blank=True)
    
    # Settings stored as JSON
    settings = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        ordering = ['-created_at']
        # Remove unique constraint to allow public access without user
        # unique_together = ['user', 'name', 'code']
    
    def __str__(self):
        if self.code:
            return f"{self.code} - {self.name}"
        return self.name
    
    def get_module_count(self):
        """Return the number of modules for this subject."""
        return self.modules.count()
    
    def get_paper_count(self):
        """Return the number of papers for this subject."""
        return self.papers.count() if hasattr(self, 'papers') else 0


class Module(SoftDeleteModel):
    """Module within a subject."""
    
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='modules'
    )
    name = models.CharField(max_length=255)
    number = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    
    # Topics within the module
    topics = models.JSONField(default=list, blank=True)
    # Example: ["Topic 1", "Topic 2", "Topic 3"]
    
    # Keywords for classification
    keywords = models.JSONField(default=list, blank=True)
    # Example: ["keyword1", "keyword2"]
    
    # Weightage (for analysis)
    weightage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Expected weightage percentage in exams'
    )
    
    class Meta:
        verbose_name = 'Module'
        verbose_name_plural = 'Modules'
        ordering = ['number']
        unique_together = ['subject', 'number']
    
    def __str__(self):
        return f"Module {self.number}: {self.name}"
    
    def get_topic_list(self):
        """Return topics as a list."""
        if isinstance(self.topics, list):
            return self.topics
        return []
    
    def add_topic(self, topic):
        """Add a topic to the module."""
        if topic not in self.topics:
            self.topics.append(topic)
            self.save(update_fields=['topics'])
    
    def remove_topic(self, topic):
        """Remove a topic from the module."""
        if topic in self.topics:
            self.topics.remove(topic)
            self.save(update_fields=['topics'])


class ExamPattern(SoftDeleteModel):
    """
    Configurable exam pattern for mapping questions to modules.
    Example: KTU pattern - Part A Q1-2 -> Module 1, Q3-4 -> Module 2, etc.
    """
    
    subject = models.OneToOneField(
        Subject,
        on_delete=models.CASCADE,
        related_name='exam_pattern',
        null=True,
        blank=True
    )
    
    name = models.CharField(max_length=255, default='Default Pattern')
    description = models.TextField(blank=True)
    
    # Pattern configuration stored as JSON
    # Example for KTU:
    # {
    #   "part_a": {"1": 1, "2": 1, "3": 2, "4": 2, "5": 3, "6": 3, "7": 4, "8": 4, "9": 5, "10": 5},
    #   "part_b": {"11": 1, "12": 1, "13": 2, "14": 2, "15": 3, "16": 3, "17": 4, "18": 4, "19": 5, "20": 5}
    # }
    pattern_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Question number to module mapping'
    )
    
    # Default marks per question type
    part_a_marks = models.PositiveIntegerField(default=3)
    part_b_marks = models.PositiveIntegerField(default=14)
    
    class Meta:
        verbose_name = 'Exam Pattern'
        verbose_name_plural = 'Exam Patterns'
    
    def __str__(self):
        return f"{self.name} ({self.subject.name if self.subject else 'Global'})"
    
    def get_module_for_question(self, question_number: str, part: str) -> int:
        """
        Get module number for a question based on pattern.
        
        Args:
            question_number: Question number as string (e.g., "1", "11a")
            part: Part A or B
            
        Returns:
            Module number or None
        """
        # Extract numeric part from question number
        import re
        match = re.match(r'(\d+)', str(question_number))
        if not match:
            return None
        
        q_num = match.group(1)
        part_key = f'part_{part.lower()}'
        
        if part_key in self.pattern_config:
            return self.pattern_config[part_key].get(q_num)
        
        return None
    
    @classmethod
    def get_default_ktu_pattern(cls):
        """Return default KTU exam pattern configuration."""
        return {
            'part_a': {
                '1': 1, '2': 1,
                '3': 2, '4': 2,
                '5': 3, '6': 3,
                '7': 4, '8': 4,
                '9': 5, '10': 5,
            },
            'part_b': {
                '11': 1, '12': 1,
                '13': 2, '14': 2,
                '15': 3, '16': 3,
                '17': 4, '18': 4,
                '19': 5, '20': 5,
            }
        }
