#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py collectstatic --noinput
# Create all media directories if they don't exist
mkdir -p /var/data/media/profile_pics
mkdir -p /var/data/media/product_images
mkdir -p /var/data/media/business_images
mkdir -p /var/data/media/price_report_images
# Set permissions (without sudo to avoid startup failure)
chmod 755 /var/data/media/profile_pics
chmod 755 /var/data/media/product_images
chmod 755 /var/data/media/business_images
chmod 755 /var/data/media/price_report_images
# Debug: Check what's actually there
echo "=== Media Directory Contents ==="
ls -la /var/data/media/
echo "=== Profile Pics Contents ==="
ls -la /var/data/media/profile_pics/
echo "=== Django Settings ==="
echo "MEDIA_ROOT: $(python -c 'from django.conf import settings; print(settings.MEDIA_ROOT)')"
echo "MEDIA_URL: $(python -c 'from django.conf import settings; print(settings.MEDIA_URL)')"
# Start gunicorn
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:10000
