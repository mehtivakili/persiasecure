"""
`manage.py run_inference` — the continuous AI inference worker (Phase AI-1).

Run inside the dedicated inference service (`docker compose --profile gpu`). It
decodes every eligible camera's RTSP at a controlled FPS, motion-gates, runs the
active object model, tracks, and ingests detections through the Phase-7 pipeline.

    manage.py run_inference           # run until SIGTERM
    manage.py run_inference --list    # print the cameras that would run, then exit
"""
import logging
import signal
import sys

from django.core.management.base import BaseCommand

from apps.analytics.inference.loop import InferenceService, plan


def _setup_logging():
    """Route the inference logs (per-detection "found N objects [...]") to stdout
    so they show in `docker compose logs inference-worker`."""
    log = logging.getLogger("apps.analytics")
    log.setLevel(logging.INFO)
    if not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(h)
        log.propagate = False


class Command(BaseCommand):
    help = "Run the continuous AI inference loop (object detection)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--list", action="store_true",
            help="List the cameras that would be processed and exit.",
        )

    def handle(self, *args, **opts):
        if opts["list"]:
            rules = plan()
            if not rules:
                self.stdout.write("No eligible cameras (feature off, no active model, or no object rules).")
                return
            for r in rules:
                self.stdout.write(f"cam {r.camera_id}  {r.camera.name}  fps={ (r.config or {}).get('fps', 5) }")
            self.stdout.write(self.style.SUCCESS(f"{len(rules)} camera(s) eligible."))
            return

        _setup_logging()
        service = InferenceService()

        def _shutdown(signum, frame):
            self.stdout.write("shutting down inference service…")
            service.stop_event.set()

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        count = service.start()
        self.stdout.write(self.style.SUCCESS(f"inference running on {count} camera(s)."))
        service.run_forever()
