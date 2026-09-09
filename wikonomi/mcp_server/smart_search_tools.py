from decimal import Decimal
from typing import Any, Literal

from asgiref.sync import sync_to_async
from mcp.types import ToolAnnotations
from pydantic import Field

from . import services
from .models import MCPUserAccess
from .permissions import READ_SCOPE
from .smart_search_policy import search_products


READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)


def _oauth_meta():
    return {'securitySchemes': [{'type': 'oauth2', 'scopes': [READ_SCOPE]}]}


def register_smart_search_tools(mcp):
    @mcp.tool(
        title='Search Wikonomi products intelligently',
        meta=_oauth_meta(),
        description=(
            'Read-only structured product discovery. Use this when barcode, brand, pack size, category, '
            'fresh-price requirements, or exact-vs-alternative control matters. Natural shopping language is supported.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def search_products(
        query: str = Field(min_length=1, max_length=300),
        brand: str = Field(default='', max_length=120),
        variant: str = Field(default='', max_length=160),
        barcode: str = Field(default='', max_length=64),
        package_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3),
        package_unit: Literal['', 'g', 'kg', 'ml', 'l', 'each', 'm', 'cm', 'other'] = '',
        pack_count: int | None = Field(default=None, ge=1, le=10000),
        category_id: int | None = Field(default=None, ge=1),
        include_alternatives: bool = True,
        current_only: bool = False,
        limit: int = Field(default=10, ge=1, le=50),
    ) -> dict[str, Any]:
        arguments = {
            'query': query,
            'brand': brand,
            'variant': variant,
            'barcode': barcode,
            'package_quantity': package_quantity,
            'package_unit': package_unit,
            'pack_count': pack_count,
            'category_id': category_id,
            'include_alternatives': include_alternatives,
            'current_only': current_only,
            'limit': limit,
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'search_products',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: search_products(**arguments),
        )
