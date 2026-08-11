"""
Continuous inference loop (Phase AI-1).

The real-time path the AI plan calls for: instead of grabbing one snapshot every
~20 s (the celery `object_worker`), a dedicated worker decodes each camera's RTSP
at a controlled FPS and runs the model only on frames the MotionGate lets through,
assigning stable track ids before ingesting. Runs in the isolated inference
service (`docker compose --profile gpu`), so it can never starve the VMS core.

Structure:
  * `plan()`            → the (rule, camera) pairs eligible to run (pure, tested).
  * `CameraWorker`      → one thread per camera: decode → gate → infer → track →
                          ingest, with reconnect/backoff.
  * `InferenceService`  → builds workers from plan(), runs until SIGTERM.

Only the pure helpers are unit-tested; the threaded I/O shell is validated live.
"""
import logging
import threading
import time

from . import registry
from .crossing import LineCrossingDetector
from .frames import RtspFrameSource
from .gate import MotionGate
from .runner import emit_tripwire, infer_frame, process_detections
from .tracker import IouTracker

logger = logging.getLogger(__name__)


def _feature_enabled():
    from django.conf import settings

    return bool(getattr(settings, "FEATURE_FLAGS", {}).get("analytics", False))


def plan():
    """
    Object-detection rules eligible for the continuous loop: analytics feature on,
    an active object DetectorModel present, and enabled object rules on enabled
    cameras. Returns a list of AnalyticsRule. Pure w.r.t. I/O — unit-tested.
    """
    if not _feature_enabled() or not registry.has_active_model("object"):
        return []
    from apps.analytics.models import AnalyticsRule

    return list(
        AnalyticsRule.objects.filter(kind="object", enabled=True, camera__enabled=True)
        .select_related("camera", "organization")
    )


def load_crossings(camera):
    """
    Build (tripwire_rule, LineCrossingDetector) pairs for a camera's enabled
    tripwire rules that define a line. Empty when the camera has none.
    """
    from apps.analytics.models import AnalyticsRule

    pairs = []
    rules = AnalyticsRule.objects.filter(camera=camera, kind="tripwire", enabled=True)
    for r in rules:
        cfg = r.config or {}
        line = cfg.get("line")
        if line and len(line) == 2:
            pairs.append((r, LineCrossingDetector(line, direction=cfg.get("direction", "both"))))
    return pairs


class CameraWorker(threading.Thread):
    def __init__(self, rule, stop_event, backoff=5.0):
        super().__init__(name=f"infer-cam-{rule.camera_id}", daemon=True)
        self.rule = rule
        self.stop_event = stop_event
        self.backoff = backoff
        config = rule.config or {}
        self.fps = int(config.get("fps", 5))
        self.gate = MotionGate(threshold=float(config.get("motion_threshold", 2.0)))
        self.tracker = IouTracker(
            iou_threshold=float(config.get("track_iou", 0.3)),
            max_age=int(config.get("track_max_age", 30)),
        )
        # Object-based tripwires on the same camera: each becomes a directional
        # line-crossing detector fed by the tracker below.
        self.crossings = load_crossings(self.rule.camera)

    def _source_url(self):
        from apps.mediactl import client as media_client

        return media_client.build_source_url(self.rule.camera)

    def _process(self, detector, jpeg):
        if not self.gate.passes(jpeg):
            return
        raws, latency_ms = infer_frame(detector, jpeg, 0, 0)
        if not raws:
            return
        self.tracker.update(raws)  # stable track_id → real dedup/direction
        process_detections(self.rule, detector, raws, jpeg, latency_ms)
        self._check_crossings(detector, raws, jpeg)

    def _check_crossings(self, detector, raws, jpeg):
        for det_rule, crosser in self.crossings:
            for raw in raws:
                if not raw.bbox or not raw.track_id:
                    continue
                cx = raw.bbox[0] + raw.bbox[2] / 2.0
                cy = raw.bbox[1] + raw.bbox[3] / 2.0
                direction = crosser.check(raw.track_id, (cx, cy))
                if direction:
                    emit_tripwire(det_rule, detector, raw, direction, jpeg)

    def run(self):
        width = 640
        detector = registry.get_detector("object")
        if detector is None:
            logger.info("cam %s: no active object model, worker idle", self.rule.camera_id)
            return
        if getattr(detector, "model", None) is not None:
            width = int(getattr(detector.model, "input_w", 640))
        while not self.stop_event.is_set():
            try:
                with RtspFrameSource(self._source_url(), fps=self.fps, width=width) as src:
                    for jpeg in src:
                        if self.stop_event.is_set():
                            break
                        self._process(detector, jpeg)
            except Exception as exc:  # decode/stream failure → reconnect
                logger.warning("cam %s inference stream error: %s", self.rule.camera_id, exc)
            if not self.stop_event.is_set():
                self.stop_event.wait(self.backoff)  # backoff before reconnect


class InferenceService:
    def __init__(self):
        self.stop_event = threading.Event()
        self.workers = []

    def start(self):
        rules = plan()
        logger.info("inference service starting: %d camera(s)", len(rules))
        for rule in rules:
            w = CameraWorker(rule, self.stop_event)
            w.start()
            self.workers.append(w)
        return len(self.workers)

    def stop(self):
        self.stop_event.set()
        for w in self.workers:
            w.join(timeout=10)

    def run_forever(self, poll=2.0):
        self.start()
        try:
            while not self.stop_event.is_set():
                time.sleep(poll)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
