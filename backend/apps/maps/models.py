"""
Site maps / floor plans with placed markers.

A SiteMap holds a floor-plan image; MapMarkers place cameras or doors on it at
normalized (0..1) x/y coordinates so the frontend can overlay clickable icons
that open live video or unlock a door.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Organization


class SiteMap(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="maps"
    )
    name = models.CharField(_("نام نقشه"), max_length=120)
    image = models.ImageField(upload_to="maps/")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("نقشه")
        verbose_name_plural = _("نقشه‌ها")
        ordering = ("order", "name")

    def __str__(self):
        return self.name


class MapMarker(models.Model):
    class Kind(models.TextChoices):
        CAMERA = "camera", _("دوربین")
        DOOR = "door", _("در")

    site_map = models.ForeignKey(SiteMap, on_delete=models.CASCADE, related_name="markers")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    object_id = models.PositiveIntegerField()  # Camera.id or Door.id
    label = models.CharField(max_length=120, blank=True, default="")
    x = models.FloatField(default=0.5)  # 0..1 normalized
    y = models.FloatField(default=0.5)
    rotation = models.FloatField(default=0)  # camera field-of-view direction (deg)

    class Meta:
        verbose_name = _("نشانگر نقشه")
        verbose_name_plural = _("نشانگرهای نقشه")

    def __str__(self):
        return f"{self.get_kind_display()} #{self.object_id} @ {self.site_map.name}"
