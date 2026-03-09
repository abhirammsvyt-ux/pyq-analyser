"""URL patterns for questions app."""
from django.urls import path
from . import views

app_name = 'questions'

urlpatterns = [
    path('', views.QuestionListView.as_view(), name='list'),
    path('<uuid:pk>/', views.QuestionDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.QuestionUpdateView.as_view(), name='edit'),
    path('<uuid:pk>/correct/', views.ManualCorrectionView.as_view(), name='correct'),
    path('<uuid:pk>/verify/', views.QuestionVerifyView.as_view(), name='verify'),
    path('export/', views.QuestionExportView.as_view(), name='export'),
]
