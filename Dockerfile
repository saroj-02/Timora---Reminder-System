# ── Timora Container Image ──────────────────────────────────────────────────
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Generate icons if not already present
RUN python3 scripts/generate_icons.py

# Expose port
EXPOSE 8000

# Render provides PORT for web services; keep 8000 as the local default.
CMD ["sh", "-c", "exec uvicorn app.main:fast_api --host 0.0.0.0 --port ${PORT:-8000}"]
