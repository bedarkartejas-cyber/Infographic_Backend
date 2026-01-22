#!/bin/bash

# Validate environment variables
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

required = ['A2E_API_KEY', 'A2E_BASE_URL', 'OPENAI_API_KEY', 
            'SUPABASE_URL', 'SUPABASE_SERVICE_KEY']

missing = [var for var in required if not os.getenv(var)]
if missing:
    print(f'ERROR: Missing required environment variables: {missing}')
    exit(1)

print('All required environment variables are set')
"

# Run migrations/initialization if needed
python -c "
from supabase_config import supabase_config
if supabase_config.is_configured():
    print('Supabase connected successfully')
else:
    print('Warning: Supabase connection failed')
"

# Start Gunicorn
exec gunicorn app:app \
    --workers ${WORKERS:-2} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind ${HOST:-0.0.0.0}:${PORT:-5000} \
    --timeout 600 \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL:-info}