Keep Django + React, but freeze sophisticated AI work until the VMS foundation is trustworthy. The current recording system has models and UI, but several modes are only labels and the event-to-video workflow does not exist yet.

## Critical issues already confirmed

1. **Recording mode on a new camera can be ignored.** The camera dialog only updates an existing recording schedule; it does not create one for a new camera. See [CameraDialog.tsx](C:/Users/a.rezaeei/persiansecure/frontend/src/features/cameras/CameraDialog.tsx:142).

2. **“Motion” and “scheduled” recording are not implemented.** The backend enables MediaMTX recording for every mode except `off`, making all of them effectively continuous. See [views.py](C:/Users/a.rezaeei/persiansecure/backend/apps/recordings/views.py:25).

3. **Pre-event and post-event values are unused.** They exist in [models.py](C:/Users/a.rezaeei/persiansecure/backend/apps/recordings/models.py:15), but no worker creates an event clip.

4. **Events only contain snapshots.** There is no event-to-recording or event-to-clip relationship in [events/models.py](C:/Users/a.rezaeei/persiansecure/backend/apps/events/models.py:25).

5. **Manual start/stop recording is missing.**

6. **Playback only receives the first API page.** Django defaults to 25 results, while the frontend discards pagination metadata. With 60-second segments, a day can appear to contain only 25 minutes.

7. **Export is incomplete.** The UI submits an export and then provides no job status or download workflow. The backend concatenates complete segments rather than precisely trimming the selected range.

8. **Browser seeking is questionable.** The backend advertises byte ranges but does not properly implement HTTP `Range` responses.

9. **Recording policies have no validation.** There is no real weekly schedule evaluator, disk quota protection, segment health verification, or event retention policy.

10. **Security needs work.** Camera passwords are stored as plain database strings, tenant ownership is not consistently validated during related-object creation, and MediaMTX’s control API is exposed on port `9997` while allowing broad API access.

## Target recording architecture

Django should coordinate recording, not carry the video bytes itself:

```text
Camera
   │ RTSP
   ▼
MediaMTX ── writes short segments ──▶ rolling recording storage
                                           │
Detection/manual event ──▶ Event created   │
                              │             │
                              ▼             ▼
                        Clip assembly worker
                              │
                              ▼
                    EventClip + protected MP4
                              │
                 React Event/Playback pages
```

Pre-event recording requires a rolling buffer. You cannot capture five seconds before an event if recording only starts after the event.

For event-based recording, MediaMTX should continuously write short segments—approximately 2–10 seconds—and the system should:

- Keep recent segments temporarily.
- On an event, preserve segments from `event time - pre_event`.
- Wait until `event time + post_event`.
- Assemble an exact event clip.
- Delete unneeded temporary segments later.
- Keep the event clip according to its own retention/legal-hold policy.

## Implementation plan

### Phase 0 — Establish a trustworthy baseline

Estimated: 2–4 days.

- Recreate the broken Python virtual environment; the current `.venv` references another Windows user.
- Add CI for backend tests, migrations, frontend type checking, and production build.
- Pin Docker image versions, especially MediaMTX.
- Remove runtime `makemigrations`; migrations should be created during development and only applied at startup.
- Hide synthetic AI results outside explicit demo mode.
- Put unfinished modules behind feature flags instead of presenting them as working functionality.
- Define the supported baseline:
  - H.264 and H.265
  - RTSP over TCP
  - ONVIF onboarding
  - Continuous, scheduled, manual, and event recording
  - Local/NAS storage initially

Exit condition: a clean installation starts reproducibly and all existing automated checks pass.

### Phase 1 — Repair camera onboarding and live view

Estimated: 4–6 days.

Turn camera creation into a reliable wizard:

1. Connection information
2. ONVIF discovery or manual RTSP
3. Connectivity test
4. Live preview
5. Codec and stream selection
6. Recording policy
7. Save and confirm status

Backend work:

- Create the camera and recording schedule atomically.
- Roll back both if MediaMTX configuration fails.
- Validate that every referenced camera belongs to the user’s organization.
- Return structured health errors: authentication failure, timeout, unsupported codec, DNS failure, or MediaMTX failure.
- Preserve camera passwords during edits without resending them to the browser.
- Encrypt camera credentials at rest.

UX work:

- Replace `window.alert`, `window.confirm`, and `window.prompt` with proper dialogs.
- Show connection progress and actionable failures.
- Add retry and refresh actions.
- Clearly distinguish camera health, live-stream availability, and recording state.

Exit condition: a user can add a real camera and confirm its live stream and recording policy in one flow.

### Phase 2 — Implement recording policies correctly

Estimated: 1–2 weeks.

Keep `RecordingSchedule`, but give every mode real semantics:

- `off`: no persistent recording
- `continuous`: record continuously
- `scheduled`: record only during configured weekly windows
- `motion/event`: maintain a short rolling buffer and preserve event clips
- `manual`: temporary operator-controlled recording session

Add:

- A schedule evaluator using the organization’s timezone.
- `start_recording` and `stop_recording` service functions.
- A `ManualRecordingSession` model containing operator, start, stop, camera, and status.
- State reconciliation after MediaMTX, Django, or server restarts.
- Idempotent segment indexing.
- Disk free-space checks and configurable low-storage alarms.
- Retention that distinguishes ordinary segments, event clips, exports, and evidence under legal hold.
- Validation limits for retention days, segment length, and pre/post durations.

Add APIs:

```text
POST /api/cameras/{id}/recording/start/
POST /api/cameras/{id}/recording/stop/
GET  /api/cameras/{id}/recording/status/
GET  /api/recordings/timeline/
```

Exit condition: every advertised mode behaves differently and survives service restarts.

### Phase 3 — Build event video capture

Estimated: 1–2 weeks.

Add an `EventClip` model:

```text
event
camera
start/end
status: pending | assembling | ready | failed
file
size
duration
sha256
error
protected_until
created_at
```

When an event is created:

1. Save the event and snapshot.
2. Queue clip creation after the database transaction commits.
3. Select rolling segments covering the pre/post window.
4. Wait for the final post-event segment.
5. Assemble and accurately trim the MP4.
6. Store duration, size, checksum, and failure reason.
7. Notify the frontend when the clip becomes ready.

Additional requirements:

- Merge or deduplicate overlapping events from the same camera.
- Retry incomplete segment assembly.
- Never delete segments used by a pending clip.
- Allow manual retry of failed clips.
- Audit clip viewing, downloading, and deletion.
- Support “protect recording” and legal hold.

Exit condition: a manual test event produces a playable clip containing video before and after the event.

### Phase 4 — Replace the playback page

Estimated: 5–8 days.

The current page is essentially a segment list. Replace it with:

- Camera selector and search
- Day/date-range navigation
- Real 24-hour timeline
- Recorded, motion/event, bookmark, and offline markers
- Continuous playback across segment boundaries
- Playback speed
- Frame stepping or short skip controls
- Jump to previous/next event
- Snapshot and bookmark controls
- Export an exact selected range
- Loading, empty, unavailable, and corrupted states

Backend improvements:

- Use overlap filtering rather than requiring a segment to start inside the requested range.
- Implement cursor pagination or a compact timeline endpoint.
- Serve playback through Nginx/internal redirects or implement proper HTTP range responses.
- Avoid streaming large video files through Django workers.
- Return signed or permission-checked playback URLs.

Exit condition: an operator can find and play any recording without manually selecting individual one-minute files.

### Phase 5 — Build an event investigation workflow

Estimated: 4–7 days.

Make event rows clickable and add an event detail page or drawer containing:

- Event type, severity, camera, and exact time
- Snapshot
- Event clip and clip-processing status
- Pre-event/post-event timeline
- “Open live camera”
- “Open in playback”
- Acknowledge, clear, comment, and assign
- Export/protect/add to evidence case
- Related events from the same camera
- Full operator audit history

Improve filtering:

- Camera/group
- Event type
- Severity
- Acknowledgement state
- Date range
- Clip availability
- Free-text search

Exit condition: operators can investigate an alarm from detection through video review and acknowledgement without moving between disconnected pages.

### Phase 6 — Complete exports, storage, security, and operations

Estimated: 1–2 weeks.

- Add an export-jobs page with queued/running/done/failed states.
- Add authenticated download endpoints.
- Trim exports to exact boundaries.
- Generate checksums and evidence metadata.
- Protect exports from normal retention.
- Add storage usage by camera and projected days remaining.
- Remove MediaMTX control API exposure from the host.
- Enforce tenant ownership in serializers and service methods.
- Encrypt camera and notification credentials.
- Add rate limiting, audit logs, secret rotation, and backup/restore.
- Add health metrics for MediaMTX, Redis, Celery, PostgreSQL, disk, cameras, and recording delay.
- Test power loss, disk full, camera reconnect, invalid credentials, and service restarts.

Exit condition: the system can be operated and recovered without manual database or filesystem repair.

### Phase 7 — Prepare the AI integration contract

Only begin sophisticated AI after the recording/event workflow passes end-to-end testing.

Define one detector contract containing:

```text
camera_id
event_type
observed_at
confidence
bounding_boxes
track_id
model_name
model_version
snapshot
metadata
```

Run AI in separate worker queues so inference cannot delay recording, exports, health checks, or alarms. Add:

- Detector health and latency
- Model/version auditability
- Confidence thresholds per camera
- Detection zones
- Duplicate suppression
- Human validation
- False-positive reporting
- GPU/CPU capacity monitoring

Then YOLO, ALPR, fire/smoke, or face models become event producers. They do not need to know how recording, event clips, playback, or retention work.

## Recommended delivery order

The most useful first milestone is:

1. Fix atomic camera + recording schedule creation.
2. Implement continuous recording reliably.
3. Add manual start/stop recording.
4. Build the recordings timeline page.
5. Add rolling buffer and event clips.
6. Connect event details to those clips.
7. Harden storage and security.
8. Introduce real AI.

For one experienced full-stack developer, a realistic core-readiness estimate is roughly **6–10 weeks**, excluding production AI work and extensive multi-brand camera certification. The strongest first implementation slice is Phases 0–3; it delivers real recording and event video rather than another set of partially accessible screens.