#!/usr/bin/env bash

# Install dependencies
pip install -r requirements.txt

# Generate the default social preview image before collecting static files
python wikonomi/manage.py generate_default_og_image

# Collect static files for production
python wikonomi/manage.py collectstatic --noinput

# Run migrations
python wikonomi/manage.py migrate --noinput
