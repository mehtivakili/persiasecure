from django.contrib import admin

from .models import (
    AnalyticsRule,
    DetectorModel,
    ObjectDetection,
    PlateRead,
    PlateWatchlist,
)


@admin.register(AnalyticsRule)
class AnalyticsRuleAdmin(admin.ModelAdmin):
    list_display = ("camera", "kind", "enabled", "interval_seconds")
    list_filter = ("kind", "enabled")


@admin.register(PlateRead)
class PlateReadAdmin(admin.ModelAdmin):
    list_display = ("plate", "camera", "confidence", "watchlist_hit", "ts")
    list_filter = ("watchlist_hit", "camera")
    search_fields = ("plate",)


@admin.register(ObjectDetection)
class ObjectDetectionAdmin(admin.ModelAdmin):
    list_display = ("label", "camera", "confidence", "ts")
    list_filter = ("label", "camera")


@admin.register(PlateWatchlist)
class PlateWatchlistAdmin(admin.ModelAdmin):
    list_display = ("plate", "organization", "active", "reason")
    search_fields = ("plate",)


@admin.register(DetectorModel)
class DetectorModelAdmin(admin.ModelAdmin):
    list_display = ("name", "task", "version", "framework", "device", "active", "created_at")
    list_filter = ("task", "framework", "device", "active")
    search_fields = ("name", "version")
    list_editable = ("active",)
