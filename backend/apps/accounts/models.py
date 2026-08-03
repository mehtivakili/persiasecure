"""
Accounts, tenancy and RBAC.

Modelled on Shinobi's group-key (`ke`) multi-tenant idea: every record in the
system belongs to an Organization. Users have a Role, and Roles carry a set of
permission codenames that the frontend and API permission classes check.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Organization(models.Model):
    """A tenant. Cameras, recordings, users and events all belong to one."""

    name = models.CharField(_("نام سازمان"), max_length=120)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    # Genetec-style org-wide threat level; automation rules can react to it and
    # the UI shows it in the app bar. Choices defined in THREAT_LEVELS below.
    threat_level = models.CharField(max_length=8, default="green")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("سازمان")
        verbose_name_plural = _("سازمان‌ها")

    def __str__(self):
        return self.name


# Canonical permission codenames used across the app (checked by RolePermission).
PERMISSION_CHOICES = [
    ("camera.view", _("مشاهده دوربین‌ها")),
    ("camera.manage", _("مدیریت دوربین‌ها")),
    ("liveview.view", _("مشاهده زنده")),
    ("playback.view", _("بازپخش ضبط‌ها")),
    ("playback.export", _("خروجی گرفتن از ضبط‌ها")),
    ("ptz.control", _("کنترل PTZ")),
    ("event.view", _("مشاهده رویدادها")),
    ("event.ack", _("تأیید و رفع هشدارها")),
    ("user.manage", _("مدیریت کاربران و نقش‌ها")),
    ("settings.manage", _("مدیریت تنظیمات سامانه")),
    # Phase 2 — analytics / access control / maps / federation / evidence
    ("analytics.view", _("مشاهده تحلیل تصویر و پلاک‌خوان")),
    ("analytics.manage", _("مدیریت قوانین تحلیل تصویر")),
    ("access.view", _("مشاهده کنترل تردد")),
    ("access.manage", _("مدیریت درها و کارت‌ها")),
    ("map.view", _("مشاهده نقشه‌ها")),
    ("map.manage", _("مدیریت نقشه‌ها")),
    ("federation.manage", _("مدیریت سرورهای فدراسیون")),
    ("evidence.view", _("مشاهده پرونده‌های مدارک")),
    ("evidence.manage", _("مدیریت پرونده‌های مدارک")),
    # Genetec-style operations features
    ("report.view", _("گزارش‌گیری")),
    ("automation.manage", _("مدیریت خودکارسازی (رویداد→عملیات)")),
    ("system.view", _("پایش سلامت سامانه")),
    ("threat.manage", _("تغییر سطح تهدید")),
]

THREAT_LEVELS = [
    ("green", _("عادی")),
    ("yellow", _("هشدار")),
    ("red", _("بحرانی")),
]


class Role(models.Model):
    """A named set of permissions within an organization."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="roles"
    )
    name = models.CharField(_("نام نقش"), max_length=80)
    description = models.CharField(max_length=255, blank=True, default="")
    # List of permission codenames from PERMISSION_CHOICES.
    permissions = models.JSONField(default=list, blank=True)
    is_system = models.BooleanField(default=False)  # built-in roles (admin/operator/viewer)

    class Meta:
        verbose_name = _("نقش")
        verbose_name_plural = _("نقش‌ها")
        unique_together = ("organization", "name")

    def __str__(self):
        return f"{self.name} ({self.organization.slug})"

    def has_perm(self, codename):
        return codename in (self.permissions or [])


class User(AbstractUser):
    """Custom user tied to an Organization and a Role."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )
    role = models.ForeignKey(
        Role, on_delete=models.SET_NULL, null=True, blank=True, related_name="users"
    )
    display_name = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")

    def get_permissions(self):
        if self.is_superuser:
            return [code for code, _label in PERMISSION_CHOICES]
        if self.role:
            return self.role.permissions or []
        return []

    def has_vms_perm(self, codename):
        return self.is_superuser or (self.role and self.role.has_perm(codename))


class AuditLog(models.Model):
    """Immutable trail of who did what."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="audit_logs", null=True
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=120)  # e.g. "camera.create"
    target = models.CharField(max_length=255, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("رویداد ممیزی")
        verbose_name_plural = _("رویدادهای ممیزی")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


def log_action(request, action, target="", **detail):
    """Helper to write an AuditLog row from a DRF request."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        user = None
    AuditLog.objects.create(
        organization=getattr(user, "organization", None) if user else None,
        user=user,
        action=action,
        target=str(target),
        ip=_client_ip(request),
        detail=detail,
    )


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
