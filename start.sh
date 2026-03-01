#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py collectstatic --noinput
# Ensure media directories exist
mkdir -p mediafiles/profile_pics
mkdir -p mediafiles/business_images
mkdir -p mediafiles/product_images
mkdir -p mediafiles/price_report_images
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:$PORT
