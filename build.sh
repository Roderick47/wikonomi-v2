#!/usr/bin/env bash

# Install dependencies
pip install -r requirements.txt

# Collect static files for production
python wikonomi/manage.py collectstatic --noinput

# Run migrations
python wikonomi/manage.py migrate --noinput
