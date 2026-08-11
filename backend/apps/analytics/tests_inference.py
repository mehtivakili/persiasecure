"""
Tests for the AI-0 inference runtime.

Covers the parts that must be correct regardless of whether the heavy model
libraries (numpy/onnxruntime) are installed:
  * box geometry (IoU, per-class NMS, letterbox round-trip) — pure Python;
  * the registry resolves an active DetectorModel to a Detector, caches it, and
    reloads when the model changes;
  * a dummy model runs end-to-end through the runner → ingest_detection → Event,
    honouring the Phase-7 confidence threshold and class filter;
  * the YOLO backend degrades gracefully (available() == False) when its optional
    deps or weights are missing, so object_worker falls back instead of raising.
"""
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import Organization
from apps.cameras.models import Camera
from apps.events.models import Event

from .inference import geometry, registry
from .inference.runner import NO_MODEL, run_object_detection
from .inference.yolo import YoloOnnxDetector
from .models import AnalyticsRule, DetectorModel


class GeometryTests(SimpleTestCase):
    def test_iou_identical_boxes_is_one(self):
        b = [0.0, 0.0, 1.0, 1.0]
        self.assertAlmostEqual(geometry.iou_xyxy(b, b), 1.0)

    def test_iou_disjoint_boxes_is_zero(self):
        self.assertEqual(geometry.iou_xyxy([0, 0, 1, 1], [2, 2, 3, 3]), 0.0)

    def test_iou_half_overlap(self):
        # Two unit squares overlapping on half → inter .5, union 1.5 → 1/3.
        self.assertAlmostEqual(geometry.iou_xyxy([0, 0, 1, 1], [0.5, 0, 1.5, 1]), 1 / 3, places=5)

    def test_per_class_nms_suppresses_duplicate_same_class(self):
        dets = [
            {"label": "person", "confidence": 0.9, "bbox": [0.1, 0.1, 0.3, 0.3]},
            {"label": "person", "confidence": 0.6, "bbox": [0.11, 0.11, 0.3, 0.3]},  # overlaps → dropped
            {"label": "car", "confidence": 0.8, "bbox": [0.1, 0.1, 0.3, 0.3]},        # other class → kept
        ]
        kept = geometry.per_class_nms(dets, iou_threshold=0.45)
        labels = sorted(d["label"] for d in kept)
        self.assertEqual(labels, ["car", "person"])
        self.assertEqual(len([d for d in kept if d["label"] == "person"]), 1)

    def test_letterbox_roundtrip_maps_box_back(self):
        src_w, src_h, dst = 1920, 1080, 640
        scale, pad_x, pad_y = geometry.letterbox_params(src_w, src_h, dst, dst)
        # A box at the source center, forward-mapped into model space…
        cx, cy = src_w / 2, src_h / 2
        mx1, my1 = cx * scale + pad_x - 10, cy * scale + pad_y - 10
        mx2, my2 = cx * scale + pad_x + 10, cy * scale + pad_y + 10
        nx = geometry.unletterbox_xyxy([mx1, my1, mx2, my2], scale, pad_x, pad_y, src_w, src_h)
        # …should come back centered (normalized ~0.5).
        self.assertAlmostEqual((nx[0] + nx[2]) / 2, 0.5, places=2)
        self.assertAlmostEqual((nx[1] + nx[3]) / 2, 0.5, places=2)


class YoloGracefulTests(SimpleTestCase):
    def test_unavailable_without_weights_or_deps(self):
        # No path set → cannot run, must report unavailable rather than raise.
        model = DetectorModel(name="y", task="object", framework="onnx", path="")
        det = YoloOnnxDetector(model)
        self.assertFalse(det.available())
        self.assertEqual(det.infer(b"", 0, 0), [])


class RegistryTests(TestCase):
    def setUp(self):
        registry.clear_cache()

    def test_no_active_model_returns_none(self):
        self.assertIsNone(registry.get_detector("object"))
        self.assertFalse(registry.has_active_model("object"))

    def test_active_dummy_model_resolves_and_caches(self):
        m = DetectorModel.objects.create(
            name="dummy-obj", task="object", framework="dummy", active=True,
            classes=["person"],
        )
        d1 = registry.get_detector("object")
        d2 = registry.get_detector("object")
        self.assertIsNotNone(d1)
        self.assertIs(d1, d2)  # cached instance reused
        # Editing the model busts the cache (new instance).
        m.version = "v2"
        m.save()
        d3 = registry.get_detector("object")
        self.assertIsNot(d1, d3)

    def test_hardware_snapshot_never_raises(self):
        self.assertIsInstance(registry.hardware_snapshot(), dict)


class RunnerEndToEndTests(TestCase):
    def setUp(self):
        cache.clear()
        registry.clear_cache()
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")
        self.rule = AnalyticsRule.objects.create(
            organization=self.org, camera=self.cam, kind="object", config={},
        )

    def _activate_dummy(self, **kw):
        return DetectorModel.objects.create(
            name="dummy-obj", task="object", framework="dummy", active=True, **kw
        )

    @mock.patch("apps.analytics.inference.runner.ffmpeg.grab_snapshot", return_value=b"jpeg")
    @mock.patch("apps.analytics.inference.runner._frame_dims", return_value=(1920, 1080))
    @mock.patch("apps.analytics.inference.runner.media_client.build_source_url", return_value="rtsp://x")
    def test_dummy_model_creates_object_event(self, *_):
        self._activate_dummy(classes=["person"])
        created = run_object_detection(self.rule)
        self.assertEqual(created, 1)
        ev = Event.objects.get()
        self.assertEqual(ev.type, "object")
        self.assertEqual(ev.details["label"], "person")
        self.assertEqual(ev.details["model_name"], "dummy-obj")

    def test_runner_reports_no_model_when_none_active(self):
        self.assertEqual(run_object_detection(self.rule), NO_MODEL)

    @mock.patch("apps.analytics.inference.runner.ffmpeg.grab_snapshot", return_value=b"jpeg")
    @mock.patch("apps.analytics.inference.runner._frame_dims", return_value=(1920, 1080))
    @mock.patch("apps.analytics.inference.runner.media_client.build_source_url", return_value="rtsp://x")
    def test_confidence_threshold_filters_detection(self, *_):
        # Dummy emits ~0.9; a threshold above that suppresses the event.
        self._activate_dummy(classes=["person"])
        self.rule.config = {"min_confidence": 0.99}
        self.rule.save()
        created = run_object_detection(self.rule)
        self.assertEqual(created, 0)
        self.assertEqual(Event.objects.count(), 0)

    @mock.patch("apps.analytics.inference.runner.ffmpeg.grab_snapshot", return_value=b"jpeg")
    @mock.patch("apps.analytics.inference.runner._frame_dims", return_value=(1920, 1080))
    @mock.patch("apps.analytics.inference.runner.media_client.build_source_url", return_value="rtsp://x")
    def test_class_filter_excludes_unwanted_labels(self, *_):
        self._activate_dummy(classes=["person"])
        self.rule.config = {"classes": ["car"]}  # dummy emits 'person' → filtered out
        self.rule.save()
        created = run_object_detection(self.rule)
        self.assertEqual(created, 0)

    @mock.patch("apps.analytics.inference.runner.ffmpeg.grab_snapshot", return_value=b"jpeg")
    @mock.patch("apps.analytics.inference.runner._frame_dims", return_value=(1920, 1080))
    @mock.patch("apps.analytics.inference.runner.media_client.build_source_url", return_value="rtsp://x")
    def test_detection_publishes_overlay_and_logs(self, *_):
        from apps.analytics.inference import overlay

        self._activate_dummy(classes=["person"])
        with self.assertLogs("apps.analytics.inference.runner", level="INFO") as logs:
            run_object_detection(self.rule)
        # Log line names what was found.
        self.assertTrue(any("person" in m for m in logs.output))
        # Overlay cache holds the latest boxes for the camera.
        data = overlay.latest(self.cam.id)
        self.assertIsNotNone(data)
        self.assertEqual(data["detections"][0]["label"], "person")
        self.assertEqual(len(data["detections"][0]["bbox"]), 4)


class CameraDetectionsEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        registry.clear_cache()
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")

    def test_endpoint_reports_active_and_boxes(self):
        from apps.analytics.inference import overlay
        from apps.analytics.inference.base import RawDetection
        from apps.analytics.views import camera_detections
        from rest_framework.test import APIRequestFactory, force_authenticate

        AnalyticsRule.objects.create(
            organization=self.org, camera=self.cam, kind="object", enabled=True, config={}
        )
        overlay.publish(self.cam.id, [RawDetection(label="car", confidence=0.9, bbox=[0.1, 0.1, 0.2, 0.2])], "yolo11m")

        user = mock.Mock(is_superuser=True, is_authenticated=True)
        user.has_vms_perm.return_value = True
        req = APIRequestFactory().get(f"/api/analytics/cameras/{self.cam.id}/detections")
        force_authenticate(req, user=user)
        resp = camera_detections(req, self.cam.id)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["active"])
        self.assertEqual(resp.data["model"], "yolo11m")
        self.assertEqual(resp.data["detections"][0]["label"], "car")
