from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from billing.models import Plan

from .auth import CanManage, HasOrganization
from .models import ApiKey, Invite, Organization, User
from .serializers import (AcceptInviteSerializer, ApiKeySerializer, InviteSerializer, LoginSerializer,
                          OrganizationSerializer, PasswordChangeSerializer, RegisterSerializer,
                          UserSerializer, me_payload)


class AuthThrottled(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    permission_classes = [AllowAny]


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"ok": True})


class RegisterView(AuthThrottled):
    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        with transaction.atomic():
            org = Organization.objects.create(name=d["organization"], phone=d.get("phone", ""),
                                              plan=Plan.objects.get(code="free"))
            user = User.objects.create_user(d["email"], d["password"], full_name=d["full_name"],
                                            organization=org, role=User.Role.OWNER)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(me_payload(user), status=status.HTTP_201_CREATED)


class LoginView(AuthThrottled):
    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = authenticate(request, email=s.validated_data["email"].lower(),
                            password=s.validated_data["password"])
        if user is None:
            raise ValidationError({"detail": "Wrong email or password."})
        if not user.organization_id:
            raise PermissionDenied("This account has no organization. Use the admin site.")
        login(request, user)
        return Response(me_payload(user))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({"ok": True})


class MeView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization]

    def get(self, request):
        return Response(me_payload(request.user))

    def patch(self, request):
        s = UserSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(me_payload(request.user))


class OrganizationView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, CanManage]

    def patch(self, request):
        s = OrganizationSerializer(request.user.organization, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(me_payload(request.user))


class PasswordView(APIView):
    def post(self, request):
        s = PasswordChangeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if not request.user.check_password(s.validated_data["old_password"]):
            raise ValidationError({"old_password": "Current password is wrong."})
        password_validation.validate_password(s.validated_data["new_password"], request.user)
        request.user.set_password(s.validated_data["new_password"])
        request.user.save()
        update_session_auth_hash(request, request.user)
        return Response({"ok": True})


class PasswordResetView(AuthThrottled):
    """Always answers the same way, so it cannot be used to discover accounts."""

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.SITE_URL}/reset-password/{uid}/{token}"
            send_mail(
                "Reset your DocFit password",
                f"Hello {user.full_name or ''},\n\nReset your password here (valid for 3 hours):\n{link}\n\n"
                "If you did not ask for this, you can ignore this email.\n\nDocFit",
                None, [user.email], fail_silently=True)
        return Response({"ok": True})


class PasswordResetConfirmView(AuthThrottled):
    def post(self, request):
        try:
            uid = force_str(urlsafe_base64_decode(str(request.data.get("uid", ""))))
            user = User.objects.get(pk=uid, is_active=True)
        except (ValueError, TypeError, User.DoesNotExist):
            user = None
        if user is None or not default_token_generator.check_token(user, str(request.data.get("token", ""))):
            raise ValidationError({"detail": "This reset link is invalid or has expired. Request a new one."})
        password = str(request.data.get("password", ""))
        password_validation.validate_password(password, user)
        user.set_password(password)
        user.save()
        return Response({"ok": True})


# ---------------------------------------------------------------- team

class TeamView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization]

    def get(self, request):
        org = request.user.organization
        data = {
            "members": UserSerializer(org.members.filter(is_active=True).order_by("date_joined"),
                                      many=True).data,
            "seats": org.effective_plan.seats,
        }
        if request.user.can_manage:
            invites = [i for i in org.invites.filter(used_by__isnull=True).order_by("-created_at")
                       if i.is_valid]
            data["invites"] = InviteSerializer(invites, many=True).data
        return Response(data)


def _seats_left(org: Organization) -> int:
    used = org.members.filter(is_active=True).count()
    used += sum(1 for i in org.invites.filter(used_by__isnull=True) if i.is_valid)
    return org.effective_plan.seats - used


class InviteCreateView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, CanManage]

    def post(self, request):
        s = InviteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        org = request.user.organization
        if _seats_left(org) <= 0:
            raise PermissionDenied("All seats on your plan are in use. Upgrade to add more people.")
        invite = s.save(organization=org, created_by=request.user)
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)


class InviteDeleteView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, CanManage]

    def delete(self, request, pk):
        get_object_or_404(Invite, pk=pk, organization=request.user.organization).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, CanManage]

    def _get(self, request, pk) -> User:
        member = get_object_or_404(User, pk=pk, organization=request.user.organization, is_active=True)
        if member.role == User.Role.OWNER:
            raise PermissionDenied("The owner cannot be changed or removed.")
        if member == request.user:
            raise PermissionDenied("You cannot change your own access.")
        return member

    def patch(self, request, pk):
        member = self._get(request, pk)
        role = request.data.get("role")
        if role not in (User.Role.ADMIN, User.Role.MEMBER):
            raise ValidationError({"role": "Choose admin or member."})
        member.role = role
        member.save(update_fields=["role"])
        return Response(UserSerializer(member).data)

    def delete(self, request, pk):
        member = self._get(request, pk)
        member.is_active = False  # keep job history; free the seat
        member.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicInviteView(AuthThrottled):
    def get(self, request, token):
        invite = get_object_or_404(Invite, token=token)
        return Response({"organization": invite.organization.name, "valid": invite.is_valid,
                         "role": invite.role})

    def post(self, request, token):
        invite = get_object_or_404(Invite, token=token)
        if not invite.is_valid:
            raise ValidationError({"detail": "This invite link has expired or was already used."})
        s = AcceptInviteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        with transaction.atomic():
            user = User.objects.create_user(d["email"], d["password"], full_name=d["full_name"],
                                            organization=invite.organization, role=invite.role)
            invite.used_by = user
            invite.save(update_fields=["used_by"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(me_payload(user), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------- API keys

class ApiKeysView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, CanManage]

    def get(self, request):
        keys = ApiKey.objects.filter(organization=request.user.organization, revoked=False)
        return Response(ApiKeySerializer(keys.order_by("-created_at"), many=True).data)

    def post(self, request):
        if not request.user.organization.effective_plan.api_access:
            raise PermissionDenied("API access is available on the Pro plan and above.")
        s = ApiKeySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        key, raw = ApiKey.issue(request.user, s.validated_data["name"])
        return Response({**ApiKeySerializer(key).data, "key": raw}, status=status.HTTP_201_CREATED)


class ApiKeyDeleteView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, CanManage]

    def delete(self, request, pk):
        key = get_object_or_404(ApiKey, pk=pk, organization=request.user.organization)
        key.revoked = True
        key.save(update_fields=["revoked"])
        return Response(status=status.HTTP_204_NO_CONTENT)
