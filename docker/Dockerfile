# =============================================================================
# Reptilia Service Dockerfile
# =============================================================================
# Multi-stage build for smaller final image
# Build context should be set to project root in docker-compose

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies (use Docker-specific requirements without macOS packages)
COPY service/requirements-docker.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-docker.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies for BLE support
RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez \
    bluetooth \
    libbluetooth-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY service/ .

# Set Python path to include the service directory
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default environment variables (override in docker-compose or docker run)
ENV MONGODB_URI=mongodb://mongodb:27017
ENV MONGODB_DATABASE=reptilia

# Run the application
CMD ["python", "main.py"]
