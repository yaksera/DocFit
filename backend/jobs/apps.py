import os
import sys

from django.apps import AppConfig


class JobsConfig(AppConfig):
    name = "jobs"

    def ready(self):
        from django.conf import settings

        # runserver's autoreloader imports twice; only start in the serving process.
        runserver = "runserver" in sys.argv and (
            os.environ.get("RUN_MAIN") == "true" or "--noreload" in sys.argv)
        if settings.JOB_RUNNER == "thread" and (
                runserver or os.environ.get("DOCFIT_THREAD_HOUSEKEEPING") == "1"):
            from .runner import start_thread_mode_housekeeping

            start_thread_mode_housekeeping()
