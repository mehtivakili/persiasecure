"""
Tests for the AI-1 continuous-inference building blocks: MJPEG frame splitter,
motion gate, IoU tracker, the eligibility plan, and the register command.
The threaded I/O shell (ffmpeg subprocess) is validated live, not here.
"""
import io

from django.test import TestCase, override_settings
from django.core.management import call_command

from apps.accounts.models import Organization
from apps.cameras.models import Camera

from .inference import registry
from .inference.base import RawDetection
from .inference.frames import extract_jpeg_frames
from .inference.gate import MotionGate
from .inference.loop import plan
from .inference.tracker import IouTracker
from .models import AnalyticsRule, DetectorModel


def _jpeg(color, size=(64, 64)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


class MjpegSplitterTests(TestCase):
    def test_splits_two_concatenated_frames(self):
        a, b = _jpeg((255, 0, 0)), _jpeg((0, 255, 0))
        frames, remainder = extract_jpeg_frames(a + b)
        self.assertEqual(len(frames), 2)
        self.assertEqual(remainder, b"")

    def test_keeps_partial_trailing_frame_as_remainder(self):
        a, b = _jpeg((255, 0, 0)), _jpeg((0, 0, 255))
        cut = a + b[: len(b) // 2]
        frames, remainder = extract_jpeg_frames(cut)
        self.assertEqual(len(frames), 1)
        self.assertTrue(remainder.startswith(b"\xff\xd8"))  # partial next frame kept from SOI
        # Feeding the rest completes it.
        frames2, remainder2 = extract_jpeg_frames(remainder + b[len(b) // 2:])
        self.assertEqual(len(frames2), 1)
        self.assertEqual(remainder2, b"")

    def test_ignores_noise_before_first_marker(self):
        a = _jpeg((10, 20, 30))
        frames, _ = extract_jpeg_frames(b"garbagebytes" + a)
        self.assertEqual(len(frames), 1)


class MotionGateTests(TestCase):
    def test_first_frame_always_passes(self):
        gate = MotionGate(threshold=2.0)
        self.assertTrue(gate.passes(_jpeg((0, 0, 0))))

    def test_identical_frame_is_gated_out(self):
        gate = MotionGate(threshold=2.0)
        frame = _jpeg((123, 123, 123))
        gate.passes(frame)                       # baseline
        self.assertFalse(gate.passes(frame))     # no change → skip inference

    def test_large_change_passes(self):
        gate = MotionGate(threshold=2.0)
        gate.passes(_jpeg((0, 0, 0)))            # baseline black
        self.assertTrue(gate.passes(_jpeg((255, 255, 255))))  # → white

    def test_decode_error_fails_open(self):
        gate = MotionGate()
        self.assertTrue(gate.passes(b"not-a-jpeg"))


class IouTrackerTests(TestCase):
    def _d(self, label, bbox):
        return RawDetection(label=label, confidence=0.9, bbox=bbox)

    def test_same_object_keeps_track_id_across_frames(self):
        tr = IouTracker(iou_threshold=0.3)
        f1 = [self._d("person", [0.10, 0.10, 0.20, 0.20])]
        tr.update(f1)
        first_id = f1[0].track_id
        f2 = [self._d("person", [0.12, 0.11, 0.20, 0.20])]  # slight move, high IoU
        tr.update(f2)
        self.assertEqual(f2[0].track_id, first_id)

    def test_distinct_objects_get_distinct_ids(self):
        tr = IouTracker()
        frame = [self._d("person", [0.0, 0.0, 0.1, 0.1]), self._d("car", [0.8, 0.8, 0.15, 0.15])]
        tr.update(frame)
        self.assertNotEqual(frame[0].track_id, frame[1].track_id)
        self.assertEqual(tr.active_count, 2)

    def test_stale_track_ages_out(self):
        tr = IouTracker(max_age=1)
        tr.update([self._d("person", [0.1, 0.1, 0.1, 0.1])])
        tr.update([])  # miss (age→1, still kept)
        tr.update([])  # miss (age→2 > max_age) → dropped
        self.assertEqual(tr.active_count, 0)


class PlanTests(TestCase):
    def setUp(self):
        registry.clear_cache()
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c", enabled=True)
        self.rule = AnalyticsRule.objects.create(
            organization=self.org, camera=self.cam, kind="object", enabled=True, config={"fps": 8}
        )

    @override_settings(FEATURE_FLAGS={"analytics": True})
    def test_plan_empty_without_active_model(self):
        self.assertEqual(plan(), [])

    @override_settings(FEATURE_FLAGS={"analytics": True})
    def test_plan_lists_rule_when_model_active(self):
        DetectorModel.objects.create(name="d", task="object", framework="dummy", active=True)
        rules = plan()
        self.assertEqual([r.id for r in rules], [self.rule.id])

    @override_settings(FEATURE_FLAGS={"analytics": False})
    def test_plan_empty_when_feature_off(self):
        DetectorModel.objects.create(name="d", task="object", framework="dummy", active=True)
        self.assertEqual(plan(), [])


class RegisterCommandTests(TestCase):
    def test_registers_and_activates_single_model_per_task(self):
        call_command(
            "register_detector_model", "--name", "yolov8n", "--task", "object",
            "--path", "/models/yolov8n.onnx", "--classes", "coco",
            "--framework", "dummy", "--allow-missing", "--activate",
        )
        m1 = DetectorModel.objects.get(name="yolov8n")
        self.assertTrue(m1.active)
        self.assertIn("person", m1.classes)
        # Activating a second deactivates the first (clean rollback semantics).
        call_command(
            "register_detector_model", "--name", "yolov8s", "--task", "object",
            "--path", "/models/yolov8s.onnx", "--framework", "dummy",
            "--allow-missing", "--activate",
        )
        m1.refresh_from_db()
        self.assertFalse(m1.active)
        self.assertEqual(DetectorModel.objects.filter(task="object", active=True).count(), 1)
