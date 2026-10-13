from django.db import models


class Plan(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=50)
    price_npr = models.PositiveIntegerField(default=0, help_text="Monthly price in NPR")
    monthly_docs = models.PositiveIntegerField(help_text="Documents per month (0 = unlimited)")
    max_upload_mb = models.PositiveIntegerField(help_text="Max total upload size per job")
    max_pages = models.PositiveIntegerField(default=100)
    seats = models.PositiveIntegerField(default=1, help_text="Team members")
    retention_hours = models.PositiveIntegerField(default=2, help_text="Files are deleted after this")
    api_access = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True, help_text="Shown on the pricing page")
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort", "price_npr"]

    def __str__(self) -> str:
        return self.name


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        COMPLETED = "completed"
        FAILED = "failed"

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE,
                                     related_name="payments")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    months = models.PositiveIntegerField(default=1)
    amount_npr = models.PositiveIntegerField()
    provider = models.CharField(max_length=20, default="khalti")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_ref = models.CharField(max_length=100, blank=True, db_index=True)  # Khalti pidx
    transaction_id = models.CharField(max_length=100, blank=True)
    raw = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.organization} {self.plan} NPR {self.amount_npr} ({self.status})"
