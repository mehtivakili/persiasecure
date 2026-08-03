"""WebSocket consumer streaming live events/alarms to the browser."""
import json

from channels.generic.websocket import AsyncWebsocketConsumer


class EventConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        # Superusers without an org get a global group; others per-org.
        org_id = getattr(user, "organization_id", None) or 0
        self.group_name = f"org_{org_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({"type": "connected"}))

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients may send {"type":"ping"} to keep the socket warm.
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return
        if data.get("type") == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    async def event_message(self, event):
        await self.send(text_data=json.dumps({"type": "event", "data": event["payload"]}))
