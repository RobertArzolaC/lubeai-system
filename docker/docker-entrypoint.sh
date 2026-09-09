#!/bin/sh
set -e

echo "Waiting for PostgreSQL at ${DB_HOST:-db}:${DB_PORT:-5432}..."
until python -c "import os, socket; s = socket.socket(); s.settimeout(1); s.connect((os.getenv('DB_HOST', 'db'), int(os.getenv('DB_PORT', '5432'))))" 2>/dev/null; do
  sleep 1
done

if [ "${DJANGO_MIGRATE:-0}" = "1" ]; then
  echo "Running migrations..."
  python manage.py migrate --noinput
fi

if [ "${DJANGO_COMPILEMESSAGES:-0}" = "1" ]; then
  echo "Compiling translation catalogs..."
  python manage.py compilemessages --ignore ".venv/*"
fi

if [ "${DJANGO_COLLECTSTATIC:-0}" = "1" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
