#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py collectstatic --noinput
# Create all media directories if they don't exist
mkdir -p /var/data/media/profile_pics
mkdir -p /var/data/media/product_images
mkdir -p /var/data/media/business_images
mkdir -p /var/data/media/price_report_images
# Set correct permissions (use sudo if needed)
sudo chmod 755 /var/data/media || chmod 755 /var/data/media
sudo chmod 755 /var/data/media/profile_pics || chmod 755 /var/data/media/profile_pics
sudo chmod 755 /var/data/media/product_images || chmod 755 /var/data/media/product_images
sudo chmod 755 /var/data/media/business_images || chmod 755 /var/data/media/business_images
sudo chmod 755 /var/data/media/price_report_images || chmod 755 /var/data/media/price_report_images
# List directories to verify
ls -la /var/data/media/
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:10000
