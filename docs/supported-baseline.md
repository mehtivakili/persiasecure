# Supported baseline

This document defines what PersianSecure can honestly claim before production
AI models are introduced.

## Supported core

- Django 5 / DRF is the control plane and source of truth.
- React 18 / Vite is the operator interface.
- PostgreSQL 16 stores application metadata.
- Redis 7 provides Celery transport, cache and Channels fan-out.
- MediaMTX 1.18 handles RTSP ingest, WebRTC/HLS live playback and segmented
  recording; FFmpeg handles probes, snapshots, transcoding and exports.
- RTSP cameras using H.264 are the primary supported path.
- H.265/HEVC cameras are recorded natively and transcoded on demand for web
  playback. Actual camera firmware combinations still require qualification.
- RTSP-over-TCP is the baseline transport.
- ONVIF discovery, probing and PTZ are best-effort because vendor firmware
  differs; manual RTSP configuration remains supported.
- Local Docker volumes are suitable for development and a single-node pilot,
  not yet a production backup or disaster-recovery design.

## Not production-ready yet

- Object detection, ALPR, fire and smoke analytics are not production AI.
- Motion and tripwire logic are lightweight frame-difference heuristics.
- Scheduled, event-triggered and pre/post-event recording are not complete.
- Access control, maps, federation and evidence are phase-2 modules and are
  hidden unless explicitly enabled.
- Multi-node high availability and cloud object storage are not supported.

## Availability flags

The backend includes feature availability in the authenticated user payload.
The React application hides routes and navigation when a flag is disabled.
All flags default to `0`:

```text
FEATURE_ANALYTICS
FEATURE_ACCESS_CONTROL
FEATURE_MAPS
FEATURE_FEDERATION
FEATURE_EVIDENCE
```

Demo behavior requires two separate opt-ins:

```text
SEED_DEMO_DATA=1
ENABLE_DEMO_ANALYTICS=1
FEATURE_ANALYTICS=1
```

The synthetic camera service also requires the Compose `demo` profile:

```powershell
docker compose --profile demo up --build
```

Never enable these demo switches in production.

A normal installation creates its first real organization and administrator
interactively, without a demo camera:

```powershell
docker compose exec backend python manage.py bootstrap_admin
```

## Acceptance matrix for the next phases

Every supported camera/codec combination must eventually pass: onboarding,
authentication failure reporting, live WebRTC with HLS fallback, reconnect,
continuous recording, playback, export, retention, service restart and disk
pressure. A feature is not considered supported until it has an automated or
documented repeatable acceptance test.
