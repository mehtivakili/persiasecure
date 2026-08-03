from rest_framework import serializers

from apps.mediactl import client as media_client

from .models import Camera, CameraGroup, PtzPreset, StreamProfile


class RecordingPolicySerializer(serializers.Serializer):
    """
    Write‑only recording policy accepted alongside a camera so onboarding can
    create the camera and its RecordingSchedule atomically (issue #1). Mirrors
    the fields the RecordingSchedule owns; validation limits guard bad input.
    """

    mode = serializers.ChoiceField(
        choices=["off", "continuous", "motion", "scheduled"], default="off"
    )
    retention_days = serializers.IntegerField(min_value=1, max_value=3650, default=14)
    segment_seconds = serializers.IntegerField(min_value=1, max_value=3600, default=60)
    # weekly = {"0".."6": [{"from":"HH:MM","to":"HH:MM"}]} (0=Saturday) for scheduled mode.
    weekly = serializers.JSONField(required=False)

    def validate_weekly(self, value):
        if not value:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("ساختار زمان‌بندی نامعتبر است.")
        for day, windows in value.items():
            if str(day) not in {"0", "1", "2", "3", "4", "5", "6"}:
                raise serializers.ValidationError("شاخص روز باید بین ۰ تا ۶ باشد.")
            if not isinstance(windows, list):
                raise serializers.ValidationError("پنجره‌های هر روز باید فهرست باشند.")
            for w in windows:
                if not isinstance(w, dict) or "from" not in w or "to" not in w:
                    raise serializers.ValidationError("هر بازه باید from و to داشته باشد.")
        return value


class StreamProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StreamProfile
        fields = [
            "id",
            "kind",
            "codec",
            "resolution",
            "fps",
            "bitrate_kbps",
            "rtsp_transport",
        ]


class PtzPresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PtzPreset
        fields = ["id", "name", "token"]


class CameraSerializer(serializers.ModelSerializer):
    stream_profiles = StreamProfileSerializer(many=True, required=False)
    ptz_presets = PtzPresetSerializer(many=True, read_only=True)
    playback = serializers.SerializerMethodField()
    is_recording = serializers.BooleanField(read_only=True)
    # True recording mode from the camera's schedule (off when none) so the UI
    # can show the actual policy instead of guessing "continuous".
    record_mode = serializers.SerializerMethodField()
    # Effective recording state (schedule OR an active manual session) and
    # whether a manual session is the reason — drives the Start/Stop button.
    recording_active = serializers.SerializerMethodField()
    manual_recording = serializers.SerializerMethodField()
    # Write‑only policy: onboarding sends this so the camera + its schedule are
    # created together, atomically (issue #1).
    recording = RecordingPolicySerializer(write_only=True, required=False)
    # password is write-only, so it is accepted on save but NEVER serialized
    # back to the browser (issue #10).
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, style={"input_type": "password"}
    )

    class Meta:
        model = Camera
        fields = [
            "id",
            "name",
            "location",
            "enabled",
            "protocol",
            "host",
            "port",
            "path",
            "rtsp_url",
            "username",
            "password",
            "onvif_host",
            "onvif_port",
            "onvif_enabled",
            "manufacturer",
            "model",
            "status",
            "last_seen",
            "ptz_enabled",
            "thumbnail",
            "is_recording",
            "record_mode",
            "recording_active",
            "manual_recording",
            "recording",
            "stream_profiles",
            "ptz_presets",
            "playback",
            "created_at",
        ]
        read_only_fields = ["status", "last_seen", "thumbnail", "created_at"]

    def get_playback(self, obj):
        return media_client.playback_urls(obj)

    def get_record_mode(self, obj):
        sched = getattr(obj, "schedule", None)
        return sched.mode if sched else "off"

    def get_recording_active(self, obj):
        from apps.recordings.services import should_record

        return should_record(obj)

    def get_manual_recording(self, obj):
        from apps.recordings.services import active_manual_session

        return active_manual_session(obj) is not None

    def create(self, validated_data):
        from apps.recordings.models import RecordingSchedule

        profiles = validated_data.pop("stream_profiles", [])
        recording = validated_data.pop("recording", None)
        request = self.context.get("request")
        # Cameras are organization-scoped.  Superusers still need to be
        # attached to their current organization; leaving this unset causes a
        # database IntegrityError because Camera.organization is NOT NULL.
        organization = getattr(getattr(request, "user", None), "organization", None)
        if organization is None:
            raise serializers.ValidationError(
                {"organization": "کاربر جاری به هیچ سازمانی اختصاص داده نشده است."}
            )
        validated_data["organization"] = organization
        # The whole graph (camera + profiles + schedule) is created here; the
        # view wraps this in a transaction and rolls it back if the media server
        # cannot be configured, so a camera never persists half‑onboarded.
        camera = Camera.objects.create(**validated_data)
        if not profiles:
            profiles = [{"kind": "main"}]
        for prof in profiles:
            StreamProfile.objects.create(camera=camera, **prof)
        if recording is not None:
            RecordingSchedule.objects.create(camera=camera, **recording)
        return camera

    def update(self, instance, validated_data):
        from apps.recordings.models import RecordingSchedule

        profiles = validated_data.pop("stream_profiles", None)
        recording = validated_data.pop("recording", None)
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # A blank/omitted password preserves the stored (encrypted) one — the
        # browser never receives it, so it cannot resend it on edit (issue #10).
        if password is not None and password != "":
            instance.password = password
        instance.save()
        if profiles is not None:
            instance.stream_profiles.all().delete()
            for prof in profiles:
                StreamProfile.objects.create(camera=instance, **prof)
        if recording is not None:
            RecordingSchedule.objects.update_or_create(camera=instance, defaults=recording)
        return instance


class CameraGroupSerializer(serializers.ModelSerializer):
    camera_details = CameraSerializer(source="cameras", many=True, read_only=True)

    class Meta:
        model = CameraGroup
        fields = ["id", "name", "layout", "cameras", "camera_details"]

    def create(self, validated_data):
        request = self.context.get("request")
        cameras = validated_data.pop("cameras", [])
        if request and not request.user.is_superuser:
            validated_data["organization"] = request.user.organization
        group = CameraGroup.objects.create(**validated_data)
        group.cameras.set(cameras)
        return group
