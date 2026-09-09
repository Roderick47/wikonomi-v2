from typing import Any

from asgiref.sync import sync_to_async
from mcp.types import ToolAnnotations
from pydantic import Field

from . import services
from .business_intelligence_services import get_branch as get_branch_service
from .business_intelligence_services import get_business as get_business_service
from .models import MCPUserAccess
from .permissions import READ_SCOPE


READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)


def _oauth_meta():
    return {'securitySchemes': [{'type': 'oauth2', 'scopes': [READ_SCOPE]}]}


def register_business_intelligence_tools(mcp):
    @mcp.tool(
        title='Get Wikonomi business intelligence',
        meta=_oauth_meta(),
        description=(
            'Read-only business profile and market coverage. Returns branches, fresh current-price coverage, '
            'current products, business-level unassigned observations, and business-wide imported inventory. '
            'Use a product query to narrow the returned current products.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_business(
        business_id: int = Field(ge=1),
        product_query: str = Field(default='', max_length=300),
        currency: str = Field(default='PGK', min_length=3, max_length=3),
        limit: int = Field(default=50, ge=1, le=100),
        include_inventory: bool = True,
    ) -> dict[str, Any]:
        arguments = {
            'business_id': business_id,
            'product_query': product_query,
            'currency': currency,
            'limit': limit,
            'include_inventory': include_inventory,
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'get_business',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: get_business_service(**arguments),
        )

    @mcp.tool(
        title='Get Wikonomi branch intelligence',
        meta=_oauth_meta(),
        description=(
            'Read-only branch profile and exact branch price coverage. Returns branch address/contact/location and '
            'latest per-product prices for that branch. Business-wide inventory is clearly labelled and is never '
            'treated as proof that an item is stocked at this branch.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_branch(
        branch_id: int = Field(ge=1),
        product_query: str = Field(default='', max_length=300),
        currency: str = Field(default='PGK', min_length=3, max_length=3),
        limit: int = Field(default=50, ge=1, le=100),
        include_stale: bool = False,
    ) -> dict[str, Any]:
        arguments = {
            'branch_id': branch_id,
            'product_query': product_query,
            'currency': currency,
            'limit': limit,
            'include_stale': include_stale,
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'get_branch',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: get_branch_service(**arguments),
        )
