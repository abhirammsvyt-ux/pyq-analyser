"""Views for analytics dashboard."""
from django.views.generic import TemplateView, View, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, FileResponse
from django.contrib import messages
from pathlib import Path

from apps.subjects.models import Subject, Module
from apps.analytics.models import TopicCluster
from .calculator import StatsCalculator


class SubjectListView(LoginRequiredMixin, ListView):
    """List all subjects with cluster statistics."""
    
    template_name = 'analytics/subject_list.html'
    context_object_name = 'subjects'
    
    def get_queryset(self):
        subjects = Subject.objects.filter(user=self.request.user).prefetch_related('papers')
        
        # Annotate each subject with cluster counts
        subject_list = []
        for subject in subjects:
            subject.tier_1_count = TopicCluster.objects.filter(
                subject=subject,
                priority_tier=TopicCluster.PriorityTier.TIER_1
            ).count()
            subject.tier_2_count = TopicCluster.objects.filter(
                subject=subject,
                priority_tier=TopicCluster.PriorityTier.TIER_2
            ).count()
            subject.tier_3_count = TopicCluster.objects.filter(
                subject=subject,
                priority_tier=TopicCluster.PriorityTier.TIER_3
            ).count()
            subject.tier_4_count = TopicCluster.objects.filter(
                subject=subject,
                priority_tier=TopicCluster.PriorityTier.TIER_4
            ).count()
            subject_list.append(subject)
        
        return subject_list


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """Analytics dashboard for a subject showing all modules."""
    
    template_name = 'analytics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        import json
        from collections import defaultdict
        context = super().get_context_data(**kwargs)
        subject = get_object_or_404(
            Subject, pk=self.kwargs['subject_pk'], user=self.request.user
        )
        
        calculator = StatsCalculator(subject)
        stats = calculator.get_complete_stats()
        
        # Get top topics per module for the main graph
        top_topics = calculator.get_top_topics_per_module(top_n=3)
        
        # Get all modules with their topic counts
        modules = subject.modules.all()
        module_data = []
        module_labels = []
        module_counts = []
        
        for module in modules:
            topic_count = TopicCluster.objects.filter(
                subject=subject,
                module=module
            ).count()
            tier_1_count = TopicCluster.objects.filter(
                subject=subject,
                module=module,
                priority_tier=TopicCluster.PriorityTier.TIER_1
            ).count()
            
            # Count questions in this module
            question_count = module.questions.count()
            module_labels.append(f'Module {module.number}')
            module_counts.append(question_count)
            
            module_data.append({
                'module': module,
                'topic_count': topic_count,
                'critical_topics': tier_1_count,
                'top_topics': top_topics.get(module.number, []),
                'question_count': question_count,
            })
        
        # Prepare chart data as JSON for JavaScript
        context['module_labels'] = json.dumps(module_labels)
        context['module_data'] = json.dumps(module_counts)
        
        # Bloom's taxonomy data
        bloom_dist = stats['bloom_distribution']
        bloom_data = [
            bloom_dist.get('remember', 0),
            bloom_dist.get('understand', 0),
            bloom_dist.get('apply', 0),
            bloom_dist.get('analyze', 0),
            bloom_dist.get('evaluate', 0),
            bloom_dist.get('create', 0),
        ]
        context['bloom_data'] = json.dumps(bloom_data)
        
        # Difficulty data
        diff_dist = stats['difficulty_distribution']
        difficulty_data = [
            diff_dist.get('easy', 0),
            diff_dist.get('medium', 0),
            diff_dist.get('hard', 0),
        ]
        context['difficulty_data'] = json.dumps(difficulty_data)
        
        # Year trend data
        year_trend = stats['year_trend']
        year_labels = [item['year'] for item in year_trend]
        year_data = [item['question_count'] for item in year_trend]
        context['year_labels'] = json.dumps(year_labels)
        context['year_data'] = json.dumps(year_data)
        
        # Compute additional stats
        total_questions = stats['overview']['total_questions']
        total_papers = stats['overview']['papers_count']
        repeated_questions = stats['overview']['duplicates']
        
        # Classification rate = questions with modules assigned
        from apps.questions.models import Question
        questions_with_module = Question.objects.filter(
            paper__subject=subject,
            module__isnull=False
        ).count()
        classification_rate = round(questions_with_module / total_questions * 100, 1) if total_questions else 0
        
        context['subject'] = subject
        
        # Get all modules
        modules = subject.modules.all().order_by('number')
        context['modules'] = modules
        
        # Group clusters by module
        all_clusters = TopicCluster.objects.filter(
            subject=subject
        ).select_related('module').prefetch_related('questions').order_by('-frequency_count')
        
        clusters_by_module = defaultdict(list)
        for cluster in all_clusters:
            if cluster.module:
                clusters_by_module[cluster.module.id].append(cluster)
        
        context['clusters_by_module'] = dict(clusters_by_module)
        
        # Priority tier counts
        context['stats'] = {
            'tier_1_count': TopicCluster.objects.filter(
                subject=subject, 
                priority_tier=TopicCluster.PriorityTier.TIER_1
            ).count(),
            'tier_2_count': TopicCluster.objects.filter(
                subject=subject, 
                priority_tier=TopicCluster.PriorityTier.TIER_2
            ).count(),
            'tier_3_count': TopicCluster.objects.filter(
                subject=subject, 
                priority_tier=TopicCluster.PriorityTier.TIER_3
            ).count(),
            'tier_4_count': TopicCluster.objects.filter(
                subject=subject, 
                priority_tier=TopicCluster.PriorityTier.TIER_4
            ).count(),
            'total_papers': total_papers,
            'total_questions': total_questions,
            'repeated_questions': repeated_questions,
        }
        
        return context


class ModuleAnalyticsView(LoginRequiredMixin, TemplateView):
    """Detailed analytics for a specific module."""
    
    template_name = 'analytics/module_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject = get_object_or_404(
            Subject, pk=self.kwargs['subject_pk'], user=self.request.user
        )
        module_number = self.kwargs['module_number']
        module = get_object_or_404(Module, subject=subject, number=module_number)
        
        calculator = StatsCalculator(subject)
        module_stats = calculator.get_module_topic_stats(module_number)
        
        # Get all topic clusters for this module
        topics = TopicCluster.objects.filter(
            subject=subject,
            module=module
        ).order_by('-frequency_count')
        
        # Count topics by tier
        tier_counts = {
            'tier_1': topics.filter(priority_tier=TopicCluster.PriorityTier.TIER_1).count(),
            'tier_2': topics.filter(priority_tier=TopicCluster.PriorityTier.TIER_2).count(),
            'tier_3': topics.filter(priority_tier=TopicCluster.PriorityTier.TIER_3).count(),
            'tier_4': topics.filter(priority_tier=TopicCluster.PriorityTier.TIER_4).count(),
        }
        
        context['subject'] = subject
        context['module'] = module
        context['stats'] = module_stats
        context['topics'] = topics
        context['tier_counts'] = tier_counts
        
        return context


class TriggerTopicAnalysisView(LoginRequiredMixin, View):
    """Trigger topic clustering analysis for a subject."""
    
    def post(self, request, subject_pk):
        subject = get_object_or_404(
            Subject, pk=subject_pk, user=request.user
        )
        
        # Queue the analysis task
        try:
            from apps.analysis.tasks import queue_topic_analysis
            queue_topic_analysis(subject)
            messages.success(
                request,
                'Topic analysis has been queued. This may take a few minutes.'
            )
        except Exception as e:
            messages.error(
                request,
                f'Failed to queue analysis: {str(e)}'
            )
        
        return redirect('analytics:dashboard', subject_pk=subject.pk)


class AnalyticsAPIView(LoginRequiredMixin, View):
    """API endpoint for analytics data (for Chart.js)."""
    
    def get(self, request, subject_pk):
        subject = get_object_or_404(
            Subject, pk=subject_pk, user=request.user
        )
        
        calculator = StatsCalculator(subject)
        stats = calculator.get_complete_stats()
        
        # Format data for charts
        chart_data = {
            'overview': stats['overview'],
            'modules': [],
            'top_topics': []
        }
        
        # Module distribution for pie chart
        for mod_data in stats['module_distribution']:
            chart_data['modules'].append({
                'label': f"Module {mod_data['module_number']}: {mod_data['module']}" if mod_data['module_number'] else 'Unclassified',
                'count': mod_data['count']
            })
        
        # Top topics per module for bar chart
        top_topics = stats.get('top_topics_per_module', {})
        for module_num, topics in top_topics.items():
            for topic in topics:
                chart_data['top_topics'].append({
                    'module': f"M{module_num}",
                    'topic': topic['topic'][:30] + '...' if len(topic['topic']) > 30 else topic['topic'],
                    'frequency': topic['frequency'],
                    'priority': topic['priority']
                })
        
        return JsonResponse(chart_data)
