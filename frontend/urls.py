from django.urls import path

from . import views


app_name = "frontend"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("publishing/", views.publishing_overview, name="publishing"),
    path("help/", views.help_page, name="help"),
]
