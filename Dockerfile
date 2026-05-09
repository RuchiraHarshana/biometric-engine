# ── Stage: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /install

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies needed to compile psycopg2 and opencv bindings
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install all dependencies into a prefix so we can copy them cleanly
RUN sed 's/^opencv-python==/opencv-python-headless==/g' requirements.txt > requirements.docker.txt \
    && pip install --no-cache-dir --prefix=/install/deps -r requirements.docker.txt


# ── Stage: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime system libraries needed by opencv-headless and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install/deps /usr/local

# Copy application source
COPY app/ ./app/
COPY static/ ./static/

# Cloud Run injects PORT (default 8080); app must listen on 0.0.0.0
ENV PORT=8080
EXPOSE 8080

# Use shell form so $PORT is expanded at runtime
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
