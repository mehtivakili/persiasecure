import os
import shutil
import tempfile
from collections import namedtuple
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, Role, User
from apps.cameras.models import Camera
from apps.events.models import Event
from apps.mediactl import client as media_client
from apps.recordings import services, tasks
from apps.recordings.models import (
    EventClip,
    ExportJob,
    ManualRecordingSession,
    Recording,
    RecordingSchedule,
)


class ShouldRecordTests(APITestCase):
    def setUp(self):
        # Keep tests hermetic and fast: the RecordingSchedule post_save signal
        # (and the services) call MediaMTX; there is none in the test env.
        patcher = mock.patch.object(media_client, "sync_camera_path", return_value=True)
        self.mock_sync = patcher.start()
        self.addCleanup(patcher.stop)
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")

    def test_off_schedule_not_recording(self):
        RecordingSchedule.objects.create(camera=self.cam, mode="off")
        self.assertFalse(services.should_record(self.cam))

    def test_continuous_schedule_records(self):
        RecordingSchedule.objects.create(camera=self.cam, mode="continuous")
        self.assertTrue(services.should_record(self.cam))

    def test_manual_session_overrides_off_schedule(self):
        RecordingSchedule.objects.create(camera=self.cam, mode="off")
        services.start_recording(self.cam, None)
        self.assertTrue(services.should_record(self.cam))
        # MediaMTX was told to record.
        self.assertTrue(self.mock_sync.call_args.kwargs["record"])

    def test_stop_reverts_to_schedule(self):
        RecordingSchedule.objects.create(camera=self.cam, mode="off")
        services.start_recording(self.cam, None)
        self.assertTrue(services.should_record(self.cam))
        services.stop_recording(self.cam, None)
        self.assertFalse(services.should_record(self.cam))
        self.assertEqual(
            ManualRecordingSession.objects.filter(camera=self.cam, status="recording").count(), 0
        )


class RecordingControlApiTests(APITestCase):
    def setUp(self):
        patcher = mock.patch.object(media_client, "sync_camera_path", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org = Organization.objects.create(name="O1", slug="o1")
        role = Role.objects.create(
            organization=self.org, name="mgr", permissions=["camera.manage", "camera.view"]
        )
        User.objects.create_user(
            username="mgr", password="pw12345678", organization=self.org, role=role
        )
        self.cam = Camera.objects.create(organization=self.org, name="c")
        RecordingSchedule.objects.create(camera=self.cam, mode="off")
        res = self.client.post(
            "/api/auth/token/", {"username": "mgr", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_start_status_stop_flow(self):
        r = self.client.post(f"/api/cameras/{self.cam.id}/recording/start/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["recording"])
        self.assertTrue(r.data["manual"])

        s = self.client.get(f"/api/cameras/{self.cam.id}/recording/status/")
        self.assertTrue(s.data["recording"])

        st = self.client.post(f"/api/cameras/{self.cam.id}/recording/stop/")
        self.assertEqual(st.status_code, 200)
        self.assertFalse(st.data["recording"])
        self.assertFalse(st.data["manual"])

    def test_viewer_cannot_start_recording(self):
        viewer_role = Role.objects.create(
            organization=self.org, name="viewer", permissions=["camera.view"]
        )
        User.objects.create_user(
            username="v", password="pw12345678", organization=self.org, role=viewer_role
        )
        res = self.client.post(
            "/api/auth/token/", {"username": "v", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        r = self.client.post(f"/api/cameras/{self.cam.id}/recording/start/")
        self.assertEqual(r.status_code, 403)


class ScheduledModeTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(media_client, "sync_camera_path", return_value=True)
        self.mock_sync = patcher.start()
        self.addCleanup(patcher.stop)
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")

    def _persian_today(self):
        return str(services._persian_index(timezone.localtime()))

    def test_records_inside_window(self):
        # A window covering the whole day always contains "now".
        RecordingSchedule.objects.create(
            camera=self.cam, mode="scheduled",
            weekly={self._persian_today(): [{"from": "00:00", "to": "24:00"}]},
        )
        self.assertTrue(services.should_record(self.cam))

    def test_not_recording_outside_window(self):
        # A window on a different day, empty today → not recording now.
        other = str((services._persian_index(timezone.localtime()) + 3) % 7)
        RecordingSchedule.objects.create(
            camera=self.cam, mode="scheduled",
            weekly={other: [{"from": "00:00", "to": "24:00"}]},
        )
        self.assertFalse(services.should_record(self.cam))

    def test_empty_weekly_records_nothing(self):
        RecordingSchedule.objects.create(camera=self.cam, mode="scheduled", weekly={})
        self.assertFalse(services.should_record(self.cam))

    def test_evaluate_schedules_reconciles(self):
        RecordingSchedule.objects.create(
            camera=self.cam, mode="scheduled",
            weekly={self._persian_today(): [{"from": "00:00", "to": "24:00"}]},
        )
        self.mock_sync.reset_mock()
        count = tasks.evaluate_schedules()
        self.assertEqual(count, 1)
        self.assertTrue(self.mock_sync.call_args.kwargs["record"])


class MotionBufferTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(media_client, "sync_camera_path", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")

    def test_motion_uses_short_segments_and_records(self):
        RecordingSchedule.objects.create(camera=self.cam, mode="motion", segment_seconds=60)
        self.assertTrue(services.should_record(self.cam))
        # Rolling buffer uses short segments, not the 60s schedule value.
        self.assertEqual(services.segment_seconds(self.cam), 6)


class RetentionTests(TestCase):
    def test_protected_segments_survive_retention(self):
        org = Organization.objects.create(name="O", slug="o")
        cam = Camera.objects.create(organization=org, name="c")
        with mock.patch.object(media_client, "sync_camera_path", return_value=True):
            RecordingSchedule.objects.create(camera=cam, mode="continuous", retention_days=1)
        old = timezone.now() - timedelta(days=10)
        keep = Recording.objects.create(
            camera=cam, start=old, file_path="/x/keep.mp4", protected=True
        )
        drop = Recording.objects.create(
            camera=cam, start=old, file_path="/x/drop.mp4", protected=False
        )
        tasks.apply_retention()
        self.assertTrue(Recording.objects.filter(id=keep.id).exists())
        self.assertFalse(Recording.objects.filter(id=drop.id).exists())


class StorageAlarmTests(TestCase):
    def setUp(self):
        cache.delete("storage_alarm_level")
        self.org = Organization.objects.create(name="O", slug="o")

    def test_low_free_space_raises_storage_event(self):
        from apps.events.models import Event

        usage = namedtuple("u", ["total", "used", "free"])(100_000_000_000, 99_000_000_000, 1_000_000_000)
        with mock.patch.object(tasks.os.path, "isdir", return_value=True), \
                mock.patch.object(tasks.shutil, "disk_usage", return_value=usage):
            result = tasks.check_storage()
        self.assertEqual(result["alarm"], "critical")
        self.assertTrue(Event.objects.filter(type="storage", severity="critical").exists())

    def test_ample_space_no_alarm(self):
        usage = namedtuple("u", ["total", "used", "free"])(100_000_000_000, 10_000_000_000, 90_000_000_000)
        with mock.patch.object(tasks.os.path, "isdir", return_value=True), \
                mock.patch.object(tasks.shutil, "disk_usage", return_value=usage):
            result = tasks.check_storage()
        self.assertEqual(result["alarm"], "")
        self.assertFalse(Event.objects.filter(type="storage").exists())


class EventClipTriggerTests(TestCase):
    """A camera event on a recording camera queues an EventClip (Phase 3)."""

    def setUp(self):
        patcher = mock.patch.object(media_client, "sync_camera_path", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")
        RecordingSchedule.objects.create(
            camera=self.cam, mode="continuous", pre_event_seconds=5, post_event_seconds=10
        )

    def _event(self, etype="motion", camera=None):
        return Event.objects.create(
            organization=self.org, camera=camera if camera else self.cam, type=etype
        )

    def test_clip_created_with_pre_post_window(self):
        ev = self._event("motion")
        clip = EventClip.objects.get(event=ev)
        self.assertEqual(clip.status, "pending")
        self.assertAlmostEqual((ev.ts - clip.start).total_seconds(), 5, delta=1)
        self.assertAlmostEqual((clip.end - ev.ts).total_seconds(), 10, delta=1)

    def test_no_clip_for_non_video_event(self):
        self._event("offline")
        self.assertEqual(EventClip.objects.count(), 0)

    def test_no_clip_when_recording_off(self):
        cam2 = Camera.objects.create(organization=self.org, name="c2")
        RecordingSchedule.objects.create(camera=cam2, mode="off")
        self._event("motion", camera=cam2)
        self.assertFalse(EventClip.objects.filter(camera=cam2).exists())

    def test_overlapping_events_are_deduplicated(self):
        self._event("motion")
        self._event("tripwire")  # within the same 15s window
        self.assertEqual(EventClip.objects.filter(camera=self.cam).count(), 1)


class ClipAssemblyTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="clips_test_")
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        patcher = mock.patch.object(media_client, "sync_camera_path", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")
        RecordingSchedule.objects.create(
            camera=self.cam, mode="motion", pre_event_seconds=5, post_event_seconds=10
        )

    def _segment(self, start, dur, name):
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as fh:
            fh.write(b"seg")
        return Recording.objects.create(
            camera=self.cam, start=start, end=start + timedelta(seconds=dur),
            file_path=path, size=3, duration=dur,
        )

    def test_assemble_produces_ready_clip_with_checksum(self):
        ev = Event.objects.create(organization=self.org, camera=self.cam, type="motion")
        clip = EventClip.objects.get(event=ev)
        # Segments covering [start, end] with the last one reaching past end.
        self._segment(clip.start - timedelta(seconds=1), 6, "a.mp4")
        self._segment(clip.end - timedelta(seconds=2), 6, "b.mp4")

        def fake_trim(list_file, offset, duration, out_file):
            with open(out_file, "wb") as fh:
                fh.write(b"FAKECLIP")
            return True

        with override_settings(RECORDINGS_DIR=self.tmp), \
                mock.patch.object(tasks, "_ffmpeg_trim", side_effect=fake_trim), \
                mock.patch.object(tasks, "_probe_duration", return_value=15.0):
            tasks.assemble_event_clip.apply(args=[clip.id]).get()

        clip.refresh_from_db()
        self.assertEqual(clip.status, "ready")
        self.assertEqual(clip.size, len(b"FAKECLIP"))
        self.assertEqual(len(clip.sha256), 64)
        self.assertEqual(clip.duration, 15.0)

    def test_assemble_fails_when_segment_files_missing(self):
        ev = Event.objects.create(organization=self.org, camera=self.cam, type="motion")
        clip = EventClip.objects.get(event=ev)
        # A DB segment covering the window but whose file does not exist on disk.
        Recording.objects.create(
            camera=self.cam, start=clip.start, end=clip.end + timedelta(seconds=1),
            file_path="/nope/missing.mp4",
        )
        with override_settings(RECORDINGS_DIR=self.tmp):
            tasks.assemble_event_clip.apply(args=[clip.id]).get()
        clip.refresh_from_db()
        self.assertEqual(clip.status, "failed")
        self.assertTrue(clip.error)

    def test_retention_keeps_segments_for_pending_clip(self):
        ev = Event.objects.create(organization=self.org, camera=self.cam, type="motion")
        clip = EventClip.objects.get(event=ev)  # pending
        old = timezone.now() - timedelta(days=30)
        # An old segment overlapping the pending clip window must not be pruned.
        seg = Recording.objects.create(
            camera=self.cam, start=clip.start, end=clip.end, file_path="/x/s.mp4"
        )
        RecordingSchedule.objects.filter(camera=self.cam).update(retention_days=1)
        # Move the segment's timestamp into the past but keep it inside the window
        # relationship by moving the clip window too.
        Recording.objects.filter(id=seg.id).update(start=old, end=old + timedelta(seconds=15))
        EventClip.objects.filter(id=clip.id).update(
            start=old, end=old + timedelta(seconds=15)
        )
        tasks.apply_retention()
        self.assertTrue(Recording.objects.filter(id=seg.id).exists())


class ClipRetryApiTests(APITestCase):
    def setUp(self):
        patcher = mock.patch.object(media_client, "sync_camera_path", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org = Organization.objects.create(name="O", slug="o")
        role = Role.objects.create(
            organization=self.org, name="mgr",
            permissions=["playback.view", "playback.export"],
        )
        User.objects.create_user(
            username="mgr", password="pw12345678", organization=self.org, role=role
        )
        self.cam = Camera.objects.create(organization=self.org, name="c")
        ev = Event.objects.create(organization=self.org, camera=self.cam, type="manual")
        self.clip = EventClip.objects.create(
            event=ev, camera=self.cam, start=timezone.now(), end=timezone.now(),
            status="failed", error="boom",
        )
        res = self.client.post(
            "/api/auth/token/", {"username": "mgr", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_retry_resets_failed_clip(self):
        with mock.patch.object(tasks.assemble_event_clip, "delay") as delayed:
            r = self.client.post(f"/api/event-clips/{self.clip.id}/retry/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "pending")
        delayed.assert_called_once_with(self.clip.id)


class PlaybackStreamTests(APITestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pb_")
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")
        self.path = os.path.join(self.tmp, "seg.mp4")
        with open(self.path, "wb") as fh:
            fh.write(bytes(range(256)) * 4)  # 1024 bytes
        self.rec = Recording.objects.create(
            camera=self.cam, start=timezone.now(), file_path=self.path, size=1024
        )

    def test_signed_full_stream(self):
        from apps.recordings.playback import sign_recording

        sig = sign_recording(self.rec.id)
        res = self.client.get(f"/api/recordings/{self.rec.id}/stream/?sig={sig}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Accept-Ranges"], "bytes")
        self.assertEqual(res["Content-Length"], "1024")

    def test_range_request_returns_206(self):
        from apps.recordings.playback import sign_recording

        sig = sign_recording(self.rec.id)
        res = self.client.get(
            f"/api/recordings/{self.rec.id}/stream/?sig={sig}", HTTP_RANGE="bytes=0-99"
        )
        self.assertEqual(res.status_code, 206)
        self.assertEqual(res["Content-Range"], "bytes 0-99/1024")
        self.assertEqual(res["Content-Length"], "100")
        body = b"".join(res.streaming_content)
        self.assertEqual(len(body), 100)

    def test_bad_signature_is_denied(self):
        res = self.client.get(f"/api/recordings/{self.rec.id}/stream/?sig=tampered")
        self.assertEqual(res.status_code, 404)


class TimelineOverlapTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="O", slug="o")
        role = Role.objects.create(
            organization=self.org, name="op", permissions=["playback.view"]
        )
        User.objects.create_user(
            username="op", password="pw12345678", organization=self.org, role=role
        )
        self.cam = Camera.objects.create(organization=self.org, name="c")
        res = self.client.post(
            "/api/auth/token/", {"username": "op", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_segment_overlapping_window_is_included_with_signed_url(self):
        base = timezone.now().replace(microsecond=0)
        # Segment starts 30s BEFORE the window but runs into it — overlap filter
        # must include it (a start-only filter would miss it).
        Recording.objects.create(
            camera=self.cam, start=base - timedelta(seconds=30),
            end=base + timedelta(seconds=30), file_path="/x/s.mp4",
        )
        after = base.isoformat()
        before = (base + timedelta(hours=1)).isoformat()
        res = self.client.get(
            f"/api/recordings/timeline/?camera={self.cam.id}&after={after}&before={before}"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertIn("sig=", res.data[0]["stream_url"])


class ExportTrimTests(TestCase):
    def test_export_trims_to_exact_range(self):
        from apps.recordings.models import ExportJob

        tmp = tempfile.mkdtemp(prefix="exp_")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        org = Organization.objects.create(name="O", slug="o")
        cam = Camera.objects.create(organization=org, name="c")
        base = timezone.now().replace(microsecond=0)
        for i, name in enumerate(("a.mp4", "b.mp4")):
            p = os.path.join(tmp, name)
            with open(p, "wb") as fh:
                fh.write(b"seg")
            Recording.objects.create(
                camera=cam, start=base + timedelta(seconds=60 * i),
                end=base + timedelta(seconds=60 * (i + 1)), file_path=p,
            )
        job = ExportJob.objects.create(
            camera=cam, start=base + timedelta(seconds=30),
            end=base + timedelta(seconds=90),
        )
        calls = {}

        def fake_trim(list_file, offset, duration, out_file):
            calls["offset"] = offset
            calls["duration"] = duration
            with open(out_file, "wb") as fh:
                fh.write(b"OUT")
            return True

        with override_settings(RECORDINGS_DIR=tmp), \
                mock.patch.object(tasks, "_ffmpeg_trim", side_effect=fake_trim):
            tasks.build_export(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertAlmostEqual(calls["offset"], 30, delta=1)  # 30s into first segment
        self.assertAlmostEqual(calls["duration"], 60, delta=1)  # 90 - 30


class ExportApiTests(APITestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="expapi_")
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.org1 = Organization.objects.create(name="O1", slug="o1")
        self.org2 = Organization.objects.create(name="O2", slug="o2")
        role = Role.objects.create(
            organization=self.org1, name="op", permissions=["playback.view", "playback.export"]
        )
        User.objects.create_user(
            username="op", password="pw12345678", organization=self.org1, role=role
        )
        self.cam1 = Camera.objects.create(organization=self.org1, name="c1")
        self.cam2 = Camera.objects.create(organization=self.org2, name="c2")
        res = self.client.post(
            "/api/auth/token/", {"username": "op", "password": "pw12345678"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_export_rejects_other_org_camera(self):
        r = self.client.post(
            "/api/exports/",
            {"camera": self.cam2.id, "start": timezone.now().isoformat(), "end": timezone.now().isoformat()},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_download_done_export(self):
        path = os.path.join(self.tmp, "export.mp4")
        with open(path, "wb") as fh:
            fh.write(b"EXPORTED")
        job = ExportJob.objects.create(
            camera=self.cam1, start=timezone.now(), end=timezone.now(),
            status="done", output_file=path, size=8,
        )
        r = self.client.get(f"/api/exports/{job.id}/download/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])

    def test_download_pending_is_404(self):
        job = ExportJob.objects.create(
            camera=self.cam1, start=timezone.now(), end=timezone.now(), status="pending"
        )
        r = self.client.get(f"/api/exports/{job.id}/download/")
        self.assertEqual(r.status_code, 404)
