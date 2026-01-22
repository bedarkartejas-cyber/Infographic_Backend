# Use a slim version of Python 3.11 for a smaller, faster image
FROM python:3.11-slim

# Create a non-root user for security compliance in production
RUN useradd -m appuser

# Set the working directory
WORKDIR /app

# Install essential system dependencies and clean up cache to keep image small
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies as root to allow caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure the application is owned by the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Health check using the PORT environment variable provided by the host
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Expose the dynamic port (Railway/Render inject this automatically)
EXPOSE $PORT

# Start the application using Gunicorn with Uvicorn workers
# Note: Workers should be adjusted based on the available CPU (usually 2-4 for small instances)
CMD ["gunicorn", "app:app", \
     "--workers=2", \
     "--worker-class=uvicorn.workers.UvicornWorker", \
     "--bind=0.0.0.0:$PORT", \
     "--timeout=600", \
     "--log-level=info"]