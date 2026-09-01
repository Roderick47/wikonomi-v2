from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    """Check ASGI/Django and database readiness without exposing configuration."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except DatabaseError:
        response = HttpResponse('unavailable', status=503, content_type='text/plain')
    else:
        response = HttpResponse('ok', content_type='text/plain')
    response['Cache-Control'] = 'no-store'
    return response
