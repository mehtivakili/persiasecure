from unittest import mock

from django.db import connection
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, Role, User
from apps.cameras import crypto
from apps.cameras.models import Camera
from apps.mediactl import client as media_client
from apps.mediactl import ffmpeg
from apps.recordings.models import RecordingSchedule


class MediaCtlTests(APITestCase):
    def test_path_name_and_source_url(self):
        org = Organization.objects.create(name="O", slug="o")
        cam = Camera.objects.create(
            organization=org, name="c", host="1.2.3.4", port=554, path="/s",
            username="u", password="p",
        )
        self.assertEqual(media_client.path_name_for(cam), f"cam_{cam.id}")
        self.assertEqual(
            media_client.build_source_url(cam), "rtsp://u:p@1.2.3.4:554/s"
        )
        # Structured fields remain authoritative so a stale full URL cannot
        # silently override edited host/path/credentials.
        cam.rtsp_url = "rtsp://example/stream"
        self.assertEqual(
            media_client.build_source_url(cam), "rtsp://u:p@1.2.3.4:554/s"
        )

    def test_playback_urls_shape(self):
        org = Organization.objects.create(name="O", slug="o")
        cam = Camera.objects.create(organization=org, name="c")
        urls = media_client.playback_urls(cam)
        self.assertIn("whep", urls["webrtc"])
        self.assertTrue(urls["hls"].endswith("index.m3u8"))


class CameraOrgScopingTests(APITestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="O1", slug="o1")
        self.org2 = Organization.objects.create(name="O2", slug="o2")
        role = Role.objects.create(
            organization=self.org1, name="r", permissions=["camera.view"]
        )
        self.user = User.objects.create_user(
            username="u", password="pw12345678", organization=self.org1, role=role
        )
        Camera.objects.create(organization=self.org1, name="mine")
        Camera.objects.create(organization=self.org2, name="theirs")

    def test_user_only_sees_own_org_cameras(self):
        res = self.client.post(
            "/api/auth/token/", {"username": "u", "password": "pw12345678"}, format="json"
        )
        token = res.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        with mock.patch.object(media_client, "sync_camera_path", return_value=True):
            res = self.client.get("/api/cameras/")
        self.assertEqual(res.status_code, 200)
        names = [c["name"] for c in res.data["results"]]
        self.assertEqual(names, ["mine"])


class CredentialEncryptionTests(TestCase):
    """Camera passwords must be encrypted at rest (Phase 1, issue #10)."""

    def _raw_password(self, camera_id):
        with connection.cursor() as cur:
            cur.execute("SELECT password FROM cameras_camera WHERE id = %s", [camera_id])
            return cur.fetchone()[0]

    def test_password_encrypted_in_db_but_plaintext_in_python(self):
        org = Organization.objects.create(name="O", slug="o")
        cam = Camera.objects.create(organization=org, name="c", password="s3cr3t")
        stored = self._raw_password(cam.id)
        self.assertTrue(stored.startswith(crypto.PREFIX))
        self.assertNotIn("s3cr3t", stored)
        cam.refresh_from_db()
        self.assertEqual(cam.password, "s3cr3t")

    def test_legacy_plaintext_is_read_unchanged(self):
        org = Organization.objects.create(name="O", slug="o")
        cam = Camera.objects.create(organization=org, name="c", password="x")
        # Simulate a pre‑encryption row: overwrite with raw plaintext.
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE cameras_camera SET password = %s WHERE id = %s", ["oldplain", cam.id]
            )
        cam.refresh_from_db()
        self.assertEqual(cam.password, "oldplain")

    def test_empty_password_stays_empty(self):
        self.assertEqual(crypto.encrypt(""), "")
        self.assertEqual(crypto.decrypt(""), "")


class ReencryptCommandTests(TestCase):
    def _raw_password(self, camera_id):
        with connection.cursor() as cur:
            cur.execute("SELECT password FROM cameras_camera WHERE id = %s", [camera_id])
            return cur.fetchone()[0]

    def test_migrates_legacy_plaintext(self):
        from django.core.management import call_command

        org = Organization.objects.create(name="O", slug="o")
        cam = Camera.objects.create(organization=org, name="c", password="x")
        with connection.cursor() as cur:
            cur.execute("UPDATE cameras_camera SET password=%s WHERE id=%s", ["legacyplain", cam.id])

        call_command("reencrypt_credentials")

        stored = self._raw_password(cam.id)
        self.assertTrue(stored.startswith(crypto.PREFIX))
        cam.refresh_from_db()
        self.assertEqual(cam.password, "legacyplain")

    def test_rotates_from_old_key(self):
        from django.core.management import call_command

        org = Organization.objects.create(name="O", slug="o")
        cam = Camera.objects.create(organization=org, name="c", password="x")
        # Simulate a value encrypted under a PREVIOUS key.
        old = crypto.fernet_from_key("previous-key")
        token = crypto.PREFIX + old.encrypt(b"rotateme").decode("ascii")
        with connection.cursor() as cur:
            cur.execute("UPDATE cameras_camera SET password=%s WHERE id=%s", [token, cam.id])

        call_command("reencrypt_credentials", old_key="previous-key")

        cam.refresh_from_db()  # decrypts with the CURRENT key
        self.assertEqual(cam.password, "rotateme")


class ReconcileCameraPathsTests(TestCase):
    def test_reconciles_only_missing_paths(self):
        from apps.cameras import tasks

        org = Organization.objects.create(name="O", slug="o")
        configured_cam = Camera.objects.create(organization=org, name="a")
        missing_cam = Camera.objects.create(organization=org, name="b")

        def is_configured(cam):
            return cam.id == configured_cam.id  # only the first has a live path

        with mock.patch.object(tasks.media_client, "path_is_configured", side_effect=is_configured), \
                mock.patch("apps.recordings.services.reconcile_recording") as reconcile:
            count = tasks.reconcile_camera_paths()

        self.assertEqual(count, 1)  # only the missing one is re-pushed
        reconcile.assert_called_once()
        self.assertEqual(reconcile.call_args.args[0].id, missing_cam.id)


class AtomicOnboardingTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="O1", slug="o1")
        role = Role.objects.create(
            organization=self.org, name="mgr", permissions=["camera.manage", "camera.view"]
        )
        self.user = User.objects.create_user(
            username="mgr", password="pw12345678", organization=self.org, role=role
        )
        res = self.client.post(
            "/api/auth/token/", {"username": "mgr", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def _payload(self):
        return {
            "name": "Front door",
            "host": "10.0.0.5",
            "port": 554,
            "path": "/stream",
            "username": "admin",
            "password": "hunter2",
            "recording": {"mode": "continuous", "retention_days": 30},
        }

    def test_create_camera_and_schedule_atomically(self):
        with mock.patch.object(media_client, "sync_camera_path", return_value=True):
            res = self.client.post("/api/cameras/", self._payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        # The password is write‑only — it must never be echoed back.
        self.assertNotIn("password", res.data)
        self.assertEqual(res.data["record_mode"], "continuous")
        cam = Camera.objects.get(name="Front door")
        sched = RecordingSchedule.objects.get(camera=cam)
        self.assertEqual(sched.mode, "continuous")
        self.assertEqual(sched.retention_days, 30)

    def test_rollback_when_mediamtx_fails(self):
        with mock.patch.object(media_client, "sync_camera_path", return_value=False), \
                mock.patch.object(media_client, "remove_camera_path", return_value=True):
            res = self.client.post("/api/cameras/", self._payload(), format="json")
        self.assertEqual(res.status_code, 503)
        # Neither the camera nor its schedule may persist.
        self.assertFalse(Camera.objects.filter(name="Front door").exists())
        self.assertEqual(RecordingSchedule.objects.count(), 0)


class ScheduleTenancyTests(APITestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="O1", slug="o1")
        self.org2 = Organization.objects.create(name="O2", slug="o2")
        role = Role.objects.create(
            organization=self.org1, name="mgr", permissions=["camera.manage"]
        )
        self.user = User.objects.create_user(
            username="mgr", password="pw12345678", organization=self.org1, role=role
        )
        self.other_cam = Camera.objects.create(organization=self.org2, name="theirs")
        res = self.client.post(
            "/api/auth/token/", {"username": "mgr", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_cannot_attach_schedule_to_other_org_camera(self):
        res = self.client.post(
            "/api/recording-schedules/",
            {"camera": self.other_cam.id, "mode": "continuous"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("camera", res.data)


class ProbeSourceTests(TestCase):
    """probe_source classifies ffprobe results into actionable reasons."""

    def _run(self, returncode, stdout="", stderr=""):
        fake = mock.Mock(returncode=returncode, stdout=stdout, stderr=stderr)
        with mock.patch.object(ffmpeg.subprocess, "run", return_value=fake):
            return ffmpeg.probe_source("rtsp://host/s")

    def test_ok_supported_codec(self):
        out = self._run(0, stdout='{"streams":[{"codec_name":"h264","width":1920,"height":1080}]}')
        self.assertTrue(out["ok"])
        self.assertEqual(out["reason"], "ok")
        self.assertEqual(out["codec"], "h264")

    def test_unsupported_codec(self):
        out = self._run(0, stdout='{"streams":[{"codec_name":"mjpeg"}]}')
        self.assertFalse(out["ok"])
        self.assertTrue(out["reachable"])
        self.assertEqual(out["reason"], "unsupported_codec")

    def test_auth_failure(self):
        out = self._run(1, stderr="401 Unauthorized")
        self.assertFalse(out["reachable"])
        self.assertEqual(out["reason"], "auth")

    def test_dns_failure(self):
        out = self._run(1, stderr="Failed to resolve hostname: Name or service not known")
        self.assertEqual(out["reason"], "dns")

    def test_timeout(self):
        with mock.patch.object(
            ffmpeg.subprocess, "run",
            side_effect=ffmpeg.subprocess.TimeoutExpired(cmd="ffprobe", timeout=12),
        ):
            out = ffmpeg.probe_source("rtsp://host/s")
        self.assertEqual(out["reason"], "timeout")
