"""
Camera / device model set.

Maps Shinobi's Monitor `details` JSON onto explicit fields: connection
(protocol/host/port/path + credentials), stream & record codecs, PTZ control
and detector settings. A Camera has one or more StreamProfiles (main/sub),
optional PTZ presets, and belongs to CameraGroups used to build grid views.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Organization

from .fields import EncryptedCharField


class CameraStatus(models.TextChoices):
    ONLINE = "online", _("آنلاین")
    OFFLINE = "offline", _("آفلاین")
    UNKNOWN = "unknown", _("نامشخص")
    DISABLED = "disabled", _("غیرفعال")


class Camera(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="cameras"
    )
    name = models.CharField(_("نام دوربین"), max_length=120)
    location = models.CharField(_("محل نصب"), max_length=255, blank=True, default="")
    enabled = models.BooleanField(_("فعال"), default=True)

    # Connection — either a full rtsp_url or assembled from parts.
    protocol = models.CharField(max_length=10, default="rtsp")
    host = models.CharField(max_length=255, blank=True, default="")
    port = models.PositiveIntegerField(default=554)
    path = models.CharField(max_length=255, blank=True, default="/")
    rtsp_url = models.CharField(
        _("آدرس کامل RTSP"), max_length=500, blank=True, default=""
    )
    username = models.CharField(max_length=120, blank=True, default="")
    # Fernet‑encrypted at rest (see apps.cameras.crypto). max_length is sized for
    # the ciphertext, not the plaintext password.
    password = EncryptedCharField(max_length=500, blank=True, default="")

    # ONVIF (discovery / PTZ)
    onvif_host = models.CharField(max_length=255, blank=True, default="")
    onvif_port = models.PositiveIntegerField(default=80)
    onvif_enabled = models.BooleanField(default=False)

    manufacturer = models.CharField(max_length=120, blank=True, default="")
    model = models.CharField(max_length=120, blank=True, default="")

    # Runtime status (updated by health-check task).
    status = models.CharField(
        max_length=10, choices=CameraStatus.choices, default=CameraStatus.UNKNOWN
    )
    last_seen = models.DateTimeField(null=True, blank=True)

    ptz_enabled = models.BooleanField(default=False)
    thumbnail = models.ImageField(upload_to="thumbnails/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("دوربین")
        verbose_name_plural = _("دوربین‌ها")
        ordering = ("name",)

    def __str__(self):
        return self.name

    @property
    def is_recording(self):
        sched = getattr(self, "schedule", None)
        return bool(sched and sched.mode != "off")


class VideoCodec(models.TextChoices):
    H264 = "h264", _("H.264 / AVC")
    H265 = "h265", _("H.265 / HEVC (و H.265+)")


class StreamProfile(models.Model):
    class Kind(models.TextChoices):
        MAIN = "main", _("جریان اصلی")
        SUB = "sub", _("جریان فرعی")

    camera = models.ForeignKey(
        Camera, on_delete=models.CASCADE, related_name="stream_profiles"
    )
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.MAIN)
    # h264 plays natively in the browser; h265/HEVC (incl. Hikvision/Dahua
    # "H.265+") is recorded natively but transcoded on-demand for live view.
    codec = models.CharField(max_length=20, choices=VideoCodec.choices, default=VideoCodec.H264)
    resolution = models.CharField(max_length=20, default="1280x720")
    fps = models.PositiveIntegerField(default=25)
    bitrate_kbps = models.PositiveIntegerField(default=0)  # 0 = camera default
    rtsp_transport = models.CharField(max_length=8, default="tcp")

    class Meta:
        unique_together = ("camera", "kind")

    def __str__(self):
        return f"{self.camera.name} — {self.get_kind_display()}"


class PtzPreset(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="ptz_presets")
    name = models.CharField(max_length=80)
    token = models.CharField(max_length=80, blank=True, default="")  # ONVIF preset token

    class Meta:
        unique_together = ("camera", "name")

    def __str__(self):
        return f"{self.camera.name}: {self.name}"


class CameraGroup(models.Model):
    """A saved set of cameras (used for grid/mosaic views)."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="camera_groups"
    )
    name = models.CharField(max_length=120)
    cameras = models.ManyToManyField(Camera, blank=True, related_name="groups")
    layout = models.CharField(max_length=10, default="2x2")  # 1x1,2x2,3x3,4x4

    class Meta:
        verbose_name = _("گروه دوربین")
        verbose_name_plural = _("گروه‌های دوربین")

    def __str__(self):
        return self.name
