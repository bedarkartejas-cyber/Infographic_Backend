#!/bin/bash

# ==============================================================================
# Production Startup Script for Marketing Generator API
# ==============================================================================

# 1. Validate Environment Variables
# We use a Python snippet to ensure all critical secrets are present before starting.
# This prevents the container from running in a "partial" or broken state.
python3 -c "
import os
import sys

required = [
    'A2E_API_KEY', 
    'A2E_BASE_URL', 
    'OPENAI_API_KEY', 
    'SUPABASE_URL', 
    'SUPABASE_SERVICE_KEY',
    'SUPABASE_JWT_SECRET'
]

missing = [var for var in required if not os.getenv(var)]
if missing:
    print(f'CRITICAL ERROR: Missing required environment variables: {missing}')
    sys.exit(1)

print('SUCCESS: All required production environment variables are set.')
"

# If the validation failed, the script exits here.
if [ $? -ne 0 ]; then
  exit 1
fi

# 2. Supabase Connection Pre-Check
# Verify that the Supabase client can actually initialize before booting the server.
python3 -c "
try:
    from supabase_config import supabase_config
    if supabase_config.is_configured():
        print('SUCCESS: Supabase connection verified.')
    else:
        print('CRITICAL ERROR: Supabase configuration failed.')
        exit(1)
except Exception as e:
    print(f'CRITICAL ERROR: Could not initialize Supabase client: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
  exit 1
fi

# 3. Start Gunicorn (Production Server)
# - Using 'exec' ensures Gunicorn becomes PID 1, allowing it to handle SIGTERM for graceful shutdowns.
# - Workers: Recommended (2 x $CPU_CORES) + 1. 
# - Worker Class: UvicornWorker for FastAPI/Async support.
# - Timeout: Set to 600s to support long-running parallel image generation tasks.
echo "Starting Gunicorn server on port ${PORT:-5000}..."

exec gunicorn app:app \
    --workers ${WORKERS:-2} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-5000} \
    --timeout 600 \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL:-info} \
    --keep-alive 5 \
    --graceful-timeout 30