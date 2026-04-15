#!/bin/sh
# Run Alembic migrations before starting the application.
# This script is the CMD for the web process only.
# Celery worker/beat use their own CMD and do not run migrations.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Creating tables (create_all for fresh installs)..."
python -c "import asyncio; from app.core.deps import init_db; asyncio.run(init_db())"

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
