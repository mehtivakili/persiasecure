from django.contrib import admin

from .models import FederatedServer, RemoteCamera


@admin.register(FederatedServer)
class FederatedServerAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "status", "camera_count", "last_sync", "enabled")
    list_filter = ("status", "enabled")


@admin.register(RemoteCamera)
class RemoteCameraAdmin(admin.ModelAdmin):
    list_display = ("name", "server", "status")
