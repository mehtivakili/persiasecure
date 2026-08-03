"""
Recording signals:
  * reconcile MediaMTX when a schedule changes (admin/shell/API), and
  * assemble an event clip whenever a new Event is created (Phase 3).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.events.models import Event

from .models import RecordingSchedule


@receiver(post_save, sender=RecordingSchedule)
def _sync_recording(sender, instance, **kwargs):
    # Reconcile against the effective state (schedule + any manual session).
    from . import services

    services.reconcile_recording(instance.camera)


@receiver(post_save, sender=Event)
def _create_event_clip(sender, instance, created, **kwargs):
    if not created:
        return
    from . import clips

    clips.schedule_clip_for_event(instance)
