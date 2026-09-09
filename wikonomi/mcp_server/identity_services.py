from decimal import Decimal, InvalidOperation

from django.db import transaction

from catalog.models import ProductIdentity
from catalog.services import (
    create_or_match_product as catalog_create_or_match_product,
    ensure_product_identity,
    normalize_unit,
    parse_product_identity,
)
from core.models import Category, Product

from .current_price_services import get_product as get_current_product


def _decimal_or_none(value, field_name):
    if value in (None, ''):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{field_name} must be a valid number.') from exc
    if result <= 0:
        raise ValueError(f'{field_name} must be greater than zero.')
    return result


def _normalized_product_name(name, package_quantity=None, package_unit='', pack_count=None):
    name = ' '.join((name or '').split())
    if not name:
        raise ValueError('Product name is required.')

    parsed = parse_product_identity(name)
    if parsed.package_quantity is not None:
        return name

    quantity = _decimal_or_none(package_quantity, 'package_quantity')
    unit = normalize_unit(package_unit)
    if package_unit and not unit:
        raise ValueError(f'Unsupported package unit: {package_unit}.')
    if quantity is None or not unit:
        return name

    quantity_text = format(quantity.normalize(), 'f')
    if '.' in quantity_text:
        quantity_text = quantity_text.rstrip('0').rstrip('.')
    count = int(pack_count or 1)
    if count <= 0:
        raise ValueError('pack_count must be greater than zero.')
    if count > 1:
        return f'{name} {count} x {quantity_text}{unit}'
    return f'{name} {quantity_text}{unit}'


def _apply_explicit_package(identity, *, package_quantity=None, package_unit='', pack_count=None):
    quantity = _decimal_or_none(package_quantity, 'package_quantity')
    unit = normalize_unit(package_unit) if package_unit else ''
    if package_unit and not unit:
        raise ValueError(f'Unsupported package unit: {package_unit}.')

    changed = []
    if quantity is not None and identity.package_quantity != quantity:
        identity.package_quantity = quantity
        changed.append('package_quantity')
    if unit and identity.package_unit != unit:
        identity.package_unit = unit
        changed.append('package_unit')
    if pack_count is not None:
        count = int(pack_count)
        if count <= 0:
            raise ValueError('pack_count must be greater than zero.')
        if identity.pack_count != count:
            identity.pack_count = count
            changed.append('pack_count')
    if changed:
        identity.save(update_fields=changed + ['updated_at'])
    return identity


def _serialize_identity(product):
    try:
        identity = product.identity
    except ProductIdentity.DoesNotExist:
        identity = ensure_product_identity(product, source=ProductIdentity.Source.INFERRED)
    return {
        'brand': identity.brand or None,
        'variant': identity.variant or None,
        'package_quantity': str(identity.package_quantity) if identity.package_quantity is not None else None,
        'package_unit': identity.package_unit or None,
        'pack_count': identity.pack_count,
        'barcode': identity.barcode or None,
        'normalized_barcode': identity.normalized_barcode or None,
        'identity_signature': identity.identity_signature or None,
        'source': identity.source,
        'confidence': str(identity.confidence) if identity.confidence is not None else None,
    }


def get_product(product_id):
    payload = get_current_product(product_id)
    product = Product.objects.select_related('identity').filter(pk=product_id).first()
    if not product:
        raise ValueError(f'Product {product_id} was not found.')
    payload['structured_identity'] = _serialize_identity(product)
    return payload


def find_or_create_product(
    *,
    actor,
    name,
    category_id=None,
    description='',
    tags=None,
    create_if_missing=True,
    ai=None,
    brand='',
    variant='',
    barcode='',
    package_quantity=None,
    package_unit='',
    pack_count=None,
):
    from . import services

    category = None
    if category_id is not None:
        category = Category.objects.filter(pk=category_id).first()
        if not category:
            raise ValueError(f'Product category {category_id} was not found.')

    canonical_name = _normalized_product_name(
        name,
        package_quantity=package_quantity,
        package_unit=package_unit,
        pack_count=pack_count,
    )

    product, created, match = catalog_create_or_match_product(
        canonical_name,
        category=category,
        created_by=actor.user,
        description=description,
        brand=brand,
        variant=variant,
        barcode=barcode,
        unit=package_unit,
        source=ProductIdentity.Source.MCP,
        created_via='mcp',
        create_if_missing=create_if_missing,
    )

    if product is None:
        best = match.product if match else None
        return {
            'status': 'not_created',
            'created': False,
            'best_candidate': ({
                'id': best.pk,
                'name': best.name,
                'similarity': round(float(match.score), 4),
                'match_basis': match.basis,
            } if best else None),
        }

    identity = ensure_product_identity(
        product,
        brand=brand,
        variant=variant,
        barcode=barcode,
        unit=package_unit,
        source=ProductIdentity.Source.MCP,
        confidence=Decimal(str(round(float(match.score), 3))) if match and match.product else None,
    )
    _apply_explicit_package(
        identity,
        package_quantity=package_quantity,
        package_unit=package_unit,
        pack_count=pack_count,
    )
    # Re-run identity maintenance so any explicit package fields participate in
    # the stored identity signature.
    ensure_product_identity(
        product,
        brand=brand,
        variant=variant,
        barcode=barcode,
        unit=identity.package_unit,
        source=ProductIdentity.Source.MCP,
        confidence=identity.confidence,
    )

    if created:
        provenance = services._ai_fields(ai)
        for field, value in provenance.items():
            setattr(product, field, value)
        product.save(update_fields=list(provenance))
        if tags:
            product.tags.add(*[str(tag).strip()[:100] for tag in tags if str(tag).strip()])

    return {
        'status': 'created' if created else 'matched',
        'created': created,
        'similarity': round(float(match.score), 4) if match else 0,
        'match_basis': match.basis if match else 'created',
        'exact_match': bool(match.exact) if match else False,
        'product': get_product(product.pk),
    }


def submit_structured_price(*, actor, data, ai=None):
    from . import services

    resolved = find_or_create_product(
        actor=actor,
        name=data.get('product_name') or '',
        category_id=data.get('product_category_id'),
        description=data.get('product_description', ''),
        tags=data.get('product_tags'),
        create_if_missing=data.get('create_product_if_missing', True),
        ai=ai,
        brand=data.get('brand', ''),
        variant=data.get('variant', ''),
        barcode=data.get('barcode', ''),
        package_quantity=data.get('package_quantity'),
        package_unit=data.get('package_unit', ''),
        pack_count=data.get('pack_count'),
    )
    product_payload = resolved.get('product')
    if not product_payload:
        raise ValueError('No product matched the supplied structured identity and creation was disabled.')

    price_data = dict(data)
    price_data['product_id'] = product_payload['id']
    for key in (
        'product_name', 'product_category_id', 'product_description', 'product_tags',
        'brand', 'variant', 'barcode', 'package_quantity', 'package_unit', 'pack_count',
        'create_product_if_missing',
    ):
        price_data.pop(key, None)
    result = services.submit_price(actor=actor, data=price_data, ai=ai)
    result['product_resolution'] = {
        'status': resolved['status'],
        'match_basis': resolved.get('match_basis'),
        'similarity': resolved.get('similarity'),
        'structured_identity': product_payload.get('structured_identity'),
    }
    return result


def bulk_submit_structured_prices(*, actor, observations, ai=None, atomic=False):
    from .models import MCPUserAccess

    limit = 100 if actor.at_least(MCPUserAccess.Role.STAFF) else 25
    if not observations:
        raise ValueError('At least one price observation is required.')
    if len(observations) > limit:
        raise ValueError(f'The {actor.role} role can submit at most {limit} prices per call.')

    results = []

    def process():
        for index, observation in enumerate(observations):
            try:
                result = submit_structured_price(actor=actor, data=observation, ai=ai)
                results.append({'index': index, 'ok': True, **result})
            except Exception as exc:
                if atomic:
                    raise ValueError(f'Price row {index} failed: {exc}') from exc
                results.append({'index': index, 'ok': False, 'error': str(exc)})

    if atomic:
        with transaction.atomic():
            process()
    else:
        process()
    return {
        'submitted': len(observations),
        'succeeded': sum(1 for item in results if item['ok']),
        'failed': sum(1 for item in results if not item['ok']),
        'results': results,
    }


def install_identity_service_upgrades():
    from . import services

    # Existing MCP tools keep their names but now use the catalog identity
    # resolver even when older clients only provide a product name.
    services.find_or_create_product = find_or_create_product
    services.get_product = get_product
