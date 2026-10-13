import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


class Job(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        PROCESSING = "processing"
        DONE = "done"
        FAILED = "failed"
        EXPIRED = "expired"  # files deleted after the retention period

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="jobs")
    user = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="jobs")
    label = models.CharField(max_length=120, blank=True, help_text="Student name or reference")
    via_api = models.BooleanField(default=False)

    # options
    target_bytes = models.PositiveBigIntegerField()
    color_mode = models.CharField(max_length=10, default="auto")
    output_format = models.CharField(max_length=5, default="pdf")
    clean_background = models.BooleanField(default=True)
    password = models.CharField(max_length=200, blank=True)  # wiped right after processing

    # input
    input_names = models.JSONField(default=list)
    input_bytes = models.PositiveBigIntegerField(default=0)

    # state / result
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED, db_index=True)
    progress = models.FloatField(default=0)
    message = models.CharField(max_length=200, blank=True)
    error = models.TextField(blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    output_name = models.CharField(max_length=255, blank=True)
    output_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=60, blank=True)
    pages = models.PositiveIntegerField(null=True, blank=True)
    met_target = models.BooleanField(null=True)
    level = models.IntegerField(null=True, blank=True)
    text_quality = models.CharField(max_length=20, blank=True)
    warnings = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.status})"

    @property
    def display_name(self) -> str:
        if not self.input_names:
            return str(self.id)
        if len(self.input_names) == 1:
            return self.input_names[0]
        return f"{self.input_names[0]} + {len(self.input_names) - 1} more"

    # ---- files (private storage, never served directly)
    @property
    def dir(self) -> Path:
        return Path(settings.DOCFIT_STORAGE) / "jobs" / str(self.id)

    @property
    def input_dir(self) -> Path:
        return self.dir / "in"

    def input_paths(self) -> list[Path]:
        if not self.input_dir.exists():
            return []
        return sorted(p for p in self.input_dir.iterdir() if p.is_file())

    def output_path(self) -> Path | None:
        out = self.dir / "out"
        if not out.exists():
            return None
        files = [p for p in out.iterdir() if p.is_file()]
        return files[0] if files else None

    @property
    def files_available(self) -> bool:
        return self.status == self.Status.DONE and self.output_path() is not None
