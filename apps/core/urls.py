"""
URL patterns for core app.
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('health/', views.HealthCheckView.as_view(), name='health'),
    path('api-health/', views.APIHealthCheckView.as_view(), name='api_health'),
    path('api-status/', views.APIStatusJSONView.as_view(), name='api_status_json'),
]
