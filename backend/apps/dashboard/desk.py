"""Smart Desk layout API — personal saved views for the operator canvas."""
from rest_framework import serializers, viewsets

from apps.accounts.permissions import HasVmsPermission

from .models import DeskLayout


class DeskLayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeskLayout
        fields = ["id", "name", "tile_count", "tiles", "is_default", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_tiles(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("چیدمان نامعتبر است.")
        valid_kinds = {"camera", "door", "map"}
        cleaned = []
        for tile in value:
            if tile.get("kind") not in valid_kinds:
                continue
            try:
                cleaned.append(
                    {
                        "index": int(tile["index"]),
                        "kind": tile["kind"],
                        "object_id": int(tile["object_id"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        return cleaned


class DeskLayoutViewSet(viewsets.ModelViewSet):
    """Layouts are private to the operator who created them."""

    serializer_class = DeskLayoutSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "liveview.view"
    required_perm_read = "liveview.view"

    def get_queryset(self):
        return DeskLayout.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user, organization=self.request.user.organization
        )
