# ============================================================
# Stage 1: builder
# Install all Python dependencies into /install.
# This stage is discarded after the build — only /install is
# copied forward, keeping the final image lean.
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed by some packages (cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first so this layer is cached
# as long as requirements.txt hasn't changed.
COPY requirements.txt .

# Install packages into /install (not system-wide).
# --no-compile skips .pyc generation here; we do it in runtime.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ============================================================
# Stage 2: runtime
# Minimal production image — only the app code and the deps
# installed above. No build tools, no caches.
# ============================================================
FROM python:3.11-slim AS runtime

# libpq-dev runtime component (needed by psycopg2-binary at import time)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create a non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8000

# Production-grade startup:
# - --host 0.0.0.0  → bind to all interfaces (required inside a container)
# - --workers 2     → 2 worker processes (tune to 2*CPU+1 in prod)
# - --no-access-log → reduce log noise (access logs come from the Ingress)
# - no --reload     → never use reload in production
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--no-access-log"]
