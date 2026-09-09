from typing import Any

from asgiref.sync import sync_to_async
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from . import comparison_services, services
from .models import MCPUserAccess
from .permissions import READ_SCOPE


READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)


def _oauth_meta():
    return {'securitySchemes': [{'type': 'oauth2', 'scopes': [READ_SCOPE]}]}


class BasketItemInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    product_id: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=10000)


def register_comparison_tools(mcp):
    @mcp.tool(
        title='Compare current Wikonomi prices',
        meta=_oauth_meta(),
        description=(
            'Read-only. Compare the latest-known valid price per store or branch for one exact product. '
            'Stale observations remain visible but cannot determine the current winner or savings.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def compare_current_prices(
        product_id: int = Field(ge=1),
        currency: str = Field(default='PGK', min_length=3, max_length=3),
    ) -> dict[str, Any]:
        arguments = {'product_id': product_id, 'currency': currency}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'compare_current_prices',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: comparison_services.compare_current_prices(product_id, currency),
        )

    @mcp.tool(
        title='Compare Wikonomi product value',
        meta=_oauth_meta(),
        description=(
            'Read-only. Compare compatible package sizes by unit price, separating the exact product, same-brand '
            'pack-size variants, and comparable alternatives. Lower unit price does not imply equal quality.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def compare_product_value(
        product_id: int = Field(ge=1),
        currency: str = Field(default='PGK', min_length=3, max_length=3),
    ) -> dict[str, Any]:
        arguments = {'product_id': product_id, 'currency': currency}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'compare_product_value',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: comparison_services.compare_product_value(product_id, currency),
        )

    @mcp.tool(
        title='Compare a Wikonomi shopping basket',
        meta=_oauth_meta(),
        description=(
            'Read-only and stateless. Compare exact product IDs across stores, show the cheapest complete one-store '
            'basket when available, and calculate a theoretical split-store minimum. Never substitutes products.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def compare_basket(
        items: list[BasketItemInput] = Field(min_length=1, max_length=100),
        currency: str = Field(default='PGK', min_length=3, max_length=3),
    ) -> dict[str, Any]:
        rows = [item.model_dump(mode='python') for item in items]
        arguments = {'items': rows, 'currency': currency}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'compare_basket',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: comparison_services.compare_basket(rows, currency),
        )
