from django.urls import path

from . import views

urlpatterns = [
    path("jobs", views.JobListCreateView.as_view()),
    path("jobs/stats", views.StatsView.as_view()),
    path("jobs/zip", views.JobZipView.as_view()),
    path("jobs/<uuid:pk>", views.JobDetailView.as_view()),
    path("jobs/<uuid:pk>/retry", views.JobRetryView.as_view()),
    path("jobs/<uuid:pk>/download", views.JobDownloadView.as_view()),
    path("jobs/<uuid:pk>/preview/<str:side>", views.JobPreviewView.as_view()),
]
