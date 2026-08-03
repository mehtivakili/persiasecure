# PersianSecure — Supervisor Report

**Date:** 3 August 2026
**In one line:** We took a camera system that *looked* finished but didn't really
work under the hood, and we made the core actually work — recording, finding
footage, reviewing alarms with video, exporting evidence, and basic security —
then set up clean groundwork for AI without switching it on yet.

This report is written in plain language on purpose. If you want a deeper,
technical version, it's all in `docs/optimization-plan.md` and the step‑by‑step
`docs/journey.md`.

---

## The situation we started with

Think of a security camera system as a chain:

> **Camera records → you can find the footage → an alarm shows you the video →
> you can export it as evidence → and it's all secure.**

When we started, the app had nice screens for all of this, but several links in
the chain were broken or fake:

- **Adding a camera often didn't actually start recording.** You could pick
  "record continuously," save, and nothing was recorded — the setting was quietly
  ignored for new cameras.
- **The recording "modes" were just labels.** "Motion," "Scheduled," and
  "Continuous" all did the same thing behind the scenes. There was no real
  schedule, no motion buffer.
- **Alarms had no video.** When motion or a tripwire fired, you got a still
  picture at best — never a clip showing what happened before and after.
- **You couldn't review a day of footage.** The playback page showed at most 25
  one‑minute pieces and made you click each one; a full day looked like 25
  minutes.
- **Security gaps.** Camera passwords were stored as plain readable text, and a
  powerful "control" port on the media server was left open to the network.
- **Live view was flaky** — a camera often wouldn't appear until you navigated
  away and came back.

In short: it demoed well, but the things a real operator needs every day didn't
hold up.

---

## What we did (in plain terms)

We worked through the project in the planned order, fixing the foundation first.
Here's what changed, grouped by what it means for a user.

### 1. Cameras that actually record, added through a proper wizard
- Adding a camera now walks you through a clear step‑by‑step wizard: connection →
  test the connection → pick the video quality → choose the recording policy →
  review and see the live picture.
- The camera **and** its recording setting are now saved together as one unit —
  the "it saved but didn't record" bug is gone.
- If the connection fails, you get a **plain reason** ("wrong password,"
  "can't reach the host," "unsupported video format") instead of a silent failure.
- **Camera passwords are now encrypted**, so they're no longer sitting in the
  database as readable text.

### 2. The recording modes are now real
- **Continuous, Scheduled, Motion, and Manual** each behave differently now.
- **Scheduled** records only during the weekly time windows you set (there's an
  editor for the days/hours).
- **Motion** keeps a short rolling buffer so we can capture the moments *before*
  something happens.
- **Manual** gives operators a plain **Start/Stop recording button** — on the
  camera list and while watching live — instead of burying it in a settings dialog.
- The system now warns you when **disk space is running low**, protects footage
  that's marked as evidence, and keeps recording correctly even after a restart.

### 3. Alarms now come with video
- When an event happens on a recording camera, the system automatically builds a
  short **clip that includes the seconds before and after** the event.
- On the Events page you can **play the clip, retry it if it failed, or lock it**
  for legal hold. There's also a "Mark test event" button so you can try it.

### 4. A real playback timeline
- The playback page is now a proper **24‑hour timeline** you can scrub through.
- It **plays continuously** across the one‑minute pieces — you pick a time and it
  just plays, no clicking individual files.
- You get **speed control, skip forward/back, jump to the next/previous alarm,
  snapshots, bookmarks**, and you can **export an exact time range**.

### 5. Investigating an alarm in one place
- Click any event and a **detail panel** opens with everything: the snapshot, the
  video clip, buttons to **jump straight into playback or the live camera at that
  moment**, acknowledge/clear, **assign it to a person, add comments**, see
  **related alarms from the same camera**, and a full **history of who did what**.
- The list has proper **filters** (search, camera, type, severity, whether it has
  a clip).

### 6. Security and day‑to‑day operations
- **Closed the exposed control port** on the media server (a real security hole).
- **Encrypted the SMS/notification provider keys** too.
- Added **login rate‑limiting** to slow down password‑guessing attacks.
- New **Exports page** to track and download your evidence exports, each with a
  **checksum** (a fingerprint that proves the file wasn't tampered with).
- The **Health page** now shows storage used per camera and an estimate of **how
  many days of recording you have left**.
- Wrote an **operations runbook** (`docs/operations.md`) with the exact commands
  to **back up and restore** everything, and a tool to **rotate the encryption
  key** safely.

### 7. Groundwork for AI (not switched on yet)
- We defined a single, clean **"contract"** that any future AI detector (plate
  reader, fire/smoke, object detection) must follow, and a pipeline that applies
  sensible controls (confidence threshold, detection zones, ignoring duplicates).
- Critically, **AI runs in its own separate lane** so heavy AI processing can
  never slow down the actual recording. There's also a **"report false positive"**
  button so operators can tell the system when it's wrong.
- We intentionally **did not turn on real AI models** — that's the next step, and
  only makes sense now that the recording core is trustworthy.

---

## What you'll see when you open the app

Start it with the demo profile (so there's a working test camera):

```bash
docker compose --profile demo up --build
```

Open **http://localhost:8080** and log in, then:

- **Cameras** → *Add camera* → the new step‑by‑step wizard, plus a red
  **record** button on each camera row.
- **Live View** → cameras load reliably now, with a **Start/Stop recording** button.
- **Playback** → pick a camera and a day → a real **timeline** you scrub and play
  straight through.
- **Events** → click any alarm → the **investigation panel** with its video clip
  and one‑click jump to playback. Try the **"Mark test event"** button.
- **Exports** (new menu item) → your evidence exports with status and download.
- **Health** → storage per camera and "days remaining."

---

## Why this mattered (the important part)

The old version was a good‑looking shell. The moment someone tried to *rely* on
it — "show me what happened at the front gate at 2 a.m." — it fell apart, because
the recording, the footage review, and the alarm‑to‑video link weren't actually
there.

Everything we did rebuilds exactly that trust:

- A camera you add **records**.
- Footage you need, you can **find and watch**.
- An alarm gives you **the video**, not just a note.
- Evidence you export is **provable** (checksums) and **recoverable** (backups).
- Sensitive data is **encrypted** and obvious holes are **closed**.

And this is *why we deliberately held back the flashy AI features*. Plate reading
or fire detection is worthless — even dangerous — if it sits on a system that
doesn't reliably record or let you check the footage. We fixed the foundation
first, on purpose. Now AI can be added safely, on top of something that actually
works.

---

## Honest status — what's proven and what's left

**Proven:**
- The frontend (the whole user interface) builds cleanly and passes its checks.
- The backend has an automated test suite that is **green — 70 out of 70 tests
  passing** — covering the risky logic (recording rules, event clips, playback,
  tenancy/isolation, encryption, key rotation, and the AI‑detector groundwork).
  *(These were run after Docker was restarted; the earlier note about the last two
  pieces being "not yet re‑run" is now resolved.)*

**Still needed for full sign‑off:**
- A **real‑camera acceptance test** — plugging in an actual camera and confirming
  the full flow end‑to‑end. Everything is built and unit‑tested for it, but a live
  hardware run is the final proof.
- Ongoing **failure drills** (power loss, disk full) as an operational checklist —
  the app already handles these, but they should be exercised on staging.

---

## Where the project stands

All eight planned phases (0 through 7) are implemented. In plain terms: **the core
video‑surveillance system now genuinely works and is secured, and the door is open
for real AI as the next, separate step** — which the plan (rightly) said should
only begin once the foundation is trustworthy. It now is.

The full record of every change, every problem hit, and how each was fixed is in
`docs/journey.md`.
