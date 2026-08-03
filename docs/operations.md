# PersianSecure — Operations Runbook

Backup, restore, and secret rotation for a Docker Compose deployment. Commands
assume you run them from the repo root (where `docker-compose.yml` lives) and
that the stack is up (`docker compose ps`). Adjust `$POSTGRES_*` to match your
`.env`.

> **Golden rule:** the single most important thing to back up — beyond the
> database — is **`CREDENTIAL_ENCRYPTION_KEY`** (in `.env`). Camera RTSP passwords
> and notification provider secrets are encrypted with it. **Lose that key and
> those credentials are unrecoverable**, even with a perfect database backup.

---

## What state exists

| State | Where | Backed up by |
|-------|-------|--------------|
| Application data (cameras, schedules, events, clips index, users, audit) | Postgres volume `pgdata` | `pg_dump` (below) |
| Recorded video segments, event clips, exports | Docker volume `recordings` | volume tar (below) |
| Uploaded media (event snapshots, plate/maps images) | `backend/media/` (bind mount) | file copy / repo host backup |
| Secrets (`DJANGO_SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY`, DB + provider keys) | `.env` | store in a secret manager, **off-box** |

---

## Backup

### 1. Database (logical dump)

```bash
docker compose exec -T postgres pg_dump -U persiansecure -d persiansecure --clean --if-exists | gzip > backup/db_$(date +%F).sql.gz
```

### 2. Recorded video + clips + exports (the `recordings` volume)

```bash
docker run --rm -v persiansecure_recordings:/data -v "$PWD/backup":/backup alpine tar czf /backup/recordings_$(date +%F).tar.gz -C /data .
```

(Confirm the volume name with `docker volume ls | grep recordings` — Compose
prefixes it with the project directory, e.g. `persiansecure_recordings`.)

### 3. Uploaded media + env

```bash
tar czf backup/media_$(date +%F).tar.gz backend/media
cp .env backup/env_$(date +%F).bak   # then move the secret to a vault, not the backup dir
```

Automate the three above with cron/systemd‑timer; keep the DB dump and the
`.env`/key **in separate stores** so one leak doesn't expose both data and key.

---

## Restore

On a fresh host: `cp .env.example .env`, restore the **same**
`CREDENTIAL_ENCRYPTION_KEY` and `DJANGO_SECRET_KEY` into `.env`, then:

```bash
docker compose up -d postgres redis mediamtx
```

### 1. Database

```bash
gunzip -c backup/db_YYYY-MM-DD.sql.gz | docker compose exec -T postgres psql -U persiansecure -d persiansecure
```

### 2. Recordings volume

```bash
docker run --rm -v persiansecure_recordings:/data -v "$PWD/backup":/backup alpine sh -c "cd /data && tar xzf /backup/recordings_YYYY-MM-DD.tar.gz"
```

### 3. Media, then bring up the app

```bash
tar xzf backup/media_YYYY-MM-DD.tar.gz
docker compose up -d
```

The backend's `entrypoint.sh` runs `migrate` on start; no manual schema steps.
The recording indexer re‑indexes any restored segments idempotently, and
`resync_all_paths`/the schedule evaluator re‑push camera paths to MediaMTX — so a
restart recovers recording state without hand‑editing the DB or filesystem.

---

## Secret rotation

### `CREDENTIAL_ENCRYPTION_KEY` (camera + notification secrets)

Because credentials are encrypted with this key, rotation must **re‑encrypt** the
stored values. A management command does it safely (it decrypts with the old key
and re‑encrypts with the new one, without ever loading the value through the
wrong key):

1. Generate a new key and keep the old one to hand:
   ```bash
   python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
   ```
2. Set the **new** value as `CREDENTIAL_ENCRYPTION_KEY` in `.env` and restart the
   backend + workers so they pick it up.
3. Re‑encrypt existing rows with the **old** key as input:
   ```bash
   docker compose exec backend python manage.py reencrypt_credentials --old-key '<OLD_KEY>'
   ```
   (First‑time migration of any legacy plaintext needs no `--old-key`:
   `docker compose exec backend python manage.py reencrypt_credentials`.)

### `DJANGO_SECRET_KEY`

Rotating it invalidates issued JWTs (everyone re‑logs in) and any outstanding
**signed playback URLs** (they're re‑minted on the next timeline load — harmless).
It does **not** affect stored credentials unless `CREDENTIAL_ENCRYPTION_KEY` was
left blank (then it is derived from the secret key — set an explicit
`CREDENTIAL_ENCRYPTION_KEY` **before** rotating the secret key, and run
`reencrypt_credentials` with the derived old key).

### Database / provider credentials

Change `POSTGRES_PASSWORD` (and re‑create the role), Kavenegar/Twilio keys, etc.
in `.env`; provider keys are re‑encrypted automatically on the next save from the
Settings page, or run `reencrypt_credentials` after a key change.

---

## Failure drills (acceptance)

Run these against staging and confirm no manual DB/filesystem repair is needed:

- **Service restart:** `docker compose restart backend celery-worker mediamtx` →
  recording resumes; `system/health` recovers; `recording_delay_seconds` returns
  to near‑segment length.
- **MediaMTX restart:** paths are re‑pushed by `resync_all_paths` on the next
  worker cycle; live view auto‑reconnects.
- **Disk full:** the `check_storage` task raises a **storage** alarm; free space
  and clear old exports.
- **Camera unplugged / bad credentials:** health flips the camera **offline** and
  the wizard's connectivity test returns a structured reason (`auth`/`network`/…).
- **Power loss (hard kill):** `docker compose kill` then `up` → migrations apply,
  segments re‑index idempotently, no duplicate rows.
