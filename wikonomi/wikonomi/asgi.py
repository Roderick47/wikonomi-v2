"""
ASGI config for wikonomi project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wikonomi.settings')

django_application = get_asgi_application()

# Import only after Django has initialized its app registry. The MCP server uses
# Django models for OAuth, permissions, audit logging, and all tool operations.
from mcp_server.server import mcp_asgi_application  # noqa: E402


_MCP_STARLETTE_PATHS = {
    '/mcp',
    '/mcp/',
    '/authorize',
    '/token',
    '/register',
    '/revoke',
    '/.well-known/oauth-authorization-server',
    '/.well-known/oauth-protected-resource/mcp',
}


async def application(scope, receive, send):
    """Route MCP/OAuth traffic to the MCP SDK and everything else to Django."""
    if scope['type'] == 'lifespan':
        await mcp_asgi_application(scope, receive, send)
        return

    if scope['type'] == 'http' and scope.get('path', '').rstrip('/') in {
        path.rstrip('/') for path in _MCP_STARLETTE_PATHS
    }:
        await mcp_asgi_application(scope, receive, send)
        return

    await django_application(scope, receive, send)
