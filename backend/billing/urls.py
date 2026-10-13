from django.urls import path

from . import views

urlpatterns = [
    path("plans", views.PlansView.as_view()),
    path("billing/payments", views.PaymentsView.as_view()),
    path("billing/khalti/initiate", views.KhaltiInitiateView.as_view()),
    path("billing/khalti/return", views.KhaltiReturnView.as_view()),
]
