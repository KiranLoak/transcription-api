#!/bin/sh

echo "Waiting for database..."

until python -c "
import os
import sys
from sqlalchemy import create_engine, text

url = os.environ.get('DATABASE_URL', '')

if not url:
    sys.exit(1)

engine = create_engine(url)

with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
"
do
  sleep 2
done

echo "Running migrations..."
alembic upgrade head

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000