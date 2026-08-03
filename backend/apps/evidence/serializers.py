from rest_framework import serializers

from .models import CustodyLog, EvidenceCase, EvidenceItem


class CustodyLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = CustodyLog
        fields = ["id", "username", "action", "note", "ts"]


class EvidenceItemSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)
    added_by_name = serializers.CharField(source="added_by.username", read_only=True)

    class Meta:
        model = EvidenceItem
        fields = [
            "id",
            "case",
            "kind",
            "camera",
            "camera_name",
            "recording",
            "file_path",
            "sha256",
            "note",
            "added_by_name",
            "added_at",
        ]
        read_only_fields = ["sha256", "added_by_name", "added_at"]


class EvidenceCaseSerializer(serializers.ModelSerializer):
    items = EvidenceItemSerializer(many=True, read_only=True)
    custody = CustodyLogSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    item_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = EvidenceCase
        fields = [
            "id",
            "case_number",
            "title",
            "description",
            "status",
            "created_by_name",
            "item_count",
            "items",
            "custody",
            "created_at",
        ]
        read_only_fields = ["created_by_name", "created_at"]
