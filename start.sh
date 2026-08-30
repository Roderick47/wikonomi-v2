#!/bin/bash
cd wikonomi
python manage.py migrate
python manage.py generate_default_og_image
python manage.py collectstatic --noinput
# Start the ASGI application so Django and the streamable HTTP MCP endpoint
# share the same deployment and database connection settings.
uvicorn wikonomi.asgi:application --host 0.0.0.0 --port "${PORT:-10000}" --workers 1 --timeout-keep-alive 75
