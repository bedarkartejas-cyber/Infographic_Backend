#!/bin/bash
set -e  # Exit on error

echo "=================================================="
echo "🚀 Starting Marketing Generator API"
echo "=================================================="

# 1. Validate Environment Variables
echo "🔍 Validating environment variables..."
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
    print(f'❌ CRITICAL ERROR: Missing required environment variables:')
    for var in missing:
        print(f'   - {var}')
    print()
    print('Set these in your cloud platform dashboard:')
    print('  Railway: Settings → Variables')
    print('  Render: Environment → Environment Variables')
    print('  Google Cloud Run: Edit & Deploy → Variables')
    sys.exit(1)

print('✅ All required environment variables are set')
print(f'   Environment: {os.getenv(\"ENVIRONMENT\", \"production\")}')
print(f'   Port: {os.getenv(\"PORT\", \"5000\")}')
print(f'   Workers: {os.getenv(\"WORKERS\", \"2\")}')
"

# Check if validation passed
if [ $? -ne 0 ]; then 
    echo "❌ Startup aborted due to missing configuration"
    exit 1
fi

# 2. Set defaults for optional variables
export ENVIRONMENT=${ENVIRONMENT:-production}
export PORT=${PORT:-5000}
export WORKERS=${WORKERS:-2}
export LOG_LEVEL=${LOG_LEVEL:-info}

echo ""
echo "📋 Configuration:"
echo "   Environment: $ENVIRONMENT"
echo "   Port: $PORT"
echo "   Workers: $WORKERS"
echo "   Log Level: $LOG_LEVEL"
echo ""

# 3. Test Python imports (quick validation)
echo "🔍 Testing Python module imports..."
python3 -c "
try:
    import fastapi
    import uvicorn
    import gunicorn
    import openai
    import supabase
    print('✅ All Python dependencies available')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')
    exit(1)
" || exit 1

# 4. Start Gunicorn
echo ""
echo "=================================================="
echo "🚀 Starting Gunicorn server..."
echo "=================================================="

exec gunicorn app:app \
    --workers ${WORKERS} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT} \
    --timeout 600 \
    --keep-alive 5 \
    --log-level ${LOG_LEVEL} \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance
