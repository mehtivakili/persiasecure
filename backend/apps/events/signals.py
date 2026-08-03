"""Kick off automation whenever a new Event is created — from any code path."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Event


@receiver(post_save, sender=Event)
def _run_automation_on_new_event(sender, instance, created, **kwargs):
    if not created:
        return
    from .tasks import run_automation

    # After commit so the worker can read the row.
    transaction.on_commit(lambda: run_automation.delay(instance.id))
