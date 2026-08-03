from django.contrib import admin

from .models import Camera, CameraGroup, PtzPreset, StreamProfile


class StreamProfileInline(admin.TabularInline):
    model = StreamProfile
    extra = 1


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "status", "enabled", "ptz_enabled", "last_seen")
    list_filter = ("organization", "status", "enabled")
    search_fields = ("name", "host", "rtsp_url")
    inlines = [StreamProfileInline]


@admin.register(CameraGroup)
class CameraGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "layout")
    filter_horizontal = ("cameras",)


admin.site.register(PtzPreset)
