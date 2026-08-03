"""
Video analytics: rules + detection results (ALPR plate reads, object detections).

A rule attaches an analytics kind (motion / object / alpr) to a camera with a
JSON config (sensitivity, detection zones as polygons, object classes, plate
country/whitelist). Workers in tasks.py run the detector and persist results
here plus raise an Event so alarms surface in the normal alarm feed.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Organization
from apps.cameras.models import Camera


class AnalyticsRule(models.Model):
    class Kind(models.TextChoices):
        MOTION = "motion", _("حرکت")
        OBJECT = "object", _("تشخیص شیء")
        ALPR = "alpr", _("پلاک خودرو")
        FIRE = "fire", _("آتش")
        SMOKE = "smoke", _("دود")
        TRIPWIRE = "tripwire", _("عبور از خط")

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="analytics_rules"
    )
    camera = models.ForeignKey(
        Camera, on_delete=models.CASCADE, related_name="analytics_rules"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    enabled = models.BooleanField(default=True)
    # Free-form detector config: {sensitivity, zones:[[[x,y],...]], classes:[...],
    #   country, min_confidence, interval_seconds}
    config = models.JSONField(default=dict, blank=True)
    interval_seconds = models.PositiveIntegerField(default=15)

    class Meta:
        verbose_name = _("قانون تحلیل")
        verbose_name_plural = _("قوانین تحلیل")
        unique_together = ("camera", "kind")

    def __str__(self):
        return f"{self.camera.name} — {self.get_kind_display()}"


class PlateRead(models.Model):
    """A single license-plate recognition result."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="plate_reads"
    )
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="plate_reads")
    plate = models.CharField(max_length=32, db_index=True)
    confidence = models.FloatField(default=0)
    country = models.CharField(max_length=8, blank=True, default="ir")
    snapshot = models.ImageField(upload_to="plates/", null=True, blank=True)
    watchlist_hit = models.BooleanField(default=False)
    event = models.ForeignKey(
        "events.Event", on_delete=models.SET_NULL, null=True, blank=True
    )
    ts = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("خواندن پلاک")
        verbose_name_plural = _("خواندن‌های پلاک")
        ordering = ("-ts",)

    def __str__(self):
        return f"{self.plate} ({self.confidence:.0f}%)"


class ObjectDetection(models.Model):
    """A single object-detection result (person, car, ...)."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="object_detections"
    )
    camera = models.ForeignKey(
        Camera, on_delete=models.CASCADE, related_name="object_detections"
    )
    label = models.CharField(max_length=40, db_index=True)
    confidence = models.FloatField(default=0)
    bbox = models.JSONField(default=list, blank=True)  # [x, y, w, h] normalized
    snapshot = models.ImageField(upload_to="objects/", null=True, blank=True)
    event = models.ForeignKey(
        "events.Event", on_delete=models.SET_NULL, null=True, blank=True
    )
    ts = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("تشخیص شیء")
        verbose_name_plural = _("تشخیص‌های شیء")
        ordering = ("-ts",)

    def __str__(self):
        return f"{self.label} ({self.confidence:.0f}%)"


class MotionHeatmap(models.Model):
    """
    Per-camera, per-day accumulation of WHERE motion happens, on a coarse
    GRID_W×GRID_H grid (KiwiVision-style heatmap). Workers add each frame
    diff's per-cell activity; the API sums a date range for display.
    """

    GRID_W = 32
    GRID_H = 18

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="heatmaps"
    )
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="heatmaps")
    date = models.DateField(db_index=True)
    # grid[row][col] = accumulated activity (ints)
    grid = models.JSONField(default=list, blank=True)
    samples = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("camera", "date")
        verbose_name = _("نقشه حرارتی حرکت")
        verbose_name_plural = _("نقشه‌های حرارتی حرکت")

    def __str__(self):
        return f"{self.camera.name} — {self.date}"


class PlateWatchlist(models.Model):
    """Plates of interest — a match raises a critical alarm."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="plate_watchlist"
    )
    plate = models.CharField(max_length=32, db_index=True)
    reason = models.CharField(max_length=255, blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "plate")

    def __str__(self):
        return self.plate
