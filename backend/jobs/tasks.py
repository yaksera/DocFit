from celery import shared_task

from . import processing


@shared_task(name="jobs.tasks.process_job", acks_late=True)
def process_job_task(job_id: str) -> None:
    processing.process_job(job_id)


@shared_task(name="jobs.tasks.purge_expired")
def purge_expired() -> int:
    return processing.purge_expired()
