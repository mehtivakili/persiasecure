"""
Smart Desk saved layouts (Genetec Security Desk "saved views" / Milestone
Smart Client "views").

A layout is a named arrangement of tiles for one operator: which entity
(camera / door / map) sits in which tile of an N-tile grid. Layouts are
personal — they follow the user to any workstation.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Organization, User


class DeskLayout(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="desk_layouts"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="desk_layouts")
    name = models.CharField(_("نام چیدمان"), max_length=120)
    # Number of tiles in the grid: 1 | 4 | 9 | 16
    tile_count = models.PositiveSmallIntegerField(default=4)
    # tiles = [{"index": 0, "kind": "camera"|"door"|"map", "object_id": 3}, ...]
    tiles = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("چیدمان میز هوشمند")
        verbose_name_plural = _("چیدمان‌های میز هوشمند")
        unique_together = ("user", "name")
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.user})"
