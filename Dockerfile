FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p local_images && chmod 755 local_images

# Health check - Railway uses PORT environment variable
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Expose port (Railway uses dynamic port)
EXPOSE $PORT

# Run the application - Railway will inject PORT automatically
CMD ["gunicorn", "app:app", "--workers=2", "--worker-class=uvicorn.workers.UvicornWorker", "--bind=0.0.0.0:$PORT", "--timeout=600", "--log-level=info"]
