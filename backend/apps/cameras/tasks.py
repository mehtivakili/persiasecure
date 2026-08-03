"""Celery tasks: periodic camera health checks."""
import logging

from celery import shared_task
from django.utils import timezone

from apps.mediactl import client as media_client

logger = logging.getLogger(__name__)


@shared_task
def health_check_all():
    """
    Poll MediaMTX for each enabled camera's path readiness and update status.
    Emits an 'offline' Event (and WS push) on online->offline transitions.
    """
    from django.core.cache import cache

    from apps.events.models import Event
    from apps.events.utils import broadcast_event

    from .models import Camera, CameraStatus

    # Heartbeat for the health monitor: proves worker+beat are alive.
    cache.set("celery_heartbeat", timezone.now(), timeout=600)

    checked = 0
    for camera in Camera.objects.filter(enabled=True):
        ready = media_client.is_camera_ready(camera)
        new_status = CameraStatus.ONLINE if ready else CameraStatus.OFFLINE
        prev = camera.status
        if ready:
            camera.last_seen = timezone.now()
        if new_status != prev:
            camera.status = new_status
            camera.save(update_fields=["status", "last_seen"])
            if new_status == CameraStatus.OFFLINE and prev == CameraStatus.ONLINE:
                ev = Event.objects.create(
                    organization=camera.organization,
                    camera=camera,
                    type="offline",
                    severity="warning",
                    details={"message": "ارتباط دوربین قطع شد."},
                )
                broadcast_event(ev)
        else:
            camera.save(update_fields=["last_seen"])
        checked += 1

    # Mark disabled cameras.
    Camera.objects.filter(enabled=False).exclude(
        status=CameraStatus.DISABLED
    ).update(status=CameraStatus.DISABLED)
    logger.info("health_check_all: %s cameras", checked)
    return checked


@shared_task
def resync_all_paths():
    """Push every enabled camera's path into MediaMTX (e.g. after a restart).

    Reconciles the effective record state (schedule + any active manual session)
    so recording survives MediaMTX/Django restarts.
    """
    from apps.recordings import services

    from .models import Camera

    count = 0
    for camera in Camera.objects.filter(enabled=True):
        services.reconcile_recording(camera)
        count += 1
    return count


@shared_task
def reconcile_camera_paths():
    """
    Self‑heal MediaMTX after a restart: re‑push ONLY the camera paths that are
    missing from its config (a restart drops runtime‑added paths, which turns
    every camera "offline"). Existing paths — and their live viewers — are left
    untouched, so this can run frequently without disrupting streams.
    """
    from apps.recordings import services

    from .models import Camera

    synced = 0
    for camera in Camera.objects.filter(enabled=True):
        if not media_client.path_is_configured(camera):
            services.reconcile_recording(camera)
            synced += 1
    if synced:
        logger.info("reconcile_camera_paths: re-pushed %s missing path(s)", synced)
    return synced
