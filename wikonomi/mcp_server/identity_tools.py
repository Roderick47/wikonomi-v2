from datetime import datetime
from decimal import Decimal
from typing import Any

from asgiref.sync import sync_to_async
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from . import identity_services, services
from .models import MCPUserAccess
from .permissions import WRITE_SCOPE
from .tools import AIMetadata


PUBLIC_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)


def _dump(model):
    return model.model_dump(mode='python', exclude_none=True) if model else None


def _oauth_meta(scope):
    return {'securitySchemes': [{'type': 'oauth2', 'scopes': ['wikonomi:read', scope]}]}


class StructuredProductInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=255)
    category_id: int | None = Field(default=None, ge=1)
    description: str = Field(default='', max_length=10000)
    tags: list[str] | None = Field(default=None, max_length=30)
    brand: str = Field(default='', max_length=120)
    variant: str = Field(default='', max_length=160)
    barcode: str = Field(default='', max_length=64)
    package_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    package_unit: str = Field(default='', max_length=16, description='Examples: g, kg, ml, l, each, m, cm.')
    pack_count: int | None = Field(default=None, ge=1, le=10000)
    create_if_missing: bool = True


class StructuredPriceObservation(BaseModel):
    model_config = ConfigDict(extra='forbid')

    product_name: str = Field(min_length=1, max_length=255)
    product_category_id: int | None = Field(default=None, ge=1)
    product_description: str = Field(default='', max_length=10000)
    product_tags: list[str] | None = Field(default=None, max_length=30)
    brand: str = Field(default='', max_length=120)
    variant: str = Field(default='', max_length=160)
    barcode: str = Field(default='', max_length=64)
    package_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    package_unit: str = Field(default='', max_length=16)
    pack_count: int | None = Field(default=None, ge=1, le=10000)
    create_product_if_missing: bool = True

    business_id: int | None = Field(default=None, ge=1)
    business_branch_id: int | None = Field(default=None, ge=1)
    business_name: str | None = Field(default=None, max_length=255)
    branch_name: str | None = Field(default=None, max_length=255)
    subcategory_id: int | None = Field(default=None, ge=1)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default='PGK', min_length=3, max_length=3)
    observed_at: datetime | None = None
    notes: str = Field(default='', max_length=10000)
    idempotency_key: str | None = Field(default=None, max_length=120)


def register_identity_tools(mcp):
    @mcp.tool(
        title='Resolve a structured Wikonomi product',
        meta=_oauth_meta(WRITE_SCOPE),
        description=(
            'Contributors only. Resolve or create a product using structured identity such as brand, barcode, '
            'variant, package quantity/unit, and pack count. Prefer this over name-only creation when those fields '
            'are visible in a receipt, shelf label, spreadsheet, or barcode scan.'
        ),
        annotations=PUBLIC_WRITE,
        structured_output=True,
    )
    async def resolve_structured_product(
        product: StructuredProductInput,
        ai: AIMetadata | None = None,
    ) -> dict[str, Any]:
        data = _dump(product)
        arguments = {'product': data, 'ai': _dump(ai)}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'resolve_structured_product',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: identity_services.find_or_create_product(
                actor=actor,
                name=data['name'],
                category_id=data.get('category_id'),
                description=data.get('description', ''),
                tags=data.get('tags'),
                create_if_missing=data.get('create_if_missing', True),
                ai=_dump(ai),
                brand=data.get('brand', ''),
                variant=data.get('variant', ''),
                barcode=data.get('barcode', ''),
                package_quantity=data.get('package_quantity'),
                package_unit=data.get('package_unit', ''),
                pack_count=data.get('pack_count'),
            ),
        )

    @mcp.tool(
        title='Submit a structured price observation',
        meta=_oauth_meta(WRITE_SCOPE),
        description=(
            'Contributors only. After user confirmation, publish one observed price while resolving the product '
            'with barcode/brand/package identity first. Use this when structured product fields are available.'
        ),
        annotations=PUBLIC_WRITE,
        structured_output=True,
    )
    async def submit_structured_price(
        observation: StructuredPriceObservation,
        ai: AIMetadata | None = None,
    ) -> dict[str, Any]:
        data = _dump(observation)
        arguments = {'observation': data, 'ai': _dump(ai)}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'submit_structured_price',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: identity_services.submit_structured_price(
                actor=actor,
                data=data,
                ai=_dump(ai),
            ),
        )

    @mcp.tool(
        title='Bulk submit structured price observations',
        meta=_oauth_meta(WRITE_SCOPE),
        description=(
            'After user confirmation, publish structured observed prices. Maximum 25 rows for contributors and '
            '100 for staff/owner. Barcode and package identity are resolved before each price is created.'
        ),
        annotations=PUBLIC_WRITE,
        structured_output=True,
    )
    async def bulk_submit_structured_prices(
        observations: list[StructuredPriceObservation] = Field(min_length=1, max_length=100),
        ai: AIMetadata | None = None,
        atomic: bool = Field(default=False, description='When true, roll back every row if any row fails.'),
    ) -> dict[str, Any]:
        rows = [_dump(item) for item in observations]
        arguments = {'observations': rows, 'ai': _dump(ai), 'atomic': atomic}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'bulk_submit_structured_prices',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: identity_services.bulk_submit_structured_prices(
                actor=actor,
                observations=rows,
                ai=_dump(ai),
                atomic=atomic,
            ),
        )
