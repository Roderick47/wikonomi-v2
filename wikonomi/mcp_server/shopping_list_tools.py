from typing import Any

from asgiref.sync import sync_to_async
from mcp.types import ToolAnnotations
from pydantic import Field

from . import services
from .models import MCPUserAccess
from .permissions import READ_SCOPE, WRITE_SCOPE
from .shopping_list_services import (
    add_shopping_list_item as add_item_service,
    compare_shopping_list as compare_list_service,
    get_shopping_list as get_list_service,
    list_shopping_lists as list_lists_service,
    remove_shopping_list_item as remove_item_service,
    update_shopping_list_item as update_item_service,
)


READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
PRIVATE_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
PRIVATE_DELETE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)


def _oauth_meta(scope):
    scopes = [READ_SCOPE] if scope == READ_SCOPE else [READ_SCOPE, scope]
    return {'securitySchemes': [{'type': 'oauth2', 'scopes': scopes}]}


def register_shopping_list_tools(mcp):
    @mcp.tool(
        title='List my Wikonomi shopping lists',
        meta=_oauth_meta(READ_SCOPE),
        description=(
            'Read-only. List shopping lists owned by the authenticated user with checked, unresolved, and product-item counts. '
            'If more than one list exists, use the returned list ID explicitly in later calls.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def list_shopping_lists() -> dict[str, Any]:
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'list_shopping_lists',
            {},
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda actor: list_lists_service(actor),
        )

    @mcp.tool(
        title='Get my Wikonomi shopping list',
        meta=_oauth_meta(READ_SCOPE),
        description=(
            'Read-only. Return one shopping list owned by the authenticated user. Unresolved free-text items are preserved '
            'but never silently matched to products. Provide shopping_list_id when the account has multiple lists.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_shopping_list(
        shopping_list_id: int | None = Field(default=None, ge=1),
        include_checked: bool = True,
        limit: int = Field(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        arguments = {
            'shopping_list_id': shopping_list_id,
            'include_checked': include_checked,
            'limit': limit,
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'get_shopping_list',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda actor: get_list_service(actor, **arguments),
        )

    @mcp.tool(
        title='Add an exact product to my Wikonomi shopping list',
        meta=_oauth_meta(WRITE_SCOPE),
        description=(
            'Private account write. After the user confirms the exact product and target list, ensure that product exists '
            'as an unchecked shopping-list item. If it is already present, no duplicate is created; use update_shopping_list_item '
            'to set quantity. If the user has no list, this write creates My Shopping List.'
        ),
        annotations=PRIVATE_WRITE,
        structured_output=True,
    )
    async def add_shopping_list_item(
        product_id: int = Field(ge=1),
        shopping_list_id: int | None = Field(default=None, ge=1),
        quantity: int = Field(default=1, ge=1, le=10000),
    ) -> dict[str, Any]:
        arguments = {
            'product_id': product_id,
            'shopping_list_id': shopping_list_id,
            'quantity': quantity,
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'add_shopping_list_item',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: add_item_service(actor, **arguments),
        )

    @mcp.tool(
        title='Update my Wikonomi shopping-list item',
        meta=_oauth_meta(WRITE_SCOPE),
        description=(
            'Private account write. After user confirmation, set the absolute quantity and/or checked state of an item '
            'owned by the authenticated user. This does not change the product identity.'
        ),
        annotations=PRIVATE_WRITE,
        structured_output=True,
    )
    async def update_shopping_list_item(
        item_id: int = Field(ge=1),
        quantity: int | None = Field(default=None, ge=1, le=10000),
        is_checked: bool | None = None,
    ) -> dict[str, Any]:
        arguments = {
            'item_id': item_id,
            'quantity': quantity,
            'is_checked': is_checked,
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'update_shopping_list_item',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: update_item_service(actor, **arguments),
        )

    @mcp.tool(
        title='Remove my Wikonomi shopping-list item',
        meta=_oauth_meta(WRITE_SCOPE),
        description=(
            'Private destructive account write. After user confirmation, remove an item only from a shopping list owned '
            'by the authenticated user. Repeating a remove for an already-absent item is a safe no-op.'
        ),
        annotations=PRIVATE_DELETE,
        structured_output=True,
    )
    async def remove_shopping_list_item(
        item_id: int = Field(ge=1),
    ) -> dict[str, Any]:
        arguments = {'item_id': item_id}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'remove_shopping_list_item',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: remove_item_service(actor, **arguments),
        )

    @mcp.tool(
        title='Compare my saved Wikonomi shopping list',
        meta=_oauth_meta(READ_SCOPE),
        description=(
            'Read-only. Run Wikonomi current basket comparison against one saved list owned by the authenticated user. '
            'Only unchecked exact product IDs participate; checked and unresolved free-text items are surfaced separately. '
            'No substitute products are inserted and the saved list is not modified.'
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def compare_shopping_list(
        shopping_list_id: int | None = Field(default=None, ge=1),
        currency: str = Field(default='PGK', min_length=3, max_length=3),
    ) -> dict[str, Any]:
        arguments = {
            'shopping_list_id': shopping_list_id,
            'currency': currency,
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'compare_shopping_list',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda actor: compare_list_service(actor, **arguments),
        )
