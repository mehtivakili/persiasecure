"""
Access control: doors, cardholders, credentials, rules and access events.

A Door is a physical access point wired to a controller (reachable over HTTP
for lock/unlock in this build; OSDP/Wiegand controllers plug into
controller.py). Cardholders own Credentials (card / PIN / plate). AccessRules
bind a cardholder to a door with an optional weekly schedule. Every decision is
recorded as an AccessEvent and can raise a VMS Event/alarm.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Organization
from apps.cameras.models import Camera


class Door(models.Model):
    class State(models.TextChoices):
        LOCKED = "locked", _("قفل")
        UNLOCKED = "unlocked", _("باز")
        HELD = "held", _("نگه‌داشته باز")
        OFFLINE = "offline", _("آفلاین")

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="doors"
    )
    name = models.CharField(_("نام در"), max_length=120)
    location = models.CharField(max_length=255, blank=True, default="")
    controller_url = models.CharField(max_length=300, blank=True, default="")
    relay = models.PositiveIntegerField(default=1)
    unlock_seconds = models.PositiveIntegerField(default=5)
    state = models.CharField(max_length=10, choices=State.choices, default=State.LOCKED)
    # Optional camera at the door for video verification.
    camera = models.ForeignKey(
        Camera, on_delete=models.SET_NULL, null=True, blank=True, related_name="doors"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("در")
        verbose_name_plural = _("درها")
        ordering = ("name",)

    def __str__(self):
        return self.name


class Cardholder(models.Model):
    class Kind(models.TextChoices):
        EMPLOYEE = "employee", _("کارمند")
        VISITOR = "visitor", _("مهمان")
        CONTRACTOR = "contractor", _("پیمانکار")

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="cardholders"
    )
    first_name = models.CharField(_("نام"), max_length=80)
    last_name = models.CharField(_("نام خانوادگی"), max_length=80)
    employee_id = models.CharField(max_length=40, blank=True, default="")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.EMPLOYEE)
    # Visitor management: access window + who is being visited.
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    host = models.CharField(_("میزبان"), max_length=120, blank=True, default="")
    active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to="cardholders/", null=True, blank=True)

    @property
    def is_valid_now(self):
        from django.utils import timezone

        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return self.active

    class Meta:
        verbose_name = _("دارندهٔ کارت")
        verbose_name_plural = _("دارندگان کارت")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Credential(models.Model):
    class Kind(models.TextChoices):
        CARD = "card", _("کارت")
        PIN = "pin", _("رمز")
        PLATE = "plate", _("پلاک خودرو")

    cardholder = models.ForeignKey(
        Cardholder, on_delete=models.CASCADE, related_name="credentials"
    )
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.CARD)
    value = models.CharField(max_length=64, db_index=True)  # card number / pin / plate
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("kind", "value")

    def __str__(self):
        return f"{self.get_kind_display()}: {self.value}"


class AccessRule(models.Model):
    door = models.ForeignKey(Door, on_delete=models.CASCADE, related_name="rules")
    cardholder = models.ForeignKey(
        Cardholder, on_delete=models.CASCADE, related_name="rules"
    )
    allowed = models.BooleanField(default=True)
    # weekly[<0-6>] = [{"from":"HH:MM","to":"HH:MM"}]; empty = always
    weekly = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("door", "cardholder")

    def __str__(self):
        return f"{self.cardholder} @ {self.door}"


class AccessEvent(models.Model):
    class Decision(models.TextChoices):
        GRANTED = "granted", _("مجاز")
        DENIED = "denied", _("غیرمجاز")

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="access_events"
    )
    door = models.ForeignKey(Door, on_delete=models.CASCADE, related_name="events")
    cardholder = models.ForeignKey(
        Cardholder, on_delete=models.SET_NULL, null=True, blank=True
    )
    credential_value = models.CharField(max_length=64, blank=True, default="")
    decision = models.CharField(max_length=8, choices=Decision.choices)
    reason = models.CharField(max_length=120, blank=True, default="")
    ts = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("رویداد تردد")
        verbose_name_plural = _("رویدادهای تردد")
        ordering = ("-ts",)

    def __str__(self):
        return f"{self.door} — {self.get_decision_display()}"
