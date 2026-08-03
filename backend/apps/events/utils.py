"""Broadcast helpers — push events to the org's WebSocket group."""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def event_payload(event):
    return {
        "id": event.id,
        "type": event.type,
        "severity": event.severity,
        "camera": event.camera_id,
        "camera_name": event.camera.name if event.camera else None,
        "details": event.details,
        "ts": event.ts.isoformat(),
        "acknowledged": event.acknowledged,
        "cleared": event.cleared,
    }


def broadcast_event(event):
    """Send a new/updated event to all clients subscribed to its organization."""
    layer = get_channel_layer()
    if layer is None:
        return
    group = f"org_{event.organization_id}"
    async_to_sync(layer.group_send)(
        group,
        {"type": "event.message", "payload": event_payload(event)},
    )
