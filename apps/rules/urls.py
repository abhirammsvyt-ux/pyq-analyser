"""URL patterns for rules app."""
from django.urls import path
from . import views

app_name = 'rules'

urlpatterns = [
    path('subject/<uuid:subject_pk>/', views.RuleListView.as_view(), name='list'),
    path('subject/<uuid:subject_pk>/create/', views.RuleCreateView.as_view(), name='create'),
    path('<uuid:pk>/edit/', views.RuleUpdateView.as_view(), name='update'),
    path('<uuid:pk>/delete/', views.RuleDeleteView.as_view(), name='delete'),
]
