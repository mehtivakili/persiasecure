from rest_framework import serializers

from .models import AutomationRule, Bookmark, Event, EventComment, NotificationSettings


class EventCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = EventComment
        fields = ["id", "event", "username", "text", "created_at"]
        read_only_fields = ["event", "username", "created_at"]


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = [
            "provider",
            "kavenegar_api_key",
            "sms_sender",
            "twilio_sid",
            "twilio_token",
            "twilio_from",
            "recipients",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_recipients(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("فهرست گیرندگان نامعتبر است.")
        cleaned = []
        for r in value:
            phone = str(r.get("phone", "")).strip()
            if not phone:
                continue
            cleaned.append(
                {
                    "name": str(r.get("name", "")).strip(),
                    "phone": phone,
                    "sms": bool(r.get("sms", True)),
                    "call": bool(r.get("call", False)),
                    "active": bool(r.get("active", True)),
                }
            )
        return cleaned


class EventSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)
    ack_by_name = serializers.CharField(source="ack_by.username", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.username", read_only=True)
    comment_count = serializers.IntegerField(source="comments.count", read_only=True)
    clip = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "camera",
            "camera_name",
            "type",
            "severity",
            "details",
            "snapshot",
            "ts",
            "acknowledged",
            "ack_by",
            "ack_by_name",
            "ack_at",
            "cleared",
            "assigned_to",
            "assigned_to_name",
            "comment_count",
            "clip",
        ]
        read_only_fields = ["ts", "ack_by", "ack_at", "assigned_to"]

    def get_clip(self, obj):
        from django.core.exceptions import ObjectDoesNotExist

        try:
            clip = obj.clip
        except ObjectDoesNotExist:
            return None
        return {
            "id": clip.id,
            "status": clip.status,
            "duration": clip.duration,
            "error": clip.error,
            "stream_url": (
                f"/api/event-clips/{clip.id}/stream/" if clip.status == "ready" else None
            ),
        }


class AutomationRuleSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = AutomationRule
        fields = [
            "id",
            "name",
            "enabled",
            "event_type",
            "min_severity",
            "camera",
            "camera_name",
            "action",
            "params",
            "last_run",
            "run_count",
        ]
        read_only_fields = ["last_run", "run_count"]


class BookmarkSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = Bookmark
        fields = ["id", "camera", "camera_name", "start", "end", "note", "created_at"]
        read_only_fields = ["created_at"]

    def validate_camera(self, camera):
        """Only bookmark a camera in the caller's organization (tenancy)."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not user.is_superuser:
            if camera.organization_id != getattr(user, "organization_id", None):
                raise serializers.ValidationError("دوربین متعلق به سازمان شما نیست.")
        return camera
