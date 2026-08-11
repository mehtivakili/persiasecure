"""
`manage.py register_detector_model` — register/activate an AI model (Phase AI-1).

Creates a `DetectorModel` row from a local weights file, computing its sha256 so
the exact artifact is auditable. Weights are NOT downloaded here (a download is a
deliberate operator action): fetch e.g. a YOLOv8n ONNX export separately, drop it
in ./models, then register it.

    manage.py register_detector_model \
        --name yolov8n --task object --path /models/yolov8n.onnx \
        --classes coco --input 640 --device cuda --activate

`--activate` deactivates other models of the same task first, so exactly one is
live per task (clean rollback: re-activate the previous row).
"""
import hashlib
import os

from django.core.management.base import BaseCommand, CommandError

from apps.analytics.inference.yolo import COCO_CLASSES
from apps.analytics.models import DetectorModel


class Command(BaseCommand):
    help = "Register (and optionally activate) an AI DetectorModel from a local weights file."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--task", required=True, choices=[c[0] for c in DetectorModel.Task.choices])
        parser.add_argument("--path", required=True, help="Path to weights inside the inference container.")
        # Not --version: Django reserves that on every management command.
        parser.add_argument("--model-version", dest="model_version", default="v1")
        parser.add_argument("--framework", default="onnx", choices=[c[0] for c in DetectorModel.Framework.choices])
        parser.add_argument("--classes", default="coco", help="'coco', or comma-separated labels.")
        parser.add_argument("--input", type=int, default=640, help="Square model input size.")
        parser.add_argument("--device", default="cpu", choices=[c[0] for c in DetectorModel.Device.choices])
        parser.add_argument("--min-confidence", type=float, default=0.35)
        parser.add_argument("--iou", type=float, default=0.45)
        parser.add_argument("--activate", action="store_true")
        parser.add_argument("--allow-missing", action="store_true", help="Register even if the weights file is absent.")

    def _classes(self, spec):
        if spec.strip().lower() == "coco":
            return list(COCO_CLASSES)
        return [c.strip() for c in spec.split(",") if c.strip()]

    def _sha256(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()

    def handle(self, *args, **opts):
        path = opts["path"]
        sha = ""
        if os.path.isfile(path):
            sha = self._sha256(path)
        elif not opts["allow_missing"]:
            raise CommandError(
                f"weights not found: {path} (use --allow-missing to register anyway)"
            )
        else:
            self.stdout.write(self.style.WARNING(f"weights not present yet: {path}"))

        model = DetectorModel.objects.create(
            name=opts["name"], task=opts["task"], version=opts["model_version"],
            framework=opts["framework"], path=path, sha256=sha,
            input_w=opts["input"], input_h=opts["input"],
            classes=self._classes(opts["classes"]),
            min_confidence=opts["min_confidence"], iou_threshold=opts["iou"],
            device=opts["device"], active=False,
        )

        if opts["activate"]:
            DetectorModel.objects.filter(task=model.task, active=True).exclude(id=model.id).update(active=False)
            model.active = True
            model.save(update_fields=["active"])

        self.stdout.write(self.style.SUCCESS(
            f"registered DetectorModel #{model.id} {model.name} {model.version} "
            f"({model.task}/{model.framework}/{model.device}) active={model.active} sha256={sha[:12] or '—'}"
        ))
