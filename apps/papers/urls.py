"""URL patterns for papers app."""
from django.urls import path
from . import views, api_views

app_name = 'papers'

urlpatterns = [
    # Public upload - no authentication required
    path('upload/', views.GenericPaperUploadView.as_view(), name='upload_generic'),
    
    # Public processing status - no authentication required
    path('processing/<uuid:subject_pk>/', views.PublicProcessingStatusView.as_view(), name='processing_status'),
    
    # API endpoints for processing
    path('api/start-processing/', api_views.StartProcessingView.as_view(), name='start_processing'),
    path('api/paper/<uuid:paper_id>/status/', api_views.PaperStatusView.as_view(), name='paper_status'),
    path('api/subject/<uuid:subject_id>/status/', api_views.SubjectStatusView.as_view(), name='subject_status'),
    
    # Subject-specific views
    path('subject/<uuid:subject_pk>/', views.PaperListView.as_view(), name='list'),
    path('subject/<uuid:subject_pk>/upload/', views.PaperUploadView.as_view(), name='upload'),
    path('<uuid:pk>/', views.PaperDetailView.as_view(), name='detail'),
    path('<uuid:pk>/delete/', views.PaperDeleteView.as_view(), name='delete'),
]
