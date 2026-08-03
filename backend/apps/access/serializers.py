from rest_framework import serializers

from .models import AccessEvent, AccessRule, Cardholder, Credential, Door


class DoorSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = Door
        fields = [
            "id",
            "name",
            "location",
            "controller_url",
            "relay",
            "unlock_seconds",
            "state",
            "camera",
            "camera_name",
            "created_at",
        ]
        read_only_fields = ["state", "created_at"]


class CredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credential
        fields = ["id", "cardholder", "kind", "value", "active"]


class CardholderSerializer(serializers.ModelSerializer):
    credentials = CredentialSerializer(many=True, read_only=True)
    is_valid_now = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cardholder
        fields = [
            "id",
            "first_name",
            "last_name",
            "employee_id",
            "kind",
            "valid_from",
            "valid_until",
            "host",
            "active",
            "is_valid_now",
            "photo",
            "credentials",
        ]


class AccessRuleSerializer(serializers.ModelSerializer):
    door_name = serializers.CharField(source="door.name", read_only=True)
    cardholder_name = serializers.SerializerMethodField()

    class Meta:
        model = AccessRule
        fields = [
            "id",
            "door",
            "door_name",
            "cardholder",
            "cardholder_name",
            "allowed",
            "weekly",
        ]

    def get_cardholder_name(self, obj):
        return f"{obj.cardholder.first_name} {obj.cardholder.last_name}"


class AccessEventSerializer(serializers.ModelSerializer):
    door_name = serializers.CharField(source="door.name", read_only=True)
    cardholder_name = serializers.SerializerMethodField()

    class Meta:
        model = AccessEvent
        fields = [
            "id",
            "door",
            "door_name",
            "cardholder",
            "cardholder_name",
            "credential_value",
            "decision",
            "reason",
            "ts",
        ]

    def get_cardholder_name(self, obj):
        return f"{obj.cardholder.first_name} {obj.cardholder.last_name}" if obj.cardholder else "—"
