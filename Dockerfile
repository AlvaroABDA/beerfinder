FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8080

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

RUN useradd -m -u 1000 beerapp \
    && mkdir -p /app/backend/private_uploads/claims /app/backend/data \
    && chown -R beerapp:beerapp /app

USER beerapp
WORKDIR /app/backend

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "python -m app.bootstrap && exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 60 wsgi:app"]
