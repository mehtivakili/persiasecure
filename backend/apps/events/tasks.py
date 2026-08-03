"""Automation executor: runs event-to-action rules for a newly created Event."""
import logging

import requests
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

TIMEOUT = 5


@shared_task
def run_automation(event_id):
    """Match all enabled rules of the event's org and execute their actions."""
    from .models import AutomationRule, Event

    event = Event.objects.filter(id=event_id).select_related("camera").first()
    if not event:
        return 0

    ran = 0
    rules = AutomationRule.objects.filter(
        organization=event.organization, enabled=True
    ).select_related("camera")
    for rule in rules:
        if not rule.matches(event):
            continue
        try:
            _execute(rule, event)
            rule.last_run = timezone.now()
            rule.run_count += 1
            rule.save(update_fields=["last_run", "run_count"])
            ran += 1
        except Exception as exc:  # never let one rule break the rest
            logger.warning("automation rule %s failed: %s", rule.id, exc)
    return ran


def _execute(rule, event):
    from .utils import event_payload

    params = rule.params or {}
    if rule.action == "webhook":
        url = params.get("url")
        if url:
            requests.post(
                url,
                json={"rule": rule.name, "event": event_payload(event)},
                timeout=TIMEOUT,
            )
    elif rule.action in ("unlock_door", "lock_door"):
        from apps.access import controller
        from apps.access.models import AccessEvent, Door

        door = Door.objects.filter(
            id=params.get("door"), organization=rule.organization
        ).first()
        if door:
            if rule.action == "unlock_door":
                controller.unlock(door)
            else:
                controller.lock(door)
            AccessEvent.objects.create(
                organization=rule.organization,
                door=door,
                decision="granted",
                reason=f"خودکارسازی: {rule.name}",
            )
    elif rule.action == "set_threat":
        from apps.accounts.models import THREAT_LEVELS

        level = params.get("level")
        if level in dict(THREAT_LEVELS):
            org = rule.organization
            org.threat_level = level
            org.save(update_fields=["threat_level"])
    elif rule.action in ("send_sms", "voice_call"):
        from . import notify

        message = params.get("message") or _alarm_message(event)
        conf = notify.org_conf(rule.organization)
        channel = "sms" if rule.action == "send_sms" else "call"
        send = notify.send_sms if rule.action == "send_sms" else notify.voice_call
        # An explicit phone on the rule wins; otherwise fan out to every
        # recipient configured for this channel in the Settings panel.
        targets = [params["phone"]] if params.get("phone") else notify.recipients(
            rule.organization, channel
        )
        for phone in targets:
            send(phone, message, conf=conf)


def _alarm_message(event):
    """Default Persian alarm text: what, where, when."""
    type_label = event.get_type_display()
    cam = event.camera.name if event.camera else "—"
    ts = event.ts.strftime("%H:%M:%S") if event.ts else ""
    return f"هشدار پرشین‌سکیور: {type_label} | دوربین: {cam} | ساعت {ts}"
