FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# -----------------------------
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Create directories
RUN mkdir -p local_images && chmod 755 local_images

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Run with PORT from Render
CMD ["sh", "-c", "gunicorn app:app --workers ${WORKERS:-2} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-5000} --timeout 600 --log-level ${LOG_LEVEL:-info}"]