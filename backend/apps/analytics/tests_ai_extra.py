"""
Tests for the three AI extensions: object-based line-crossing (tripwire),
Iranian ALPR, and cross-camera batching.
"""
import threading
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import Organization
from apps.cameras.models import Camera
from apps.events.models import Event

from .inference import registry
from .inference.base import RawDetection
from .inference.batching import BatchCollector, group
from .inference.crossing import LineCrossingDetector, segments_intersect
from .inference.dummy import DummyDetector
from .inference.loop import CameraWorker, load_crossings
from .inference.plates import (
    fold_digits,
    is_valid_iranian_plate,
    normalize_plate,
    parse_iranian_plate,
)
from .inference.runner import run_alpr_detection
from .models import AnalyticsRule, DetectorModel, PlateRead, PlateWatchlist


# --------------------------------------------------------------------------- #
# Object-based line crossing
# --------------------------------------------------------------------------- #
class CrossingGeometryTests(SimpleTestCase):
    def test_segments_that_cross(self):
        self.assertTrue(segments_intersect((0, 0), (1, 1), (0, 1), (1, 0)))

    def test_parallel_segments_do_not_cross(self):
        self.assertFalse(segments_intersect((0, 0), (1, 0), (0, 1), (1, 1)))

    def test_directional_crossing_and_first_frame_none(self):
        # Vertical line at x=0.5; object moving left→right.
        det = LineCrossingDetector([(0.5, 0.0), (0.5, 1.0)])
        self.assertIsNone(det.check("t1", (0.2, 0.5)))       # first sample: no path yet
        self.assertEqual(det.check("t1", (0.8, 0.5)), "ab")  # crossed
        # Moving back the other way → opposite direction label.
        self.assertEqual(det.check("t1", (0.2, 0.5)), "ba")

    def test_movement_parallel_to_line_never_crosses(self):
        det = LineCrossingDetector([(0.5, 0.0), (0.5, 1.0)])
        det.check("t1", (0.2, 0.1))
        self.assertIsNone(det.check("t1", (0.2, 0.9)))  # stays on the same side

    def test_direction_filter(self):
        det = LineCrossingDetector([(0.5, 0.0), (0.5, 1.0)], direction="ba")
        det.check("t1", (0.2, 0.5))
        self.assertIsNone(det.check("t1", (0.8, 0.5)))  # this is "ab", filtered out


class CrossingLoopIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        registry.clear_cache()
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="lobby3", enabled=True)
        self.obj_rule = AnalyticsRule.objects.create(
            organization=self.org, camera=self.cam, kind="object", enabled=True, config={}
        )
        self.trip_rule = AnalyticsRule.objects.create(
            organization=self.org, camera=self.cam, kind="tripwire", enabled=True,
            config={"line": [[0.5, 0.0], [0.5, 1.0]]},
        )

    def test_load_crossings_finds_tripwire(self):
        pairs = load_crossings(self.cam)
        self.assertEqual(len(pairs), 1)

    def test_tracked_object_crossing_line_raises_tripwire_event(self):
        worker = CameraWorker(self.obj_rule, threading.Event())
        detector = DummyDetector()
        # Frame 1: object left of the line.
        left = [RawDetection(label="person", confidence=0.9, bbox=[0.1, 0.45, 0.1, 0.1], track_id="t1")]
        worker._check_crossings(detector, left, b"jpeg")
        self.assertEqual(Event.objects.filter(type="tripwire").count(), 0)
        # Frame 2: same track now right of the line → one crossing event.
        right = [RawDetection(label="person", confidence=0.9, bbox=[0.8, 0.45, 0.1, 0.1], track_id="t1")]
        worker._check_crossings(detector, right, b"jpeg")
        events = Event.objects.filter(type="tripwire")
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().severity, "critical")
        self.assertEqual(events.first().details.get("direction"), "ab")


# --------------------------------------------------------------------------- #
# Iranian ALPR
# --------------------------------------------------------------------------- #
class PlateNormalizationTests(SimpleTestCase):
    def test_fold_persian_and_arabic_digits(self):
        self.assertEqual(fold_digits("۱۲۳٤٥"), "12345")

    def test_parse_valid_iranian_plate_with_persian_digits(self):
        parsed = parse_iranian_plate("۱۲ ب ۳۴۵ ایران ۶۷")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["canonical"], "12ب34567")
        self.assertEqual(parsed["province"], "67")
        self.assertEqual(parsed["letter"], "ب")

    def test_normalize_strips_iran_word_and_separators(self):
        self.assertEqual(normalize_plate("12-ب-345 ایران 67"), "12ب34567")

    def test_invalid_layout_returns_none(self):
        self.assertIsNone(parse_iranian_plate("hello world"))
        self.assertFalse(is_valid_iranian_plate("999999999"))  # no letter


class AlprRunnerTests(TestCase):
    def setUp(self):
        cache.clear()
        registry.clear_cache()
        self.org = Organization.objects.create(name="O", slug="o")
        self.cam = Camera.objects.create(organization=self.org, name="gate", enabled=True)
        self.rule = AnalyticsRule.objects.create(
            organization=self.org, camera=self.cam, kind="alpr", enabled=True, config={}
        )
        DetectorModel.objects.create(name="dummy-alpr", task="alpr", framework="dummy", active=True)

    @mock.patch("apps.analytics.inference.runner.ffmpeg.grab_snapshot", return_value=b"jpeg")
    @mock.patch("apps.analytics.inference.runner._frame_dims", return_value=(1280, 720))
    @mock.patch("apps.analytics.inference.runner.media_client.build_source_url", return_value="rtsp://x")
    def test_dummy_alpr_creates_plateread_and_event(self, *_):
        created = run_alpr_detection(self.rule)
        self.assertEqual(created, 1)
        pr = PlateRead.objects.get()
        self.assertEqual(pr.plate, "12ب34567")
        self.assertFalse(pr.watchlist_hit)
        self.assertEqual(Event.objects.get(type="alpr").severity, "info")

    @mock.patch("apps.analytics.inference.runner.ffmpeg.grab_snapshot", return_value=b"jpeg")
    @mock.patch("apps.analytics.inference.runner._frame_dims", return_value=(1280, 720))
    @mock.patch("apps.analytics.inference.runner.media_client.build_source_url", return_value="rtsp://x")
    def test_watchlist_hit_raises_critical(self, *_):
        PlateWatchlist.objects.create(organization=self.org, plate="12ب34567", active=True)
        run_alpr_detection(self.rule)
        ev = Event.objects.get(type="alpr")
        self.assertEqual(ev.severity, "critical")
        self.assertTrue(PlateRead.objects.get().watchlist_hit)


# --------------------------------------------------------------------------- #
# Cross-camera batching
# --------------------------------------------------------------------------- #
class BatchingTests(SimpleTestCase):
    def test_group_chunks(self):
        self.assertEqual(group([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_group_rejects_zero(self):
        with self.assertRaises(ValueError):
            group([1], 0)

    def test_batch_collector_fifo_drain(self):
        bc = BatchCollector()
        bc.add("cam1", b"a")
        bc.add("cam2", b"b")
        bc.add("cam3", b"c")
        self.assertEqual(len(bc), 3)
        first = bc.drain(2)
        self.assertEqual([k for k, _ in first], ["cam1", "cam2"])
        self.assertEqual(len(bc), 1)

    def test_default_infer_batch_is_sequential(self):
        det = DummyDetector()
        out = det.infer_batch([(b"x", 0, 0), (b"y", 0, 0)])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0].label, "person")
