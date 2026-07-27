# ─── Stage 1: Builder ────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system dependencies required for pg8000 and cryptography
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Stage 2: Production ─────────────────────────────────────────────
FROM python:3.11-slim AS production

LABEL maintainer="FABOuanes"
LABEL description="FABOuanes - Application de gestion de production et ventes"

# Runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r fabuser && useradd -r -g fabuser -d /app -s /sbin/nologin fabuser

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY alembic/ alembic/
COPY alembic.ini .
COPY pyproject.toml .
COPY app/ app/
COPY templates/ templates/
COPY static/ static/
COPY launcher.py .

# Create runtime directories
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R fabuser:fabuser /app

USER fabuser

# Environment defaults (override at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FAB_HOST=0.0.0.0 \
    FAB_PORT=5000 \
    WEB_CONCURRENCY=1 \
    FAB_LOG_JSON=1

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Production entrypoint with gunicorn
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--workers", "1", \
     "--log-level", "info"]
