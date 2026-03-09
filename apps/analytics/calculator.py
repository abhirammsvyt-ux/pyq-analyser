"""
Statistics calculator for analytics dashboard.
"""
from typing import Dict, Any, List
from collections import Counter
from django.db.models import Count, Avg

from apps.questions.models import Question
from apps.subjects.models import Subject
from apps.analytics.models import TopicCluster


class StatsCalculator:
    """Calculates statistics for a subject."""
    
    def __init__(self, subject: Subject):
        self.subject = subject
        self.questions = Question.objects.filter(paper__subject=subject)
    
    def get_overview(self) -> Dict[str, Any]:
        """Get overview statistics."""
        total_questions = self.questions.count()
        unique_questions = self.questions.filter(is_duplicate=False).count()
        duplicates = total_questions - unique_questions
        
        # Count topic clusters
        total_clusters = TopicCluster.objects.filter(subject=self.subject).count()
        tier_1_topics = TopicCluster.objects.filter(
            subject=self.subject,
            priority_tier=TopicCluster.PriorityTier.TIER_1
        ).count()
        
        return {
            'total_questions': total_questions,
            'unique_questions': unique_questions,
            'duplicates': duplicates,
            'duplicate_percentage': round(duplicates / total_questions * 100, 1) if total_questions else 0,
            'papers_count': self.subject.papers.count(),
            'modules_count': self.subject.modules.count(),
            'total_topics': total_clusters,
            'critical_topics': tier_1_topics,
        }
    
    def get_module_distribution(self) -> List[Dict[str, Any]]:
        """Get question distribution across modules."""
        modules = self.subject.modules.all()
        distribution = []
        
        for module in modules:
            count = self.questions.filter(module=module).count()
            distribution.append({
                'module': module.name,
                'module_number': module.number,
                'count': count,
                'expected_weightage': float(module.weightage),
            })
        
        # Add unclassified
        unclassified = self.questions.filter(module__isnull=True).count()
        if unclassified:
            distribution.append({
                'module': 'Unclassified',
                'module_number': 0,
                'count': unclassified,
                'expected_weightage': 0,
            })
        
        return distribution
    
    def get_difficulty_distribution(self) -> Dict[str, int]:
        """Get question distribution by difficulty."""
        return dict(
            self.questions
            .exclude(difficulty='')
            .values('difficulty')
            .annotate(count=Count('id'))
            .values_list('difficulty', 'count')
        )
    
    def get_bloom_distribution(self) -> Dict[str, int]:
        """Get question distribution by Bloom's level."""
        return dict(
            self.questions
            .exclude(bloom_level='')
            .values('bloom_level')
            .annotate(count=Count('id'))
            .values_list('bloom_level', 'count')
        )
    
    def get_year_trend(self) -> List[Dict[str, Any]]:
        """Get question count trend by year."""
        papers = self.subject.papers.exclude(year='').order_by('year')
        trend = []
        
        for paper in papers:
            count = paper.questions.count()
            trend.append({
                'year': paper.year,
                'paper': paper.title,
                'question_count': count,
            })
        
        return trend
    
    def get_topic_frequency(self, top_n: int = 10) -> List[Dict[str, int]]:
        """Get most frequent topics."""
        all_topics = []
        for question in self.questions.exclude(topics=[]):
            all_topics.extend(question.topics)
        
        counter = Counter(all_topics)
        return [{'topic': t, 'count': c} for t, c in counter.most_common(top_n)]
    
    def get_top_topics_per_module(self, top_n: int = 3) -> Dict[int, List[Dict[str, Any]]]:
        """
        Get top N topics for each module based on repetition.
        Used for the main dashboard graph.
        """
        modules = self.subject.modules.all()
        result = {}
        
        for module in modules:
            clusters = TopicCluster.objects.filter(
                subject=self.subject,
                module=module
            ).order_by('-frequency_count')[:top_n]
            
            result[module.number] = [
                {
                    'topic': cluster.topic_name,
                    'frequency': cluster.frequency_count,
                    'priority': cluster.get_tier_label(),
                    'marks': cluster.total_marks,
                }
                for cluster in clusters
            ]
        
        return result
    
    def get_module_topic_stats(self, module_number: int) -> Dict[str, Any]:
        """Get detailed topic statistics for a specific module."""
        try:
            module = self.subject.modules.get(number=module_number)
        except:
            return {}
        
        clusters = TopicCluster.objects.filter(
            subject=self.subject,
            module=module
        ).order_by('-frequency_count')
        
        # Group by priority tier
        by_tier = {}
        for tier in TopicCluster.PriorityTier:
            tier_clusters = clusters.filter(priority_tier=tier)
            by_tier[tier.label] = [
                {
                    'topic': c.topic_name,
                    'frequency': c.frequency_count,
                    'years': c.years_appeared,
                    'marks': c.total_marks,
                }
                for c in tier_clusters
            ]
        
        return {
            'module': module,
            'total_topics': clusters.count(),
            'topics_by_tier': by_tier,
            'all_topics': [
                {
                    'topic': c.topic_name,
                    'frequency': c.frequency_count,
                    'tier': c.get_tier_label(),
                }
                for c in clusters
            ]
        }
    
    def get_complete_stats(self) -> Dict[str, Any]:
        """Get all statistics."""
        return {
            'overview': self.get_overview(),
            'module_distribution': self.get_module_distribution(),
            'difficulty_distribution': self.get_difficulty_distribution(),
            'bloom_distribution': self.get_bloom_distribution(),
            'year_trend': self.get_year_trend(),
            'top_topics': self.get_topic_frequency(),
            'top_topics_per_module': self.get_top_topics_per_module(),
        }
