import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("persiansecure")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Queue isolation (Phase 7): AI/analytics inference runs on a dedicated `ai`
# queue consumed by a separate worker, so slow model inference can never delay
# recording indexing, event‑clip assembly, exports, health checks or alarms
# (which stay on the default `celery` queue).
app.conf.task_default_queue = "celery"
app.conf.task_routes = {
    "apps.analytics.tasks.*": {"queue": "ai"},
}

# Periodic jobs — health checks and recording indexing.
app.conf.beat_schedule = {
    "camera-health-check": {
        "task": "apps.cameras.tasks.health_check_all",
        "schedule": 30.0,  # seconds
    },
    "reconcile-camera-paths": {
        "task": "apps.cameras.tasks.reconcile_camera_paths",
        "schedule": 60.0,  # re-push only MISSING MediaMTX paths (self-heal after a restart)
    },
    "index-recordings": {
        "task": "apps.recordings.tasks.index_recordings",
        "schedule": 60.0,
    },
    "apply-retention": {
        "task": "apps.recordings.tasks.apply_retention",
        "schedule": crontab(minute=0),  # hourly
    },
    "evaluate-schedules": {
        "task": "apps.recordings.tasks.evaluate_schedules",
        "schedule": 60.0,  # toggle scheduled-mode recording as windows open/close
    },
    "check-storage": {
        "task": "apps.recordings.tasks.check_storage",
        "schedule": 300.0,  # low-storage alarm, every 5 minutes
    },
    "run-analytics-rules": {
        "task": "apps.analytics.tasks.run_enabled_rules",
        "schedule": 20.0,
    },
    "sync-federation": {
        "task": "apps.federation.tasks.sync_all_servers",
        "schedule": 60.0,
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
