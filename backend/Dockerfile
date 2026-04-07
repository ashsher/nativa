# Nativa Backend — Multi-stage Dockerfile
#
# Stage 1 (builder): Install Python dependencies into a virtual environment.
# Stage 2 (runtime): Copy only the venv and application code into a slim image.
#
# Using a multi-stage build keeps the final image small by excluding the
# compiler toolchain and build artefacts required only during pip install.

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install system packages needed to compile asyncpg and lxml.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate a virtual environment so the installed packages are
# isolated and easy to copy to the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first so Docker can cache this layer independently of
# application code changes.
COPY requirements.txt .
COPY constraints.txt .

# Install all Python dependencies inside the virtual environment.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -c constraints.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Prevent .pyc files; keep logs streaming.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Add the virtual environment binaries to PATH.
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage.
COPY --from=builder /opt/venv /opt/venv

# Install only the runtime system libraries (no compiler toolchain).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy application source code into the image.
COPY app/ ./app/
COPY migrations/ ./migrations/

# Expose the port that uvicorn will listen on.
EXPOSE 8000

# Run the FastAPI application with uvicorn.
# - host 0.0.0.0 makes it accessible from outside the container.
# - workers 1 is safe for a single-container deployment; scale with replicas.
# - forwarded_allow_ips="*" trusts X-Forwarded-For from any proxy (adjust for production).
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--forwarded-allow-ips", "*"]
