"""Celery tasks: poll federated servers and refresh their camera snapshots."""
import logging

from celery import shared_task
from django.utils import timezone

from . import client

logger = logging.getLogger(__name__)


@shared_task
def sync_server(server_id):
    from .models import FederatedServer, RemoteCamera

    server = FederatedServer.objects.filter(id=server_id, enabled=True).first()
    if not server:
        return 0
    if not client.ping(server):
        server.status = FederatedServer.Status.OFFLINE
        server.save(update_fields=["status"])
        return 0

    cameras = client.fetch_cameras(server)
    server.status = FederatedServer.Status.ONLINE
    if cameras is not None:
        server.remote_cameras.all().delete()
        for cam in cameras:
            playback = cam.get("playback", {})
            RemoteCamera.objects.create(
                server=server,
                remote_id=cam.get("id", 0),
                name=cam.get("name", ""),
                status=cam.get("status", "unknown"),
                webrtc_url=playback.get("webrtc", ""),
                hls_url=playback.get("hls", ""),
            )
        server.camera_count = len(cameras)
    server.last_sync = timezone.now()
    server.save(update_fields=["status", "camera_count", "last_sync"])
    return server.camera_count


@shared_task
def sync_all_servers():
    from .models import FederatedServer

    ids = FederatedServer.objects.filter(enabled=True).values_list("id", flat=True)
    for sid in ids:
        sync_server.delay(sid)
    return len(ids)
