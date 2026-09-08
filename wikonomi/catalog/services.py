import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from django.db import transaction
from django.utils.text import slugify

from .models import ProductDuplicateCandidate, ProductIdentity


AUTO_FUZZY_MATCH_THRESHOLD = 0.92
DUPLICATE_REVIEW_THRESHOLD = 0.72

UNIT_ALIASES = {
    'g': 'g',
    'gram': 'g',
    'grams': 'g',
    'gm': 'g',
    'gms': 'g',
    'kg': 'kg',
    'kgs': 'kg',
    'kilogram': 'kg',
    'kilograms': 'kg',
    'ml': 'ml',
    'millilitre': 'ml',
    'millilitres': 'ml',
    'milliliter': 'ml',
    'milliliters': 'ml',
    'l': 'l',
    'lt': 'l',
    'ltr': 'l',
    'litre': 'l',
    'litres': 'l',
    'liter': 'l',
    'liters': 'l',
    'pc': 'each',
    'pcs': 'each',
    'piece': 'each',
    'pieces': 'each',
    'each': 'each',
    'ea': 'each',
    'm': 'm',
    'metre': 'm',
    'metres': 'm',
    'meter': 'm',
    'meters': 'm',
    'cm': 'cm',
    'centimetre': 'cm',
    'centimetres': 'cm',
    'centimeter': 'cm',
    'centimeters': 'cm',
}

UNIT_PATTERN = '|'.join(sorted((re.escape(key) for key in UNIT_ALIASES), key=len, reverse=True))
PACK_PATTERN = re.compile(
    rf'(?P<count>\d+)\s*[x×]\s*(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})\b',
    flags=re.IGNORECASE,
)
QUANTITY_PATTERN = re.compile(
    rf'(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})\b',
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedIdentity:
    base_name: str
    brand: str
    variant: str
    package_quantity: Decimal | None
    package_unit: str
    pack_count: int | None
    barcode: str
    normalized_barcode: str
    identity_signature: str


@dataclass(frozen=True)
class ProductMatch:
    product: object | None
    score: float
    basis: str
    exact: bool = False


def normalize_text(value):
    value = (value or '').casefold().strip()
    value = re.sub(r'[^\w\s]', ' ', value)
    return ' '.join(value.split())


def normalize_barcode(value):
    """Normalize GTIN/EAN/UPC-style identifiers without assuming they are all numeric."""
    value = (value or '').strip().casefold()
    return re.sub(r'[\s\-]+', '', value)


def normalize_unit(value):
    return UNIT_ALIASES.get(normalize_text(value), '')


def _decimal_text(value):
    if value is None:
        return ''
    normalized = value.normalize()
    return format(normalized, 'f').rstrip('0').rstrip('.') if '.' in format(normalized, 'f') else format(normalized, 'f')


def _base_measure(quantity, unit):
    if quantity is None or not unit:
        return quantity, unit
    if unit == 'kg':
        return quantity * Decimal('1000'), 'g'
    if unit == 'l':
        return quantity * Decimal('1000'), 'ml'
    if unit == 'm':
        return quantity * Decimal('100'), 'cm'
    return quantity, unit


def parse_product_identity(name, *, brand='', variant='', barcode='', unit=''):
    raw_name = ' '.join((name or '').split())
    cleaned_name = raw_name
    quantity = None
    package_unit = ''
    pack_count = None

    pack_match = PACK_PATTERN.search(cleaned_name)
    if pack_match:
        try:
            quantity = Decimal(pack_match.group('quantity'))
        except InvalidOperation:
            quantity = None
        package_unit = normalize_unit(pack_match.group('unit'))
        pack_count = int(pack_match.group('count'))
        cleaned_name = f'{cleaned_name[:pack_match.start()]} {cleaned_name[pack_match.end():]}'
    else:
        quantity_matches = list(QUANTITY_PATTERN.finditer(cleaned_name))
        if quantity_matches:
            quantity_match = quantity_matches[-1]
            try:
                quantity = Decimal(quantity_match.group('quantity'))
            except InvalidOperation:
                quantity = None
            package_unit = normalize_unit(quantity_match.group('unit'))
            pack_count = 1
            cleaned_name = f'{cleaned_name[:quantity_match.start()]} {cleaned_name[quantity_match.end():]}'

    if not package_unit:
        package_unit = normalize_unit(unit)

    normalized_brand = normalize_text(brand)
    normalized_variant = normalize_text(variant)
    base_name = normalize_text(cleaned_name)
    if normalized_brand and base_name.startswith(normalized_brand + ' '):
        base_name = base_name[len(normalized_brand):].strip()

    base_quantity, base_unit = _base_measure(quantity, package_unit)
    signature_parts = []
    if normalized_brand:
        signature_parts.append(f'brand:{normalized_brand}')
    if base_name:
        signature_parts.append(f'name:{base_name}')
    if normalized_variant:
        signature_parts.append(f'variant:{normalized_variant}')
    if base_quantity is not None and base_unit:
        signature_parts.append(f'size:{_decimal_text(base_quantity)}{base_unit}')
        signature_parts.append(f'pack:{pack_count or 1}')

    normalized_code = normalize_barcode(barcode)
    return ParsedIdentity(
        base_name=base_name,
        brand=' '.join((brand or '').split()),
        variant=' '.join((variant or '').split()),
        package_quantity=quantity,
        package_unit=package_unit,
        pack_count=pack_count,
        barcode=' '.join((barcode or '').split()),
        normalized_barcode=normalized_code,
        identity_signature='|'.join(signature_parts),
    )


def _identity_for_product(product):
    try:
        identity = product.identity
    except ProductIdentity.DoesNotExist:
        return parse_product_identity(product.name)

    inferred = parse_product_identity(
        product.name,
        brand=identity.brand,
        variant=identity.variant,
        barcode=identity.barcode,
        unit=identity.package_unit,
    )
    quantity = identity.package_quantity if identity.package_quantity is not None else inferred.package_quantity
    package_unit = identity.package_unit or inferred.package_unit
    pack_count = identity.pack_count if identity.pack_count is not None else inferred.pack_count
    base_quantity, base_unit = _base_measure(quantity, package_unit)
    signature_parts = []
    if normalize_text(identity.brand):
        signature_parts.append(f'brand:{normalize_text(identity.brand)}')
    if inferred.base_name:
        signature_parts.append(f'name:{inferred.base_name}')
    if normalize_text(identity.variant):
        signature_parts.append(f'variant:{normalize_text(identity.variant)}')
    if base_quantity is not None and base_unit:
        signature_parts.append(f'size:{_decimal_text(base_quantity)}{base_unit}')
        signature_parts.append(f'pack:{pack_count or 1}')

    return ParsedIdentity(
        base_name=inferred.base_name,
        brand=identity.brand,
        variant=identity.variant,
        package_quantity=quantity,
        package_unit=package_unit,
        pack_count=pack_count,
        barcode=identity.barcode,
        normalized_barcode=identity.normalized_barcode or normalize_barcode(identity.barcode),
        identity_signature=identity.identity_signature or '|'.join(signature_parts),
    )


def _package_compatible(left, right):
    left_q, left_u = _base_measure(left.package_quantity, left.package_unit)
    right_q, right_u = _base_measure(right.package_quantity, right.package_unit)
    if left_q is None or right_q is None or not left_u or not right_u:
        return True
    return (
        left_u == right_u
        and left_q == right_q
        and (left.pack_count or 1) == (right.pack_count or 1)
    )


def _brand_compatible(left, right):
    left_brand = normalize_text(left.brand)
    right_brand = normalize_text(right.brand)
    return not left_brand or not right_brand or left_brand == right_brand


def ensure_product_identity(
    product,
    *,
    brand='',
    variant='',
    barcode='',
    unit='',
    source=ProductIdentity.Source.INFERRED,
    confidence=None,
):
    parsed = parse_product_identity(
        product.name,
        brand=brand,
        variant=variant,
        barcode=barcode,
        unit=unit,
    )
    identity, created = ProductIdentity.objects.get_or_create(product=product)

    explicit_source = source != ProductIdentity.Source.INFERRED
    changed = []
    updates = {
        'brand': parsed.brand if parsed.brand else identity.brand,
        'variant': parsed.variant if parsed.variant else identity.variant,
        'package_quantity': parsed.package_quantity if parsed.package_quantity is not None else identity.package_quantity,
        'package_unit': parsed.package_unit if parsed.package_unit else identity.package_unit,
        'pack_count': parsed.pack_count if parsed.pack_count is not None else identity.pack_count,
        'barcode': parsed.barcode if parsed.barcode else identity.barcode,
        'normalized_barcode': parsed.normalized_barcode if parsed.normalized_barcode else identity.normalized_barcode,
        'source': source if explicit_source or created else identity.source,
        'confidence': confidence if confidence is not None else identity.confidence,
    }

    for field, value in updates.items():
        if getattr(identity, field) != value:
            setattr(identity, field, value)
            changed.append(field)

    refreshed = parse_product_identity(
        product.name,
        brand=identity.brand,
        variant=identity.variant,
        barcode=identity.barcode,
        unit=identity.package_unit,
    )
    quantity = identity.package_quantity if identity.package_quantity is not None else refreshed.package_quantity
    package_unit = identity.package_unit or refreshed.package_unit
    pack_count = identity.pack_count if identity.pack_count is not None else refreshed.pack_count
    base_quantity, base_unit = _base_measure(quantity, package_unit)
    signature_parts = []
    if normalize_text(identity.brand):
        signature_parts.append(f'brand:{normalize_text(identity.brand)}')
    if refreshed.base_name:
        signature_parts.append(f'name:{refreshed.base_name}')
    if normalize_text(identity.variant):
        signature_parts.append(f'variant:{normalize_text(identity.variant)}')
    if base_quantity is not None and base_unit:
        signature_parts.append(f'size:{_decimal_text(base_quantity)}{base_unit}')
        signature_parts.append(f'pack:{pack_count or 1}')
    signature = '|'.join(signature_parts)
    if identity.identity_signature != signature:
        identity.identity_signature = signature
        changed.append('identity_signature')

    if changed or created:
        identity.save(update_fields=list(dict.fromkeys(changed)) + ['updated_at'] if changed else None)
    return identity


def find_best_product(name, *, barcode='', brand='', variant='', unit='', min_similarity=DUPLICATE_REVIEW_THRESHOLD):
    from core.models import Product, ProductAlias

    incoming = parse_product_identity(
        name,
        brand=brand,
        variant=variant,
        barcode=barcode,
        unit=unit,
    )

    if incoming.normalized_barcode:
        barcode_matches = list(
            ProductIdentity.objects.filter(normalized_barcode=incoming.normalized_barcode)
            .select_related('product')
            .order_by('product_id')[:2]
        )
        if barcode_matches:
            return ProductMatch(barcode_matches[0].product, 1.0, 'barcode', exact=True)

    if incoming.identity_signature and incoming.package_quantity is not None:
        structured = (
            ProductIdentity.objects.filter(identity_signature=incoming.identity_signature)
            .select_related('product')
            .order_by('product_id')
            .first()
        )
        if structured:
            return ProductMatch(structured.product, 1.0, 'structured_identity', exact=True)

    normalized_name = normalize_text(name)
    direct = Product.objects.filter(name__iexact=(name or '').strip()).first()
    if direct:
        return ProductMatch(direct, 1.0, 'exact_name', exact=True)

    alias = ProductAlias.objects.filter(
        normalized_name=normalized_name,
        is_active=True,
    ).select_related('canonical_product').first()
    if alias:
        return ProductMatch(alias.canonical_product, 1.0, 'alias', exact=True)

    best = ProductMatch(None, 0.0, 'none', exact=False)
    products = Product.objects.select_related('identity').all()
    for candidate in products:
        candidate_identity = _identity_for_product(candidate)
        if incoming.normalized_barcode and candidate_identity.normalized_barcode:
            if incoming.normalized_barcode != candidate_identity.normalized_barcode:
                continue
        if not _brand_compatible(incoming, candidate_identity):
            continue
        if not _package_compatible(incoming, candidate_identity):
            continue

        candidate_name = candidate_identity.base_name or normalize_text(candidate.name)
        score = SequenceMatcher(None, incoming.base_name or normalized_name, candidate_name).ratio()
        if incoming.brand and candidate_identity.brand and normalize_text(incoming.brand) == normalize_text(candidate_identity.brand):
            score = min(1.0, score + 0.04)
        if score >= min_similarity and score > best.score:
            best = ProductMatch(candidate, score, 'fuzzy_compatible_name', exact=False)
    return best


def record_duplicate_candidate(source_product, candidate_product, score, basis, details=None):
    if not source_product or not candidate_product or source_product.pk == candidate_product.pk:
        return None
    first, second = sorted((source_product, candidate_product), key=lambda product: product.pk)
    candidate, created = ProductDuplicateCandidate.objects.get_or_create(
        source_product=first,
        candidate_product=second,
        defaults={
            'similarity_score': Decimal(str(round(float(score), 4))),
            'match_basis': basis,
            'details': details or {},
        },
    )
    if not created and candidate.status == ProductDuplicateCandidate.Status.PENDING:
        new_score = Decimal(str(round(float(score), 4)))
        changed = []
        if new_score > candidate.similarity_score:
            candidate.similarity_score = new_score
            changed.append('similarity_score')
        if basis and candidate.match_basis != basis:
            candidate.match_basis = basis
            changed.append('match_basis')
        if details and candidate.details != details:
            candidate.details = details
            changed.append('details')
        if changed:
            candidate.save(update_fields=changed + ['updated_at'])
    return candidate


def _unique_product_slug(name):
    from core.models import Product

    base = (slugify(name) or 'product')[:220]
    slug = base
    suffix = 2
    while Product.objects.filter(slug=slug).exists():
        slug = f'{base[:210]}-{suffix}'
        suffix += 1
    return slug


def create_or_match_product(
    name,
    *,
    category=None,
    created_by=None,
    description='',
    brand='',
    variant='',
    barcode='',
    unit='',
    source=ProductIdentity.Source.WEB,
    created_via=None,
    create_if_missing=True,
):
    from core.models import Product

    name = ' '.join((name or '').split())
    if not name:
        raise ValueError('Product name is required.')

    match = find_best_product(
        name,
        barcode=barcode,
        brand=brand,
        variant=variant,
        unit=unit,
    )
    if match.product and (match.exact or match.score >= AUTO_FUZZY_MATCH_THRESHOLD):
        ensure_product_identity(
            match.product,
            brand=brand,
            variant=variant,
            barcode=barcode,
            unit=unit,
            source=source,
            confidence=Decimal(str(round(float(match.score), 3))),
        )
        return match.product, False, match

    if not create_if_missing:
        return None, False, match

    with transaction.atomic():
        product = Product.objects.create(
            name=name[:255],
            slug=_unique_product_slug(name),
            description=(description or '')[:10000],
            category=category,
            created_by=created_by,
            **({'created_via': created_via} if created_via else {}),
        )
        ensure_product_identity(
            product,
            brand=brand,
            variant=variant,
            barcode=barcode,
            unit=unit,
            source=source,
            confidence=Decimal('1.000') if barcode else Decimal('0.800'),
        )
        if match.product and match.score >= DUPLICATE_REVIEW_THRESHOLD:
            record_duplicate_candidate(
                product,
                match.product,
                match.score,
                match.basis,
                details={
                    'incoming_name': name,
                    'incoming_barcode': normalize_barcode(barcode),
                    'reason': 'Close compatible match was below automatic merge threshold.',
                },
            )
    return product, True, match


def backfill_identity_for_product(product):
    return ensure_product_identity(product, source=ProductIdentity.Source.INFERRED)
