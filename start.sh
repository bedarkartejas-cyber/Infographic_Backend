#!/bin/bash

# 1. Validate Environment Variables
python3 -c "
import os
import sys
required = ['A2E_API_KEY', 'A2E_BASE_URL', 'OPENAI_API_KEY', 'SUPABASE_URL', 'SUPABASE_SERVICE_KEY', 'SUPABASE_JWT_SECRET']
missing = [var for var in required if not os.getenv(var)]
if missing:
    print(f'CRITICAL ERROR: Missing variables: {missing}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then exit 1; fi

# 2. Start Gunicorn
echo "Starting Gunicorn on port ${PORT:-5000}..."
exec gunicorn app:app \
    --workers ${WORKERS:-2} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-5000} \
    --timeout 600
