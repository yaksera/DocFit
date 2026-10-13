"""Runs the compression engine for a Job and manages its files."""
import logging
import os
import shutil
import time
from pathlib import Path

from django.db import close_old_connections
from django.utils import timezone

from engine import CompressOptions, EngineError, PasswordRequired, compress

from .models import Job

log = logging.getLogger(__name__)

ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp"}


def output_name(job: Job, ext: str) -> str:
    stem = Path(job.input_names[0]).stem if job.input_names else "document"
    if len(job.input_names) > 1:
        stem = f"{job.label or stem}-merged"
    safe = "".join(c if c.isalnum() or c in " ._-()" else "_" for c in stem).strip() or "document"
    return f"{safe[:120]}-compressed{ext}"


def process_job(job_id) -> None:
    job = Job.objects.filter(pk=job_id).first()
    if job is None or job.status not in (Job.Status.QUEUED, Job.Status.PROCESSING):
        return
    Job.objects.filter(pk=job.pk).update(status=Job.Status.PROCESSING, started_at=timezone.now(),
                                         progress=0.01, message="Starting")
    plan = job.organization.effective_plan
    opts = CompressOptions(target_bytes=job.target_bytes, color_mode=job.color_mode,
                           output_format=job.output_format, clean_background=job.clean_background,
                           password=job.password or None, max_pages=plan.max_pages)
    last = [0.0]

    def progress(frac: float, msg: str) -> None:
        now = time.monotonic()
        if now - last[0] > 0.7 or frac >= 1:
            last[0] = now
            Job.objects.filter(pk=job.pk).update(progress=round(frac, 3), message=msg[:200])

    out_dir = job.dir / "out"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = {"password": "", "finished_at": None}
    try:
        result = compress([str(p) for p in job.input_paths()], str(out_dir / "result"), opts, progress)
        ext = os.path.splitext(result.output_path)[1]
        fields.update(
            status=Job.Status.DONE, progress=1.0, message="Done", output_bytes=result.output_bytes,
            content_type=result.content_type, pages=result.pages, met_target=result.met_target,
            level=result.level, text_quality=result.text_quality, warnings=result.warnings,
            output_name=output_name(job, ext), error="", error_code="")
    except PasswordRequired as exc:
        fields.update(status=Job.Status.FAILED, error=str(exc), error_code="password_required")
    except EngineError as exc:
        fields.update(status=Job.Status.FAILED, error=str(exc), error_code="engine")
    except Exception:  # noqa: BLE001 - never leave a job stuck in "processing"
        log.exception("Job %s crashed", job.pk)
        fields.update(status=Job.Status.FAILED, error_code="internal",
                      error="Something went wrong while processing this file. Our team has been "
                            "notified; please try again or contact support.")
    fields["finished_at"] = timezone.now()
    if fields["status"] == Job.Status.FAILED:
        fields["message"] = "Failed"
        shutil.rmtree(out_dir, ignore_errors=True)
    Job.objects.filter(pk=job.pk).update(**fields)


def delete_files(job: Job) -> None:
    shutil.rmtree(job.dir, ignore_errors=True)


def purge_expired() -> int:
    """Delete the files of jobs past their retention time. Returns how many."""
    n = 0
    for job in Job.objects.filter(expires_at__lt=timezone.now()).exclude(status=Job.Status.EXPIRED):
        if job.status in (Job.Status.QUEUED, Job.Status.PROCESSING):
            continue
        delete_files(job)
        Job.objects.filter(pk=job.pk).update(status=Job.Status.EXPIRED, password="")
        n += 1
    if n:
        log.info("Purged files of %d expired jobs", n)
    return n


def run_in_thread(job_id) -> None:
    close_old_connections()
    try:
        process_job(job_id)
    finally:
        close_old_connections()
