from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from apps.accounts.models import Organization
from apps.analytics.contract import Detection, DetectionSerializer
from apps.analytics.models import AnalyticsRule
from apps.analytics.pipeline import detector_health, ingest_detection
from apps.cameras.models import Camera
from apps.events.models import Event

from .detectors import _demo_enabled
from .tasks import run_enabled_rules


class DemoAnalyticsGateTests(SimpleTestCase):
    @override_settings(FEATURE_FLAGS={"analytics": False})
    def test_scheduler_is_idle_when_analytics_feature_is_disabled(self):
        self.assertEqual(run_enabled_rules(), 0)

    @override_settings(ENABLE_DEMO_ANALYTICS=False)
    def test_rule_cannot_enable_demo_output_by_itself(self):
        self.assertFalse(_demo_enabled({"demo": True}))

    @override_settings(ENABLE_DEMO_ANALYTICS=True)
    def test_deployment_and_rule_must_both_opt_in(self):
        self.assertFalse(_demo_enabled({}))
        self.assertTrue(_demo_enabled({"demo": True}))


class DetectionContractTests(SimpleTestCase):
    def test_serializer_rejects_out_of_range_confidence(self):
        s = DetectionSerializer(data={"camera_id": 1, "event_type": "object", "confidence": 1.5})
        self.assertFalse(s.is_valid())

    def test_serializer_accepts_valid_detection(self):
        s = DetectionSerializer(
            data={"camera_id": 1, "event_type": "object", "confidence": 0.8, "model_name": "yolo"}
        )
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.to_detection().model_name, "yolo")


class IngestPipelineTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="c")
        self.rule = AnalyticsRule.objects.create(
            organization=self.org, camera=self.cam, kind="object", config={}
        )

    def _det(self, **kw):
        base = dict(
            camera_id=self.cam.id, event_type="object", confidence=0.9,
            model_name="yolo", model_version="v8", bounding_boxes=[[0.5, 0.5, 0.1, 0.1]],
            track_id="t1",
        )
        base.update(kw)
        return Detection(**base)

    def test_accepts_and_records_model_metadata(self):
        ev = ingest_detection(self._det(), rule=self.rule, latency_ms=12.0)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.details["model_name"], "yolo")
        self.assertEqual(ev.details["model_version"], "v8")
        self.assertEqual(ev.details["confidence"], 0.9)
        self.assertIn("yolo", detector_health())

    def test_threshold_drops_low_confidence(self):
        self.rule.config = {"min_confidence": 0.8}
        self.rule.save()
        ev = ingest_detection(self._det(confidence=0.5), rule=self.rule)
        self.assertIsNone(ev)
        self.assertEqual(Event.objects.count(), 0)

    def test_zone_drops_detection_outside_polygon(self):
        # A small top-left zone; a detection centered bottom-right is excluded.
        self.rule.config = {"zone": [[0, 0], [0.2, 0], [0.2, 0.2], [0, 0.2]]}
        self.rule.save()
        ev = ingest_detection(self._det(bounding_boxes=[[0.8, 0.8, 0.05, 0.05]]), rule=self.rule)
        self.assertIsNone(ev)

    def test_duplicate_suppression(self):
        first = ingest_detection(self._det(), rule=self.rule)
        second = ingest_detection(self._det(), rule=self.rule)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(Event.objects.filter(camera=self.cam).count(), 1)
