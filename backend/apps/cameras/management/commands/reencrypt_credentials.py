"""
Re-encrypt every stored credential with the CURRENT ``CREDENTIAL_ENCRYPTION_KEY``.

Two uses (Phase 6 operations):
  * Migrate legacy plaintext rows into encrypted form (no ``--old-key``).
  * Rotate the encryption key: set the NEW key in ``.env``, then run with
    ``--old-key <previous-key>`` so each value is decrypted with the old key and
    re-encrypted with the new one.

Covers camera RTSP passwords and notification provider secrets.
"""
from django.core.management.base import BaseCommand
from django.db import connection

from apps.cameras import crypto


def _plaintext(raw, old_fernet):
    if not raw:
        return ""
    if old_fernet is not None:
        return crypto.decrypt_with(old_fernet, raw)
    # No old key: legacy plaintext stays as-is; current-key ciphertext decrypts.
    return crypto.decrypt(raw) if crypto.is_encrypted(raw) else raw


class Command(BaseCommand):
    help = "Re-encrypt stored credentials with the current key (use --old-key to rotate)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--old-key",
            default=None,
            help="Previous CREDENTIAL_ENCRYPTION_KEY, when rotating to a new key.",
        )

    def handle(self, *args, **options):
        from apps.cameras.models import Camera
        from apps.events.models import NotificationSettings

        old_fernet = crypto.fernet_from_key(options["old_key"]) if options["old_key"] else None
        count = 0

        with connection.cursor() as cur:
            cur.execute("SELECT id, password FROM cameras_camera")
            camera_rows = cur.fetchall()
        for cam_id, raw in camera_rows:
            if not raw:
                continue
            # .update() runs the field's get_prep_value → encrypts with the
            # current key; we never load the ORM object (which would try to
            # decrypt with the wrong key during rotation).
            Camera.objects.filter(id=cam_id).update(password=_plaintext(raw, old_fernet))
            count += 1

        with connection.cursor() as cur:
            cur.execute(
                "SELECT id, kavenegar_api_key, twilio_token FROM events_notificationsettings"
            )
            ns_rows = cur.fetchall()
        for ns_id, api_key, token in ns_rows:
            updates = {}
            if api_key:
                updates["kavenegar_api_key"] = _plaintext(api_key, old_fernet)
            if token:
                updates["twilio_token"] = _plaintext(token, old_fernet)
            if updates:
                NotificationSettings.objects.filter(id=ns_id).update(**updates)
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Re-encrypted credentials for {count} row(s)."))
