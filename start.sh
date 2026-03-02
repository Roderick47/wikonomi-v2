#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py collectstatic --noinput
# Create media directories only if they don't exist
mkdir -p /var/data/media/profile_pics
mkdir -p /var/data/media/product_images
mkdir -p /var/data/media/business_images
mkdir -p /var/data/media/price_report_images
# Set permissions
chmod 755 /var/data/media/profile_pics
chmod 755 /var/data/media/product_images
chmod 755 /var/data/media/business_images
chmod 755 /var/data/media/price_report_images
# Start gunicorn immediately
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:10000
