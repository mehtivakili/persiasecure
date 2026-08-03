from rest_framework import serializers

from .models import FederatedServer, RemoteCamera


class RemoteCameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemoteCamera
        fields = ["id", "remote_id", "name", "status", "webrtc_url", "hls_url"]


class FederatedServerSerializer(serializers.ModelSerializer):
    remote_cameras = RemoteCameraSerializer(many=True, read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = FederatedServer
        fields = [
            "id",
            "name",
            "base_url",
            "username",
            "password",
            "status",
            "last_sync",
            "camera_count",
            "enabled",
            "remote_cameras",
        ]
        read_only_fields = ["status", "last_sync", "camera_count"]
