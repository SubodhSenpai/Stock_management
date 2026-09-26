# ── Build stage: install Python dependencies ───────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ──────────────────────────────────────────────────────
FROM python:3.11-slim

# Non-root user for production safety.
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

# Installed packages from the builder stage.
COPY --from=builder /install /usr/local

# Application source.
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

# Alembic needs write access to its __pycache__; the rest is read-only.
RUN chown -R app:app /app
USER app

EXPOSE 8000

# Uvicorn with 4 workers, one per core (tune via UVICORN_WORKERS env var).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4}"]
