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
# Create superuser if none exists (for admin access)
python manage.py shell << EOF
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@wikonomi.com', 'admin123')
    print("Created superuser: admin/admin123")
else:
    print("Superuser already exists")
EOF
# Start gunicorn immediately
gunicorn wikonomi.wsgi:application --bind 0.0.0.0:10000
