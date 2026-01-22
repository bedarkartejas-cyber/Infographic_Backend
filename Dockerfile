FROM python:3.11-slim

# Create a non-root user for security
RUN useradd -m appuser

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# FIX: Set execute permissions for the start script
RUN chmod +x /app/start.sh

# Ensure the application is owned by the non-root user
RUN chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

EXPOSE $PORT

CMD ["gunicorn", "app:app", \
     "--workers=2", \
     "--worker-class=uvicorn.workers.UvicornWorker", \
     "--bind=0.0.0.0:$PORT", \
     "--timeout=600", \
     "--log-level=info"]
