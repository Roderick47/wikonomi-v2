#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py collectstatic --noinput
# Create media directory if it doesn't exist
mkdir -p /var/data/media
mkdir -p /var/data/media/profile_pics
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:10000
