from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf", views.CsrfView.as_view()),
    path("auth/register", views.RegisterView.as_view()),
    path("auth/login", views.LoginView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/me", views.MeView.as_view()),
    path("auth/password", views.PasswordView.as_view()),
    path("auth/password-reset", views.PasswordResetView.as_view()),
    path("auth/password-reset/confirm", views.PasswordResetConfirmView.as_view()),
    path("organization", views.OrganizationView.as_view()),
    path("team", views.TeamView.as_view()),
    path("team/invites", views.InviteCreateView.as_view()),
    path("team/invites/<int:pk>", views.InviteDeleteView.as_view()),
    path("team/members/<int:pk>", views.MemberView.as_view()),
    path("invites/<str:token>", views.PublicInviteView.as_view()),
    path("keys", views.ApiKeysView.as_view()),
    path("keys/<int:pk>", views.ApiKeyDeleteView.as_view()),
]
