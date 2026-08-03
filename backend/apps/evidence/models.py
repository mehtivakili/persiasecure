"""
Evidence management with chain-of-custody.

An EvidenceCase groups EvidenceItems (recordings, exported clips, snapshots or
notes). Each item stores a SHA-256 hash of its file so tampering is detectable.
Every meaningful action (create case, add item, export, close) appends an
immutable CustodyLog entry — the audit trail a court needs.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Organization, User
from apps.cameras.models import Camera
from apps.recordings.models import Recording


class EvidenceCase(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("باز")
        CLOSED = "closed", _("بسته")
        ARCHIVED = "archived", _("بایگانی")

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="evidence_cases"
    )
    case_number = models.CharField(max_length=40, unique=True)
    title = models.CharField(_("عنوان پرونده"), max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("پروندهٔ مدارک")
        verbose_name_plural = _("پرونده‌های مدارک")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.case_number} — {self.title}"


class EvidenceItem(models.Model):
    class Kind(models.TextChoices):
        RECORDING = "recording", _("ضبط")
        EXPORT = "export", _("خروجی")
        SNAPSHOT = "snapshot", _("عکس")
        NOTE = "note", _("یادداشت")

    case = models.ForeignKey(EvidenceCase, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True)
    recording = models.ForeignKey(
        Recording, on_delete=models.SET_NULL, null=True, blank=True
    )
    file_path = models.CharField(max_length=500, blank=True, default="")
    sha256 = models.CharField(max_length=64, blank=True, default="")
    note = models.TextField(blank=True, default="")
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("added_at",)

    def __str__(self):
        return f"{self.get_kind_display()} @ {self.case.case_number}"


class CustodyLog(models.Model):
    """Immutable chain-of-custody entry."""

    case = models.ForeignKey(EvidenceCase, on_delete=models.CASCADE, related_name="custody")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=80)  # created / item_added / exported / closed
    note = models.CharField(max_length=255, blank=True, default="")
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("ts",)

    def __str__(self):
        return f"{self.action} @ {self.ts:%Y-%m-%d %H:%M}"
