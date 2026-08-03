FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ffmpeg for snapshots/motion, plus build deps for onvif/psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh || true

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
