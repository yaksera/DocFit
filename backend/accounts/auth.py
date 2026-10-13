from django.utils import timezone
from rest_framework import authentication, exceptions, permissions

from .models import ApiKey


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authorization: Bearer dfk_xxx"""

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode(errors="ignore")
        if not header.startswith("Bearer dfk_"):
            return None
        raw = header[len("Bearer "):].strip()
        key = (ApiKey.objects.select_related("user", "organization__plan")
               .filter(key_hash=ApiKey.hash(raw), revoked=False).first())
        if key is None or not key.user.is_active:
            raise exceptions.AuthenticationFailed("Invalid API key.")
        if not key.organization.effective_plan.api_access:
            raise exceptions.PermissionDenied("Your plan does not include API access.")
        now = timezone.now()
        if not key.last_used_at or (now - key.last_used_at).total_seconds() > 300:
            ApiKey.objects.filter(pk=key.pk).update(last_used_at=now)
        return key.user, key

    def authenticate_header(self, request):
        return "Bearer"


class HasOrganization(permissions.BasePermission):
    message = "Your account is not linked to an organization."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.organization_id)


class CanManage(permissions.BasePermission):
    message = "Only the owner or an admin can do this."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.can_manage)
