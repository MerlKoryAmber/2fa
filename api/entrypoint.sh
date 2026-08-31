#!/bin/sh
set -e
cd /app
export PYTHONPATH=/app
python scripts/pre_migrate.py
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config /app/log_config.json
