from rest_framework import serializers

from .models import MapMarker, SiteMap


class MapMarkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapMarker
        fields = ["id", "site_map", "kind", "object_id", "label", "x", "y", "rotation"]


class SiteMapSerializer(serializers.ModelSerializer):
    markers = MapMarkerSerializer(many=True, read_only=True)

    class Meta:
        model = SiteMap
        fields = ["id", "name", "image", "order", "markers", "created_at"]
        read_only_fields = ["created_at"]
