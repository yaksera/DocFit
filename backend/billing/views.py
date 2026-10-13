import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.auth import CanManage, HasOrganization
from accounts.models import Organization
from accounts.serializers import PlanSerializer

from . import khalti
from .models import Payment, Plan

log = logging.getLogger(__name__)

# months -> months charged (yearly = 2 months free)
BILLING_PERIODS = {1: 1, 12: 10}


class PlansView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(PlanSerializer(Plan.objects.filter(is_public=True), many=True).data)


class PaymentSerializer(serializers.ModelSerializer):
    plan = serializers.CharField(source="plan.name")

    class Meta:
        model = Payment
        fields = ["id", "plan", "months", "amount_npr", "provider", "status", "transaction_id",
                  "created_at", "completed_at"]


class PaymentsView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, CanManage]

    def get(self, request):
        qs = request.user.organization.payments.select_related("plan")[:50]
        return Response(PaymentSerializer(qs, many=True).data)


class KhaltiInitiateView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization, CanManage]

    def post(self, request):
        plan = Plan.objects.filter(code=request.data.get("plan"), is_public=True, price_npr__gt=0).first()
        if plan is None:
            raise ValidationError({"plan": "Choose a paid plan."})
        try:
            months = int(request.data.get("months", 1))
        except (TypeError, ValueError):
            months = 0
        if months not in BILLING_PERIODS:
            raise ValidationError({"months": "Choose monthly or yearly billing."})
        org = request.user.organization
        amount = plan.price_npr * BILLING_PERIODS[months]
        payment = Payment.objects.create(organization=org, plan=plan, months=months, amount_npr=amount,
                                         provider="khalti", created_by=request.user)
        try:
            data = khalti.initiate(
                amount_paisa=amount * 100, order_id=f"docfit-{payment.pk}",
                order_name=f"DocFit {plan.name} - {months} month{'s' if months > 1 else ''}",
                return_url=f"{settings.SITE_URL}/api/billing/khalti/return",
                website_url=settings.SITE_URL,
                customer={"name": request.user.full_name or request.user.email,
                          "email": request.user.email, "phone": org.phone})
        except khalti.KhaltiError as exc:
            payment.status = Payment.Status.FAILED
            payment.raw = {"error": str(exc)}
            payment.save(update_fields=["status", "raw"])
            raise ValidationError({"detail": str(exc)})
        payment.provider_ref = data.get("pidx", "")
        payment.raw = {"initiate": data}
        payment.save(update_fields=["provider_ref", "raw"])
        return Response({"payment_url": data.get("payment_url")})


def activate(payment: Payment, transaction_id: str, raw: dict) -> None:
    with transaction.atomic():
        p = Payment.objects.select_for_update().get(pk=payment.pk)
        if p.status == Payment.Status.COMPLETED:
            return  # already processed (user refreshed the return page)
        org = Organization.objects.select_for_update().get(pk=p.organization_id)
        now = timezone.now()
        base = org.plan_expires_at if (org.plan_id == p.plan_id and org.plan_expires_at
                                       and org.plan_expires_at > now) else now
        org.plan = p.plan
        org.plan_expires_at = base + timedelta(days=30 * p.months + (5 if p.months == 12 else 0))
        org.save(update_fields=["plan", "plan_expires_at"])
        p.status, p.transaction_id, p.completed_at = Payment.Status.COMPLETED, transaction_id, now
        p.raw = {**p.raw, "lookup": raw}
        p.save()


class KhaltiReturnView(View):
    """Khalti sends the customer's browser here. We verify with Khalti, then go back to the app."""

    def get(self, request):
        pidx = request.GET.get("pidx", "")
        payment = Payment.objects.filter(provider="khalti", provider_ref=pidx).first() if pidx else None
        if payment is None:
            return redirect("/app/billing?payment=failed")
        try:
            data = khalti.lookup(pidx)
        except khalti.KhaltiError:
            log.exception("Khalti lookup failed for payment %s", payment.pk)
            return redirect("/app/billing?payment=pending")
        state = data.get("status")
        if state == "Completed" and int(data.get("total_amount", 0)) == payment.amount_npr * 100:
            activate(payment, data.get("transaction_id", ""), data)
            return redirect("/app/billing?payment=success")
        if state in ("Pending", "Initiated"):
            return redirect("/app/billing?payment=pending")
        Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED, raw={**payment.raw, "lookup": data})
        return redirect("/app/billing?payment=failed")
