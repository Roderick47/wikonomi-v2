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
# Create a test file to verify disk is working
echo "Disk test file" > /var/data/media/test.txt
echo "=== Disk Test ==="
cat /var/data/media/test.txt
echo "=== Directory Listing ==="
ls -la /var/data/media/
# Start gunicorn
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:10000
