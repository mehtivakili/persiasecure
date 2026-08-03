from rest_framework import serializers

from .models import AnalyticsRule, ObjectDetection, PlateRead, PlateWatchlist


class AnalyticsRuleSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = AnalyticsRule
        fields = [
            "id",
            "camera",
            "camera_name",
            "kind",
            "enabled",
            "config",
            "interval_seconds",
        ]


class PlateReadSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = PlateRead
        fields = [
            "id",
            "camera",
            "camera_name",
            "plate",
            "confidence",
            "country",
            "snapshot",
            "watchlist_hit",
            "ts",
        ]


class ObjectDetectionSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source="camera.name", read_only=True)

    class Meta:
        model = ObjectDetection
        fields = [
            "id",
            "camera",
            "camera_name",
            "label",
            "confidence",
            "bbox",
            "snapshot",
            "ts",
        ]


class PlateWatchlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlateWatchlist
        fields = ["id", "plate", "reason", "active"]
