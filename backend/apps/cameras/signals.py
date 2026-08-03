"""Keep MediaMTX in sync when cameras change outside the API (admin, shell)."""
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.mediactl import client as media_client

from .models import Camera


@receiver(post_delete, sender=Camera)
def _remove_path_on_delete(sender, instance, **kwargs):
    media_client.remove_camera_path(instance)
