# Dockerfile for the Nativa Telegram bot.
#
# Uses Python 3.11-slim to keep the image small (no build tools needed).
# The bot is a pure-Python application with no compiled extensions.

# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
# We only need pip — no system packages required.
# --no-install-recommends keeps the layer small.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
# Copy requirements first so Docker can cache this layer separately.
# The layer is only invalidated when requirements.txt changes.
COPY requirements.txt .

# Install dependencies without caching wheels to keep image size down
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
# Copy the bot source after dependencies so code changes don't bust the
# pip cache layer.
COPY bot.py .

# ── Runtime configuration ─────────────────────────────────────────────────────
# Environment variables are injected at runtime via docker-compose env_file.
# Do NOT bake secrets into the image.

# Run as a non-root user for security
RUN adduser --disabled-password --gecos "" botuser
USER botuser

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Run bot.py directly; Python buffering is disabled (-u) so logs appear
# immediately in docker logs / compose output.
CMD ["python", "-u", "bot.py"]
