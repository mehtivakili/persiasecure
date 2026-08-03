"""
Multi-server federation.

A FederatedServer is a remote PersianSecure (or compatible) node whose cameras
and events can be aggregated into this control center. We store connection
credentials, poll health, and cache a lightweight snapshot of the remote's
cameras (RemoteCamera) for a unified list without proxying every request.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Organization


class FederatedServer(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online", _("آنلاین")
        OFFLINE = "offline", _("آفلاین")
        UNKNOWN = "unknown", _("نامشخص")

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="federated_servers"
    )
    name = models.CharField(_("نام سرور"), max_length=120)
    base_url = models.CharField(_("آدرس پایه"), max_length=300)  # e.g. https://site2:8080
    username = models.CharField(max_length=120, blank=True, default="")
    password = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.UNKNOWN)
    last_sync = models.DateTimeField(null=True, blank=True)
    camera_count = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("سرور فدراسیون")
        verbose_name_plural = _("سرورهای فدراسیون")
        ordering = ("name",)

    def __str__(self):
        return self.name


class RemoteCamera(models.Model):
    """Cached snapshot of a camera living on a federated server."""

    server = models.ForeignKey(
        FederatedServer, on_delete=models.CASCADE, related_name="remote_cameras"
    )
    remote_id = models.PositiveIntegerField()
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=10, default="unknown")
    webrtc_url = models.CharField(max_length=400, blank=True, default="")
    hls_url = models.CharField(max_length=400, blank=True, default="")

    class Meta:
        unique_together = ("server", "remote_id")

    def __str__(self):
        return f"{self.server.name}:{self.name}"
