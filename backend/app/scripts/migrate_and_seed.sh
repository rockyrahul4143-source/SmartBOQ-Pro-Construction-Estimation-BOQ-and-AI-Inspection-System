#!/bin/sh
# migrate_and_seed.sh
# Called by docker-compose entrypoint — waits for DB, runs migrations, seeds.
set -e

echo "⏳ Waiting for PostgreSQL..."
until python -c "import psycopg2; psycopg2.connect('${DATABASE_URL}')" 2>/dev/null; do
  sleep 1
done
echo "✅ PostgreSQL is ready"

echo "🔄 Running Alembic migrations..."
alembic upgrade head

echo "🌱 Running seed data..."
python -m app.scripts.seed_data

echo "🚀 Starting SmartBOQ Pro API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
