"""Create a demo consultancy for local testing and sales demos.

    python manage.py seed_demo

Login: demo@docfit.local / the DEMO_PASSWORD env var (default below).
"""
import os

from django.core.management.base import BaseCommand

from accounts.models import Organization, User
from billing.models import Plan

DEFAULT_PASSWORD = "docfit-demo-2026"


class Command(BaseCommand):
    help = "Create (or reset) the demo consultancy account on the Pro plan."

    def handle(self, *args, **opts):
        password = os.environ.get("DEMO_PASSWORD", DEFAULT_PASSWORD)
        org, _ = Organization.objects.get_or_create(
            name="Demo Education Consultancy", defaults={"plan": Plan.objects.get(code="pro")})
        org.plan = Plan.objects.get(code="pro")
        org.plan_expires_at = None
        org.save()
        user, created = User.objects.get_or_create(
            email="demo@docfit.local",
            defaults={"full_name": "Demo Counsellor", "organization": org, "role": User.Role.OWNER})
        user.organization, user.role, user.is_active = org, User.Role.OWNER, True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Reset'} demo@docfit.local (password from DEMO_PASSWORD or default)."))
