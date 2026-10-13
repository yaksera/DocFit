from django.contrib import admin

from .models import Payment, Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "price_npr", "monthly_docs", "max_upload_mb", "max_pages", "seats",
                    "retention_hours", "api_access", "is_public"]
    list_editable = ["price_npr", "monthly_docs", "max_upload_mb", "max_pages", "seats",
                     "retention_hours", "api_access", "is_public"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["organization", "plan", "months", "amount_npr", "provider", "status",
                    "transaction_id", "created_at"]
    list_filter = ["status", "provider", "plan"]
    search_fields = ["organization__name", "transaction_id", "provider_ref"]
    readonly_fields = ["raw"]
