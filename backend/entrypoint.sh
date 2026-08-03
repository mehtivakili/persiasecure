#!/usr/bin/env bash
set -e

echo "==> PersianSecure backend starting (RUN_MODE=${RUN_MODE:-web})"

# Wait for the database
python - <<'PY'
import os, time, socket
host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print("Database is up.")
            break
    except OSError:
        print("Waiting for database...")
        time.sleep(2)
else:
    raise SystemExit("Database not reachable")
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput || true

# Demo data is explicit opt-in. Production startup must never create default
# credentials, a synthetic camera, or random analytics behind the operator's
# back. Use Django's createsuperuser command for a real installation.
if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
    python manage.py seed_demo
fi

if [ "${RUN_MODE}" = "web" ]; then
    # ASGI server (HTTP + WebSocket via Channels)
    exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 2
else
    exec "$@"
fi
