from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from asgiref.sync import sync_to_async
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .models import MCPUserAccess
from .permissions import PUBLISH_SCOPE, READ_SCOPE, WRITE_SCOPE
from . import services


class AIMetadata(BaseModel):
    """Optional internal provenance; never guess an unknown provider or model."""

    provider: str = Field(default='', max_length=80, description='AI provider, for example OpenAI or Anthropic.')
    model: str = Field(default='', max_length=120, description='Model name when the client knows it.')
    confidence: float | None = Field(default=None, ge=0, le=1, description='Confidence in extracted or generated data.')
    source_note: str = Field(
        default='',
        max_length=5000,
        description='Short provenance note, such as “extracted from two user-provided shelf photos”.',
    )


class PriceObservation(BaseModel):
    model_config = ConfigDict(extra='forbid')

    product_id: int | None = Field(default=None, ge=1)
    product_name: str | None = Field(default=None, max_length=255)
    product_category_id: int | None = Field(default=None, ge=1)
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
    idempotency_key: str | None = Field(
        default=None,
        max_length=120,
        description='Stable caller-generated key. Reuse it when retrying the same observation.',
    )


class GuideStepInput(BaseModel):
    title: str = Field(default='', max_length=120)
    instruction: str = Field(min_length=1, max_length=30000)
    position: float | None = None
    source_step_id: int | None = Field(
        default=None,
        ge=1,
        description='On updates, the current step ID whose photos, tips, and questions should follow this step.',
    )


class GuideReferenceInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=8, max_length=2048)
    publisher: str = Field(default='', max_length=180)
    accessed_at: str | None = Field(default=None, description='ISO date, for example 2026-08-30.')


class GuideCreateInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default='', max_length=20000)
    organization_name: str = Field(default='', max_length=255)
    category_name: str = Field(default='', max_length=100)
    steps: list[GuideStepInput] = Field(min_length=1, max_length=100)
    references: list[GuideReferenceInput] = Field(default_factory=list, max_length=50)
    edit_summary: str = Field(default='Created through Wikonomi MCP', max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=120)


class GuideUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=20000)
    organization_name: str | None = Field(default=None, max_length=255)
    category_name: str | None = Field(default=None, max_length=100)
    steps: list[GuideStepInput] | None = Field(default=None, min_length=1, max_length=100)
    references: list[GuideReferenceInput] | None = Field(default=None, max_length=50)
    edit_summary: str = Field(default='Updated through Wikonomi MCP', max_length=255)


READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
PUBLIC_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)
PUBLIC_UPDATE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=True)


def _dump(model):
    return model.model_dump(mode='python', exclude_none=True) if model else None


def _oauth_meta(scope):
    scopes = [READ_SCOPE] if scope == READ_SCOPE else [READ_SCOPE, scope]
    return {'securitySchemes': [{'type': 'oauth2', 'scopes': scopes}]}


def register_tools(mcp):
    @mcp.tool(
        title='Get Wikonomi schema help',
        meta=_oauth_meta(READ_SCOPE),
        description='Use this before a Wikonomi workflow when you need entity rules, permissions, or the safe price/guide sequence.',
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_schema_help(
        topic: Literal['overview', 'prices', 'guides', 'permissions'] = 'overview',
    ) -> dict[str, Any]:
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'get_schema_help',
            {'topic': topic},
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: services.schema_help(topic),
        )

    @mcp.tool(
        title='Search Wikonomi',
        meta=_oauth_meta(READ_SCOPE),
        description='Use this to find products, businesses, branches, or guides before creating or updating records.',
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def search_wikonomi(
        query: str = Field(min_length=1, max_length=300),
        entity_types: list[Literal['product', 'business', 'guide']] | None = None,
        limit: int = Field(default=10, ge=1, le=50),
    ) -> dict[str, Any]:
        arguments = {'query': query, 'entity_types': entity_types, 'limit': limit}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'search_wikonomi',
            arguments,
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: services.search_wikonomi(query, entity_types, limit),
        )

    @mcp.tool(
        title='Get a Wikonomi product',
        meta=_oauth_meta(READ_SCOPE),
        description='Use this after search_wikonomi to retrieve a product, aliases, statistics, and recent price observations.',
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_product(product_id: int = Field(ge=1)) -> dict[str, Any]:
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'get_product',
            {'product_id': product_id},
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: services.get_product(product_id),
        )

    @mcp.tool(
        title='Find or create a product',
        meta=_oauth_meta(WRITE_SCOPE),
        description='Contributors only. Use after searching for an observed product. It fuzzy-matches before creating a public product record; confirm creation with the user.',
        annotations=PUBLIC_WRITE,
        structured_output=True,
    )
    async def find_or_create_product(
        name: str = Field(min_length=1, max_length=255),
        category_id: int | None = Field(default=None, ge=1),
        description: str = Field(default='', max_length=10000),
        tags: list[str] | None = Field(default=None, max_length=30),
        create_if_missing: bool = True,
        ai: AIMetadata | None = None,
    ) -> dict[str, Any]:
        arguments = {
            'name': name,
            'category_id': category_id,
            'description': description,
            'tags': tags,
            'create_if_missing': create_if_missing,
            'ai': _dump(ai),
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'find_or_create_product',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: services.find_or_create_product(
                actor=actor,
                name=name,
                category_id=category_id,
                description=description,
                tags=tags,
                create_if_missing=create_if_missing,
                ai=_dump(ai),
            ),
        )

    @mcp.tool(
        title='Submit a price observation',
        meta=_oauth_meta(WRITE_SCOPE),
        description='Contributors only. After user confirmation, publish one actual observed price publicly under their account. Retains internal provenance and returns a report ID for evidence upload.',
        annotations=PUBLIC_WRITE,
        structured_output=True,
    )
    async def submit_price(observation: PriceObservation, ai: AIMetadata | None = None) -> dict[str, Any]:
        arguments = {'observation': _dump(observation), 'ai': _dump(ai)}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'submit_price',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: services.submit_price(
                actor=actor,
                data=_dump(observation),
                ai=_dump(ai),
            ),
        )

    @mcp.tool(
        title='Bulk submit price observations',
        meta=_oauth_meta(WRITE_SCOPE),
        description='After user confirmation, publish observed prices publicly under their account. Maximum 25 rows for contributors and 100 for staff/owner. Never invent missing prices.',
        annotations=PUBLIC_WRITE,
        structured_output=True,
    )
    async def bulk_submit_prices(
        observations: list[PriceObservation] = Field(min_length=1, max_length=100),
        ai: AIMetadata | None = None,
        atomic: bool = Field(default=False, description='When true, roll back every row if any row fails.'),
    ) -> dict[str, Any]:
        rows = [_dump(item) for item in observations]
        arguments = {'observations': rows, 'ai': _dump(ai), 'atomic': atomic}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'bulk_submit_prices',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: services.bulk_submit_prices(
                actor=actor,
                observations=rows,
                ai=_dump(ai),
                atomic=atomic,
            ),
        )

    @mcp.tool(
        title='Upload price evidence',
        meta=_oauth_meta(WRITE_SCOPE),
        description='Contributors only. After price submission and user confirmation, publish one JPEG, PNG, or WebP as evidence for up to 20 report IDs. Remove personal details from receipts before upload.',
        annotations=PUBLIC_WRITE,
        structured_output=True,
    )
    async def upload_evidence(
        price_report_ids: list[int] = Field(min_length=1, max_length=20),
        image_base64: str = Field(min_length=16, description='Raw base64 or a data:image/...;base64 data URL.'),
        filename: str = Field(default='evidence.jpg', max_length=255),
        caption: str = Field(default='', max_length=240),
    ) -> dict[str, Any]:
        arguments = {
            'price_report_ids': price_report_ids,
            'image_base64': image_base64,
            'filename': filename,
            'caption': caption,
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'upload_evidence',
            arguments,
            scope=WRITE_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: services.upload_evidence(
                actor=actor,
                price_report_ids=price_report_ids,
                image_base64=image_base64,
                filename=filename,
                caption=caption,
            ),
        )

    @mcp.tool(
        title='Get a Wikonomi guide',
        meta=_oauth_meta(READ_SCOPE),
        description='Use this after search_wikonomi and before editing a guide. Returns the current published version, stable step IDs, and references. Drafts are not available.',
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_guide(guide_id: int = Field(ge=1)) -> dict[str, Any]:
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'get_guide',
            {'guide_id': guide_id},
            scope=READ_SCOPE,
            minimum_role=MCPUserAccess.Role.READER,
            operation=lambda _actor: services.get_guide(guide_id),
        )

    @mcp.tool(
        title='Create and publish a Wikonomi guide',
        meta=_oauth_meta(PUBLISH_SCOPE),
        description='Contributors only. After user confirmation, create a publicly visible practical guide under their account. Retains sources and internal AI provenance.',
        annotations=PUBLIC_WRITE,
        structured_output=True,
    )
    async def create_guide(guide: GuideCreateInput, ai: AIMetadata | None = None) -> dict[str, Any]:
        arguments = {'guide': _dump(guide), 'ai': _dump(ai)}
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'create_guide',
            arguments,
            scope=PUBLISH_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: services.create_guide(actor=actor, data=_dump(guide), ai=_dump(ai)),
        )

    @mcp.tool(
        title='Update and publish a Wikonomi guide',
        meta=_oauth_meta(PUBLISH_SCOPE),
        description='Contributors only. Use after get_guide and user confirmation. Replaces the publicly visible guide with a new version; previous versions remain in history. Editing another user’s guide requires explicit high-impact confirmation.',
        annotations=PUBLIC_UPDATE,
        structured_output=True,
    )
    async def update_guide(
        guide_id: int = Field(ge=1),
        changes: GuideUpdateInput = Field(description='Only provided fields are changed.'),
        confirm_high_impact: bool = Field(
            default=False,
            description='Set true only after reviewing the current guide when editing another user’s contribution.',
        ),
        ai: AIMetadata | None = None,
    ) -> dict[str, Any]:
        arguments = {
            'guide_id': guide_id,
            'changes': _dump(changes),
            'confirm_high_impact': confirm_high_impact,
            'ai': _dump(ai),
        }
        return await sync_to_async(services.audited_call, thread_sensitive=True)(
            'update_guide',
            arguments,
            scope=PUBLISH_SCOPE,
            minimum_role=MCPUserAccess.Role.CONTRIBUTOR,
            operation=lambda actor: services.update_guide(
                actor=actor,
                guide_id=guide_id,
                changes=_dump(changes),
                confirm_high_impact=confirm_high_impact,
                ai=_dump(ai),
            ),
        )
