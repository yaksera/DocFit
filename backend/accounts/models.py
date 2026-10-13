import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    """A consultancy (the paying customer). Users belong to one organization."""

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    plan = models.ForeignKey("billing.Plan", on_delete=models.PROTECT, related_name="organizations")
    plan_expires_at = models.DateTimeField(null=True, blank=True,
                                           help_text="Paid plans fall back to Free after this")
    default_target_kb = models.PositiveIntegerField(default=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    @property
    def effective_plan(self):
        from billing.models import Plan

        if self.plan.price_npr and self.plan_expires_at and self.plan_expires_at < timezone.now():
            return Plan.objects.get(code="free")
        return self.plan

    def period_start(self):
        now = timezone.localtime()
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def docs_used(self) -> int:
        return self.jobs.filter(created_at__gte=self.period_start()).exclude(status="failed").count()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner"
        ADMIN = "admin"
        MEMBER = "member"

    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.CASCADE,
                                     related_name="members")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    objects = UserManager()

    def __str__(self) -> str:
        return self.email

    @property
    def can_manage(self) -> bool:
        return self.role in (self.Role.OWNER, self.Role.ADMIN)


def _token() -> str:
    return secrets.token_urlsafe(24)


class Invite(models.Model):
    """Invite link the owner shares (WhatsApp, email...). No mail server needed."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invites")
    token = models.CharField(max_length=64, unique=True, default=_token)
    role = models.CharField(max_length=10, choices=User.Role.choices, default=User.Role.MEMBER)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_valid(self) -> bool:
        return self.used_by_id is None and self.expires_at > timezone.now()


class ApiKey(models.Model):
    """Key for programmatic access (Authorization: Bearer dfk_...). Only a hash is stored."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="api_keys")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=80)
    prefix = models.CharField(max_length=12, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)

    @staticmethod
    def hash(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(cls, user: User, name: str) -> tuple["ApiKey", str]:
        raw = "dfk_" + secrets.token_urlsafe(32)
        key = cls.objects.create(organization=user.organization, user=user, name=name,
                                 prefix=raw[:12], key_hash=cls.hash(raw))
        return key, raw
