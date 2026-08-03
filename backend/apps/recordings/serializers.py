from rest_framework import serializers

from .models import EventClip, ExportJob, Recording, RecordingSchedule


class EventClipSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)
    stream_url = serializers.SerializerMethodField()

    class Meta:
        model = EventClip
        fields = [
            "id",
            "event",
            "camera",
            "camera_name",
            "start",
            "end",
            "status",
            "duration",
            "size",
            "sha256",
            "error",
            "protected_until",
            "created_at",
            "stream_url",
        ]
        read_only_fields = fields

    def get_stream_url(self, obj):
        return f"/api/event-clips/{obj.id}/stream/" if obj.status == EventClip.Status.READY else None


class RecordingScheduleSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = RecordingSchedule
        fields = [
            "id",
            "camera",
            "camera_name",
            "mode",
            "weekly",
            "retention_days",
            "segment_seconds",
            "pre_event_seconds",
            "post_event_seconds",
        ]

    def validate_camera(self, camera):
        """
        Enforce tenant ownership: a non‑superuser may only attach a schedule to a
        camera in their own organization. Without this, a crafted request could
        create/repoint a schedule onto another tenant's camera (issue #10).
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not user.is_superuser:
            if camera.organization_id != getattr(user, "organization_id", None):
                raise serializers.ValidationError("دوربین متعلق به سازمان شما نیست.")
        return camera

    def validate(self, attrs):
        # Guard against absurd values before they reach MediaMTX / retention.
        for field, lo, hi in (
            ("retention_days", 1, 3650),
            ("segment_seconds", 1, 3600),
            ("pre_event_seconds", 0, 300),
            ("post_event_seconds", 0, 600),
        ):
            if field in attrs and not (lo <= attrs[field] <= hi):
                raise serializers.ValidationError(
                    {field: f"مقدار باید بین {lo} و {hi} باشد."}
                )
        return attrs


class RecordingSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)
    stream_url = serializers.SerializerMethodField()

    class Meta:
        model = Recording
        fields = [
            "id",
            "camera",
            "camera_name",
            "start",
            "end",
            "duration",
            "size",
            "status",
            "has_motion",
            "stream_url",
        ]

    def get_stream_url(self, obj):
        # Served by the playback endpoint (streams the file with range support).
        return f"/api/recordings/{obj.id}/stream"


class ExportJobSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ExportJob
        fields = [
            "id",
            "camera",
            "camera_name",
            "start",
            "end",
            "status",
            "size",
            "sha256",
            "download_url",
            "note",
            "created_at",
        ]
        read_only_fields = ["status", "size", "sha256", "created_at"]

    def get_download_url(self, obj):
        return f"/api/exports/{obj.id}/download/" if obj.status == "done" else None

    def validate_camera(self, camera):
        """Only export from a camera in the caller's organization (tenancy)."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not user.is_superuser:
            if camera.organization_id != getattr(user, "organization_id", None):
                raise serializers.ValidationError("دوربین متعلق به سازمان شما نیست.")
        return camera
