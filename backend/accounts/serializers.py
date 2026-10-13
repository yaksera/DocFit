from django.conf import settings
from django.contrib.auth import password_validation
from rest_framework import serializers

from billing.models import Plan

from .models import ApiKey, Invite, Organization, User


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["code", "name", "price_npr", "monthly_docs", "max_upload_mb", "max_pages", "seats",
                  "retention_hours", "api_access"]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "phone", "default_target_kb"]
        read_only_fields = ["id"]

    def validate_default_target_kb(self, v):
        if not 20 <= v <= 100_000:
            raise serializers.ValidationError("Choose between 20 KB and 100 MB.")
        return v


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "date_joined", "last_login"]
        read_only_fields = ["id", "email", "role", "date_joined", "last_login"]


def me_payload(user: User) -> dict:
    org = user.organization
    plan = org.effective_plan
    return {
        "user": UserSerializer(user).data,
        "organization": OrganizationSerializer(org).data,
        "plan": PlanSerializer(plan).data,
        "plan_expires_at": org.plan_expires_at if plan.price_npr else None,
        "usage": {"used": org.docs_used(), "limit": plan.monthly_docs,
                  "period_start": org.period_start()},
        "payments_enabled": bool(settings.KHALTI_SECRET_KEY),
    }


class _PasswordMixin:
    def validate(self, attrs):
        user = User(email=attrs.get("email", ""), full_name=attrs.get("full_name", ""))
        password_validation.validate_password(attrs["password"], user)
        return attrs


class RegisterSerializer(_PasswordMixin, serializers.Serializer):
    organization = serializers.CharField(max_length=150)
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate_email(self, v):
        v = v.lower()
        if User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return v


class AcceptInviteSerializer(_PasswordMixin, serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    validate_email = RegisterSerializer.validate_email


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField()


class InviteSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Invite
        fields = ["id", "role", "url", "created_at", "expires_at"]
        read_only_fields = ["id", "url", "created_at", "expires_at"]

    def get_url(self, obj):
        return f"{settings.SITE_URL}/invite/{obj.token}"

    def validate_role(self, v):
        if v == User.Role.OWNER:
            raise serializers.ValidationError("There can be only one owner.")
        return v


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ["id", "name", "prefix", "created_at", "last_used_at"]
        read_only_fields = ["id", "prefix", "created_at", "last_used_at"]
