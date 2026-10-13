"""Dispatches jobs to Celery (production) or a background thread (local development)."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections, transaction

from . import processing

log = logging.getLogger(__name__)
_pool: ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()


def _thread_pool() -> ThreadPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="docfit-job")
        return _pool


def enqueue(job_id) -> None:
    def send():
        if settings.JOB_RUNNER == "celery":
            from .tasks import process_job_task

            process_job_task.delay(str(job_id))
        else:
            _thread_pool().submit(processing.run_in_thread, job_id)

    transaction.on_commit(send)


def start_thread_mode_housekeeping() -> None:
    """Thread mode only: re-queue jobs interrupted by a restart, purge expired files periodically."""
    from .models import Job

    def loop():
        close_old_connections()
        try:
            for job in Job.objects.filter(status__in=[Job.Status.QUEUED, Job.Status.PROCESSING]):
                Job.objects.filter(pk=job.pk).update(status=Job.Status.QUEUED, progress=0)
                _thread_pool().submit(processing.run_in_thread, job.pk)
        except Exception:  # database not migrated yet, etc.
            log.debug("Startup recovery skipped", exc_info=True)
        stop = threading.Event()
        while not stop.wait(600):
            try:
                close_old_connections()
                processing.purge_expired()
            except Exception:
                log.exception("Purge failed")

    threading.Thread(target=loop, name="docfit-housekeeping", daemon=True).start()
