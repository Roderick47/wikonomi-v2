#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py collectstatic --noinput
# Use Render's PORT or default to 10000
export PORT=${PORT:-10000}
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:$PORT
