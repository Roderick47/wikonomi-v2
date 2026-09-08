import re
from decimal import Decimal, InvalidOperation

from django.db import migrations


UNIT_ALIASES = {
    'g': 'g', 'gram': 'g', 'grams': 'g', 'gm': 'g', 'gms': 'g',
    'kg': 'kg', 'kgs': 'kg', 'kilogram': 'kg', 'kilograms': 'kg',
    'ml': 'ml', 'millilitre': 'ml', 'millilitres': 'ml', 'milliliter': 'ml', 'milliliters': 'ml',
    'l': 'l', 'lt': 'l', 'ltr': 'l', 'litre': 'l', 'litres': 'l', 'liter': 'l', 'liters': 'l',
    'pc': 'each', 'pcs': 'each', 'piece': 'each', 'pieces': 'each', 'each': 'each', 'ea': 'each',
    'm': 'm', 'metre': 'm', 'metres': 'm', 'meter': 'm', 'meters': 'm',
    'cm': 'cm', 'centimetre': 'cm', 'centimetres': 'cm', 'centimeter': 'cm', 'centimeters': 'cm',
}
UNIT_PATTERN = '|'.join(sorted((re.escape(key) for key in UNIT_ALIASES), key=len, reverse=True))
PACK_PATTERN = re.compile(rf'(?P<count>\d+)\s*[x×]\s*(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})\b', re.I)
QUANTITY_PATTERN = re.compile(rf'(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})\b', re.I)


def normalize_text(value):
    value = (value or '').casefold().strip()
    value = re.sub(r'[^\w\s]', ' ', value)
    return ' '.join(value.split())


def normalize_barcode(value):
    return re.sub(r'[\s\-]+', '', (value or '').strip().casefold())


def normalize_unit(value):
    return UNIT_ALIASES.get(normalize_text(value), '')


def base_measure(quantity, unit):
    if quantity is None or not unit:
        return quantity, unit
    if unit == 'kg':
        return quantity * Decimal('1000'), 'g'
    if unit == 'l':
        return quantity * Decimal('1000'), 'ml'
    if unit == 'm':
        return quantity * Decimal('100'), 'cm'
    return quantity, unit


def decimal_text(value):
    if value is None:
        return ''
    text = format(value.normalize(), 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def parse_name(name, brand='', fallback_unit=''):
    cleaned = ' '.join((name or '').split())
    quantity = None
    unit = ''
    pack_count = None

    match = PACK_PATTERN.search(cleaned)
    if match:
        try:
            quantity = Decimal(match.group('quantity'))
        except InvalidOperation:
            quantity = None
        unit = normalize_unit(match.group('unit'))
        pack_count = int(match.group('count'))
        cleaned = f'{cleaned[:match.start()]} {cleaned[match.end():]}'
    else:
        matches = list(QUANTITY_PATTERN.finditer(cleaned))
        if matches:
            match = matches[-1]
            try:
                quantity = Decimal(match.group('quantity'))
            except InvalidOperation:
                quantity = None
            unit = normalize_unit(match.group('unit'))
            pack_count = 1
            cleaned = f'{cleaned[:match.start()]} {cleaned[match.end():]}'

    if not unit:
        unit = normalize_unit(fallback_unit)

    brand_norm = normalize_text(brand)
    base_name = normalize_text(cleaned)
    if brand_norm and base_name.startswith(brand_norm + ' '):
        base_name = base_name[len(brand_norm):].strip()

    base_quantity, base_unit = base_measure(quantity, unit)
    parts = []
    if brand_norm:
        parts.append(f'brand:{brand_norm}')
    if base_name:
        parts.append(f'name:{base_name}')
    if base_quantity is not None and base_unit:
        parts.append(f'size:{decimal_text(base_quantity)}{base_unit}')
        parts.append(f'pack:{pack_count or 1}')
    return quantity, unit, pack_count, '|'.join(parts)


def backfill(apps, schema_editor):
    Product = apps.get_model('core', 'Product')
    BusinessInventoryItem = apps.get_model('core', 'BusinessInventoryItem')
    ProductIdentity = apps.get_model('catalog', 'ProductIdentity')

    inventory_by_product = {}
    for item in BusinessInventoryItem.objects.all().only('product_id', 'brand', 'barcode', 'unit'):
        inventory_by_product.setdefault(item.product_id, []).append(item)

    pending = []
    for product in Product.objects.all().only('id', 'name'):
        inventory = inventory_by_product.get(product.id, [])
        brands = {item.brand.strip() for item in inventory if item.brand and item.brand.strip()}
        barcode_values = {
            normalize_barcode(item.barcode): item.barcode.strip()
            for item in inventory
            if item.barcode and normalize_barcode(item.barcode)
        }
        units = {item.unit.strip() for item in inventory if item.unit and item.unit.strip()}

        brand = next(iter(brands)) if len(brands) == 1 else ''
        barcode = next(iter(barcode_values.values())) if len(barcode_values) == 1 else ''
        fallback_unit = next(iter(units)) if len(units) == 1 else ''
        quantity, package_unit, pack_count, signature = parse_name(
            product.name,
            brand=brand,
            fallback_unit=fallback_unit,
        )
        pending.append(ProductIdentity(
            product_id=product.id,
            brand=brand,
            package_quantity=quantity,
            package_unit=package_unit,
            pack_count=pack_count,
            barcode=barcode,
            normalized_barcode=normalize_barcode(barcode),
            identity_signature=signature,
            source='bulk_import' if brand or barcode or fallback_unit else 'inferred',
            confidence=Decimal('0.800'),
        ))

    ProductIdentity.objects.bulk_create(pending, ignore_conflicts=True, batch_size=500)


def reverse_backfill(apps, schema_editor):
    ProductIdentity = apps.get_model('catalog', 'ProductIdentity')
    ProductIdentity.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_backfill),
    ]
