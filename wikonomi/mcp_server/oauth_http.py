"""OAuth HTTP compatibility without changing the MCP SDK's authentication checks."""

from functools import partial

from mcp.server.auth.middleware.client_auth import AuthenticationError, ClientAuthenticator
from mcp.server.transport_security import DEFAULT_MAX_REQUEST_BODY_SIZE, RequestBodyLimitMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, request_response


def install_revocation_route(app, provider):
    """Accept RFC 7009 public clients without a fabricated client_secret field.

    MCP SDK 2.1.1's revocation request model treats the nullable client_secret
    as required even for public clients and HTTP Basic authentication. Keep
    the SDK authenticator, token binding, body limit, and CORS behavior while
    avoiding that unnecessary form-field requirement.
    """
    authenticator = ClientAuthenticator(provider)
    no_cache = {'Cache-Control': 'no-store', 'Pragma': 'no-cache'}

    async def revoke(request):
        try:
            client = await authenticator.authenticate_request(request)
        except AuthenticationError as exc:
            return JSONResponse(
                {'error': 'unauthorized_client', 'error_description': exc.message},
                status_code=401, headers=no_cache,
            )
        form = await request.form()
        raw_token = form.get('token')
        if not isinstance(raw_token, str) or not raw_token:
            return JSONResponse(
                {'error': 'invalid_request', 'error_description': 'A token is required.'},
                status_code=400, headers=no_cache,
            )
        loaders = [provider.load_access_token, partial(provider.load_refresh_token, client)]
        if form.get('token_type_hint') == 'refresh_token':
            loaders.reverse()
        token = None
        for loader in loaders:
            token = await loader(raw_token)
            if token is not None:
                break
        if token is not None and token.client_id == client.client_id:
            await provider.revoke_token(token)
        # Unknown, already-revoked, and other clients' tokens must not disclose
        # whether a credential exists. The provider revokes the whole family.
        return Response(status_code=200, headers=no_cache)

    endpoint = CORSMiddleware(
        RequestBodyLimitMiddleware(request_response(revoke), DEFAULT_MAX_REQUEST_BODY_SIZE),
        allow_origins=['*'],
        allow_methods=['POST', 'OPTIONS'],
        allow_headers=['MCP-Protocol-Version'],
    )
    for index, route in enumerate(app.router.routes):
        if getattr(route, 'path', None) == '/revoke':
            app.router.routes[index] = Route(
                '/revoke', endpoint=endpoint, methods=['POST', 'OPTIONS'], name=route.name,
            )
            return
    raise RuntimeError('The expected MCP OAuth revocation route was not registered.')
