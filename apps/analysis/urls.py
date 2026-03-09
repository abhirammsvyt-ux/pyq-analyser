"""URL patterns for analysis app."""
from django.urls import path
from . import views

app_name = 'analysis'

urlpatterns = [
    path('jobs/', views.AnalysisJobListView.as_view(), name='job_list'),
    path('job/<uuid:pk>/', views.AnalysisDetailView.as_view(), name='detail'),
    path('job/<uuid:pk>/status/', views.AnalysisStatusView.as_view(), name='status'),
    path('subject/<uuid:subject_pk>/analyze/', views.ManualAnalyzeView.as_view(), name='manual_analyze'),
    path('subject/<uuid:subject_pk>/reset/', views.ResetAndAnalyzeView.as_view(), name='reset_analyze'),
    path('paper/<uuid:pk>/log/', views.ProcessingLogView.as_view(), name='processing_log'),
]
