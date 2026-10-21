"""
URL configuration for ai_providers app.
"""
from django.urls import path
from . import views

app_name = 'ai_providers'

urlpatterns = [
    path('', views.provider_dashboard, name='dashboard'),
    path('configure/', views.configure_provider, name='configure'),
    path('validate/<int:pk>/', views.validate_config, name='validate'),
    path('remove/<int:pk>/', views.remove_config, name='remove'),
]
