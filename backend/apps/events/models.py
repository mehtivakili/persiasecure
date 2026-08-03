"""
Events / alarms and bookmarks.

An Event is any notable occurrence: motion, ALPR hit, object detection,
camera offline or tampering. Operators acknowledge and clear alarms; the
frontend receives new events in real time over the WebSocket consumer.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Organization, User
from apps.cameras.fields import EncryptedCharField
from apps.cameras.models import Camera


class EventType(models.TextChoices):
    MOTION = "motion", _("حرکت")
    ALPR = "alpr", _("پلاک خودرو")
    OBJECT = "object", _("تشخیص شیء")
    FIRE = "fire", _("آتش")
    SMOKE = "smoke", _("دود")
    TRIPWIRE = "tripwire", _("عبور از خط")
    OFFLINE = "offline", _("قطع ارتباط")
    TAMPER = "tamper", _("دستکاری")
    MANUAL = "manual", _("دستی")
    STORAGE = "storage", _("فضای ذخیره‌سازی")


class Severity(models.TextChoices):
    INFO = "info", _("اطلاع")
    WARNING = "warning", _("هشدار")
    CRITICAL = "critical", _("بحرانی")


class Event(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="events"
    )
    camera = models.ForeignKey(
        Camera, on_delete=models.CASCADE, related_name="events", null=True, blank=True
    )
    type = models.CharField(max_length=12, choices=EventType.choices)
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.INFO
    )
    details = models.JSONField(default=dict, blank=True)
    snapshot = models.ImageField(upload_to="events/", null=True, blank=True)
    ts = models.DateTimeField(auto_now_add=True, db_index=True)

    # Alarm lifecycle
    acknowledged = models.BooleanField(default=False)
    ack_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="acked_events"
    )
    ack_at = models.DateTimeField(null=True, blank=True)
    cleared = models.BooleanField(default=False)
    # Investigation (Phase 5): who owns following this alarm up.
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_events"
    )

    class Meta:
        verbose_name = _("رویداد")
        verbose_name_plural = _("رویدادها")
        ordering = ("-ts",)
        indexes = [models.Index(fields=["organization", "-ts"])]

    def __str__(self):
        return f"{self.get_type_display()} @ {self.ts:%Y-%m-%d %H:%M}"


class EventComment(models.Model):
    """An operator note on an event during investigation (Phase 5)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    text = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"comment on evt#{self.event_id}"


SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


class AutomationRule(models.Model):
    """
    Genetec-style event-to-action rule: when an Event matching the trigger is
    created, run the configured action. Executed asynchronously by
    apps.events.tasks.run_automation (wired via post_save signal).
    """

    class Action(models.TextChoices):
        WEBHOOK = "webhook", _("فراخوانی وب‌هوک")
        UNLOCK_DOOR = "unlock_door", _("بازکردن در")
        LOCK_DOOR = "lock_door", _("قفل‌کردن در")
        SET_THREAT = "set_threat", _("تغییر سطح تهدید")
        SEND_SMS = "send_sms", _("ارسال پیامک")
        VOICE_CALL = "voice_call", _("تماس صوتی")

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="automation_rules"
    )
    name = models.CharField(_("نام قانون"), max_length=120)
    enabled = models.BooleanField(default=True)
    # Trigger filters — blank/null means "any".
    event_type = models.CharField(max_length=12, blank=True, default="")
    min_severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.INFO
    )
    camera = models.ForeignKey(
        Camera, on_delete=models.CASCADE, null=True, blank=True,
        related_name="automation_rules",
    )
    # Action + parameters ({url} | {door} | {level}).
    action = models.CharField(max_length=16, choices=Action.choices)
    params = models.JSONField(default=dict, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("قانون خودکارسازی")
        verbose_name_plural = _("قوانین خودکارسازی")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def matches(self, event):
        if not self.enabled:
            return False
        if self.event_type and event.type != self.event_type:
            return False
        if self.camera_id and event.camera_id != self.camera_id:
            return False
        return SEVERITY_ORDER.get(event.severity, 0) >= SEVERITY_ORDER.get(
            self.min_severity, 0
        )


class Bookmark(models.Model):
    """A named marker on a camera's timeline (for later review)."""

    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="bookmarks")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-start",)

    def __str__(self):
        return f"{self.camera.name}: {self.note}"


class NotificationSettings(models.Model):
    """
    Per-organization notification config edited in the Settings panel:
    the SMS/voice provider + credentials, and the list of recipient phone
    numbers that receive alarm SMS/calls. apps.events.notify reads this
    (falling back to the .env defaults for any blank field).
    """

    class Provider(models.TextChoices):
        CONSOLE = "console", _("فقط ثبت در لاگ (بدون حساب)")
        KAVENEGAR = "kavenegar", _("کاوه‌نگار (ایران)")
        TWILIO = "twilio", _("Twilio (بین‌المللی)")

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="notification_settings"
    )
    provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.CONSOLE
    )
    # Provider secrets are encrypted at rest (Phase 6, issue #10).
    kavenegar_api_key = EncryptedCharField(max_length=500, blank=True, default="")
    sms_sender = models.CharField(max_length=40, blank=True, default="")
    twilio_sid = models.CharField(max_length=100, blank=True, default="")
    twilio_token = EncryptedCharField(max_length=500, blank=True, default="")
    twilio_from = models.CharField(max_length=40, blank=True, default="")
    # recipients = [{"name": str, "phone": str, "sms": bool, "call": bool, "active": bool}]
    recipients = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("تنظیمات اعلان")
        verbose_name_plural = _("تنظیمات اعلان‌ها")

    def __str__(self):
        return f"Notifications ({self.organization.slug})"
