#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py collectstatic --noinput
# Start gunicorn immediately - bind to port 10000
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:10000 --timeout 120
