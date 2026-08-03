"""
The detector contract (Phase 7).

Any AI detector — YOLO, ALPR, fire/smoke, face — produces `Detection`s in this
one shape and hands them to `pipeline.ingest_detection`. Detectors never need to
know how recording, event clips, playback or retention work; they are pure event
producers. This decouples model work from the trustworthy VMS core.
"""
from dataclasses import dataclass, field
from typing import Optional

from rest_framework import serializers


@dataclass
class Detection:
    camera_id: int
    event_type: str                 # motion | object | alpr | fire | smoke | tripwire | face | ...
    confidence: float               # 0..1
    observed_at: Optional[object] = None          # datetime; defaults to now
    bounding_boxes: list = field(default_factory=list)  # [[x, y, w, h], ...] normalized 0..1
    track_id: str = ""              # stable id across frames (for dedup/tracking)
    model_name: str = ""
    model_version: str = ""
    snapshot: Optional[bytes] = None
    metadata: dict = field(default_factory=dict)   # label, plate, zone, gpu, etc.


class DetectionSerializer(serializers.Serializer):
    """Validates a detection arriving over the wire (e.g. an external detector)."""

    camera_id = serializers.IntegerField()
    event_type = serializers.CharField(max_length=12)
    confidence = serializers.FloatField(min_value=0.0, max_value=1.0)
    observed_at = serializers.DateTimeField(required=False)
    bounding_boxes = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()),
        required=False,
        default=list,
    )
    track_id = serializers.CharField(required=False, allow_blank=True, default="")
    model_name = serializers.CharField(required=False, allow_blank=True, default="")
    model_version = serializers.CharField(required=False, allow_blank=True, default="")
    metadata = serializers.DictField(required=False, default=dict)

    def to_detection(self) -> Detection:
        d = self.validated_data
        return Detection(
            camera_id=d["camera_id"],
            event_type=d["event_type"],
            confidence=d["confidence"],
            observed_at=d.get("observed_at"),
            bounding_boxes=d.get("bounding_boxes", []),
            track_id=d.get("track_id", ""),
            model_name=d.get("model_name", ""),
            model_version=d.get("model_version", ""),
            metadata=d.get("metadata", {}),
        )
