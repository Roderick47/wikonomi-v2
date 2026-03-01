#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:10000
