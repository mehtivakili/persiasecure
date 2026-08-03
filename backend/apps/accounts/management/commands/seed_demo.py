"""
Idempotent demo seeder:
  - default Organization
  - three system Roles (admin / operator / viewer)
  - a superuser (from env) attached to the org + admin role
  - a demo camera pointing at a public RTSP test stream
  - a continuous recording schedule for that camera

Safe to run on every container start.
"""
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import PERMISSION_CHOICES, Organization, Role, User

ALL_PERMS = [c for c, _ in PERMISSION_CHOICES]
OPERATOR_PERMS = [
    "camera.view",
    "liveview.view",
    "playback.view",
    "playback.export",
    "ptz.control",
    "event.view",
    "event.ack",
    "analytics.view",
    "access.view",
    "map.view",
    "evidence.view",
    "evidence.manage",
    "report.view",
    "system.view",
]
VIEWER_PERMS = [
    "camera.view",
    "liveview.view",
    "playback.view",
    "event.view",
    "analytics.view",
    "map.view",
]


class Command(BaseCommand):
    help = "Seed default org, roles, superuser and a demo camera."

    @transaction.atomic
    def handle(self, *args, **options):
        org, _ = Organization.objects.get_or_create(
            slug="default", defaults={"name": "سازمان پیش‌فرض"}
        )

        roles = {
            "admin": ("مدیر سامانه", ALL_PERMS),
            "operator": ("اپراتور", OPERATOR_PERMS),
            "viewer": ("ناظر", VIEWER_PERMS),
        }
        role_objs = {}
        for key, (name, perms) in roles.items():
            role, _ = Role.objects.get_or_create(
                organization=org,
                name=name,
                defaults={"permissions": perms, "is_system": True},
            )
            # keep permissions in sync for system roles
            if role.is_system and role.permissions != perms:
                role.permissions = perms
                role.save(update_fields=["permissions"])
            role_objs[key] = role

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin12345")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@persiansecure.local")
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "organization": org,
                "role": role_objs["admin"],
                "display_name": "مدیر سامانه",
            },
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created."))
        else:
            # Ensure org/role are set even if user pre-existed.
            changed = False
            if user.organization_id is None:
                user.organization = org
                changed = True
            if user.role_id is None:
                user.role = role_objs["admin"]
                changed = True
            if changed:
                user.save()

        self._seed_demo_camera(org)
        self.stdout.write(self.style.SUCCESS("Demo seed complete."))

    def _seed_demo_camera(self, org):
        # Imported here to avoid app-loading order issues.
        from apps.analytics.models import AnalyticsRule, PlateWatchlist
        from apps.cameras.models import Camera, StreamProfile
        from apps.mediactl import client as media_client
        from apps.recordings.models import RecordingSchedule

        # The test-video compose service publishes a synthetic stream (with
        # hard scene cuts, so real ffmpeg motion detection fires) to MediaMTX.
        demo_url = "rtsp://mediamtx:8554/test_video"

        cam, created = Camera.objects.get_or_create(
            organization=org,
            name="دوربین نمونه",
            defaults={
                "protocol": "rtsp",
                "host": "mediamtx",
                "port": 8554,
                "path": "/test_video",
                "rtsp_url": demo_url,
                "manufacturer": "Demo",
                "model": "TestPattern",
                "enabled": True,
            },
        )
        if created:
            StreamProfile.objects.create(
                camera=cam,
                kind="main",
                codec="h264",
                resolution="1280x720",
                fps=25,
            )
            RecordingSchedule.objects.create(
                camera=cam,
                mode="continuous",
                retention_days=7,
                segment_seconds=60,
            )
            self.stdout.write(self.style.SUCCESS("Demo camera created."))
        elif cam.rtsp_url != demo_url:
            # Migrate pre-existing installs off the old public placeholder URL.
            cam.rtsp_url = demo_url
            cam.host, cam.port, cam.path = "mediamtx", 8554, "/test_video"
            cam.save(update_fields=["rtsp_url", "host", "port", "path"])
            self.stdout.write(self.style.SUCCESS("Demo camera repointed to test_video."))

        # Analytics rules: real motion + tripwire detection, demo-mode
        # ALPR/object/fire/smoke so every alarm pipeline can be tested before
        # real models/cameras arrive. The tripwire is a vertical line at the
        # center of the frame — exactly where the test video's intruder passes.
        rules = [
            ("motion", {}),
            ("tripwire", {"line": [[0.5, 0.1], [0.5, 0.95]], "sensitivity": 6.0}),
            ("fire", {"demo": True, "demo_rate": 0.1}),
            ("smoke", {"demo": True, "demo_rate": 0.1}),
            ("alpr", {"demo": True, "country": "ir"}),
            ("object", {"demo": True}),
        ]
        for kind, config in rules:
            rule, r_created = AnalyticsRule.objects.get_or_create(
                camera=cam,
                kind=kind,
                defaults={"organization": org, "config": config, "interval_seconds": 20},
            )
            if r_created:
                self.stdout.write(self.style.SUCCESS(f"Analytics rule '{kind}' created."))

        # Notification settings + recipient phone (edited later in the Settings
        # panel). SMS_PROVIDER=console logs messages; set a real provider there.
        from apps.events.models import AutomationRule, NotificationSettings

        admin_phone = os.environ.get("ALARM_PHONE", "+989120000000")
        ns, _ = NotificationSettings.objects.get_or_create(organization=org)
        if not ns.recipients:
            ns.recipients = [
                {"name": "مدیر سامانه", "phone": admin_phone, "sms": True, "call": False, "active": True}
            ]
            ns.save(update_fields=["recipients"])

        # SMS alarms (Genetec-style event-to-action): fire/smoke/tripwire →
        # پیامک. Empty params ⇒ fan out to every recipient in Settings.
        sms_rules = [
            ("پیامک هشدار آتش", "fire"),
            ("پیامک هشدار دود", "smoke"),
            ("پیامک عبور از خط", "tripwire"),
        ]
        for name, etype in sms_rules:
            AutomationRule.objects.get_or_create(
                organization=org,
                name=name,
                defaults={
                    "event_type": etype,
                    "min_severity": "info",
                    "action": "send_sms",
                    "params": {},
                    "enabled": True,
                },
            )

        # A watchlist plate matching one demo plate → produces critical alarms.
        PlateWatchlist.objects.get_or_create(
            organization=org,
            plate="12ب34567",
            defaults={"reason": "خودروی تحت تعقیب (نمونه)", "active": True},
        )

        # Push/update the MediaMTX path (no-op if the media server is not up yet).
        sched = getattr(cam, "schedule", None)
        media_client.sync_camera_path(
            cam,
            record=cam.is_recording,
            segment_seconds=sched.segment_seconds if sched else 60,
        )
