#!/bin/bash
set -e

echo "🔄 Running Alembic migrations..."
alembic upgrade head

if [ "$APP_ENV" = "production" ]; then
    echo "🔒 Running dependency security audit..."
    if command -v pip-audit &> /dev/null; then
        pip-audit --format=columns --desc=on || echo "⚠️  Dependency vulnerabilities found — review before deploying"
    fi
fi

echo "🚀 Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
