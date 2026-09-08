from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q

from comments.models import Comment
from core.models import (
    BulkImportRow,
    BusinessInventoryItem,
    Notification,
    PriceReport,
    Product,
    ProductAlias,
    ProductImage,
    ProductWatchlist,
    ShoppingListItem,
)

from .models import ProductDuplicateCandidate, ProductIdentity
from .services import (
    _identity_for_product,
    _package_compatible,
    ensure_product_identity,
    normalize_barcode,
    normalize_text,
)


INVENTORY_FIELDS = (
    'sku',
    'barcode',
    'description',
    'brand',
    'unit',
    'stock_quantity',
    'last_import_session',
)


def _validate_identity_compatibility(source, target):
    source_identity = _identity_for_product(source)
    target_identity = _identity_for_product(target)

    source_barcode = normalize_barcode(source_identity.barcode)
    target_barcode = normalize_barcode(target_identity.barcode)
    if source_barcode and target_barcode and source_barcode != target_barcode:
        raise ValueError('Cannot merge products with conflicting barcodes.')

    source_brand = normalize_text(source_identity.brand)
    target_brand = normalize_text(target_identity.brand)
    if source_brand and target_brand and source_brand != target_brand:
        raise ValueError('Cannot merge products with conflicting structured brands.')

    if not _package_compatible(source_identity, target_identity):
        raise ValueError('Cannot merge products with different structured package sizes.')


def _merge_identity(source, target):
    try:
        source_identity = source.identity
    except ProductIdentity.DoesNotExist:
        source_identity = None
    target_identity = ensure_product_identity(target)

    if source_identity:
        ensure_product_identity(
            target,
            brand=target_identity.brand or source_identity.brand,
            variant=target_identity.variant or source_identity.variant,
            barcode=target_identity.barcode or source_identity.barcode,
            unit=target_identity.package_unit or source_identity.package_unit,
            source=(
                target_identity.source
                if target_identity.source != ProductIdentity.Source.INFERRED
                else source_identity.source
            ),
            confidence=target_identity.confidence or source_identity.confidence,
        )
        # Preserve an explicitly stored quantity/count that cannot be inferred
        # from the target's display name.
        target_identity.refresh_from_db()
        changed = []
        if target_identity.package_quantity is None and source_identity.package_quantity is not None:
            target_identity.package_quantity = source_identity.package_quantity
            changed.append('package_quantity')
        if target_identity.pack_count is None and source_identity.pack_count is not None:
            target_identity.pack_count = source_identity.pack_count
            changed.append('pack_count')
        if changed:
            target_identity.save(update_fields=changed + ['updated_at'])
        source_identity.delete()


def _merge_inventory(source, target):
    for source_item in BusinessInventoryItem.objects.filter(product=source).select_related('business'):
        target_item = BusinessInventoryItem.objects.filter(
            business=source_item.business,
            product=target,
        ).first()
        if target_item is None:
            source_item.product = target
            source_item.save(update_fields=['product', 'updated_at'])
            continue

        source_is_newer = source_item.updated_at and (
            not target_item.updated_at or source_item.updated_at > target_item.updated_at
        )
        changed = []
        for field in INVENTORY_FIELDS:
            source_value = getattr(source_item, field)
            target_value = getattr(target_item, field)
            should_copy = source_value not in (None, '') and (
                target_value in (None, '') or source_is_newer
            )
            if should_copy and target_value != source_value:
                setattr(target_item, field, source_value)
                changed.append(field)
        if changed:
            target_item.save(update_fields=changed + ['updated_at'])
        source_item.delete()


def _merge_watchlists(source, target):
    for watch in ProductWatchlist.objects.filter(product=source):
        ProductWatchlist.objects.get_or_create(user=watch.user, product=target)
        watch.delete()


def _merge_aliases(source, target, reviewed_by=None):
    ProductAlias.objects.get_or_create(
        canonical_product=target,
        alias_name=source.name,
        defaults={'created_by': reviewed_by},
    )
    for alias in ProductAlias.objects.filter(canonical_product=source):
        ProductAlias.objects.get_or_create(
            canonical_product=target,
            alias_name=alias.alias_name,
            defaults={'created_by': alias.created_by or reviewed_by},
        )
        alias.delete()


def _move_generic_comments(source, target):
    product_type = ContentType.objects.get_for_model(Product)
    Comment.objects.filter(
        content_type=product_type,
        object_id=source.pk,
    ).update(object_id=target.pk)


def _remaining_reverse_relations(product):
    remaining = []
    for relation in product._meta.related_objects:
        accessor = relation.get_accessor_name()
        if not accessor:
            continue
        try:
            related = getattr(product, accessor)
        except Exception:
            continue
        if relation.one_to_one:
            try:
                value = related
            except relation.related_model.DoesNotExist:
                value = None
            if value is not None:
                remaining.append(relation.related_model._meta.label)
        else:
            try:
                if related.exists():
                    remaining.append(relation.related_model._meta.label)
            except AttributeError:
                continue
    return sorted(set(remaining))


@transaction.atomic
def merge_products(source_product, target_product, *, reviewed_by=None):
    """
    Merge source into target without allowing related records to disappear.

    The canonical target keeps its ID. The source name and aliases become
    aliases of the target. Conflicting barcode/brand/package identity blocks
    the merge rather than guessing.
    """
    if not source_product or not target_product:
        raise ValueError('Both source and target products are required.')
    if source_product.pk == target_product.pk:
        raise ValueError('A product cannot be merged into itself.')

    locked = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=[source_product.pk, target_product.pk]
        )
    }
    if len(locked) != 2:
        raise ValueError('One of the selected products no longer exists.')
    source = locked[source_product.pk]
    target = locked[target_product.pk]

    _validate_identity_compatibility(source, target)
    _merge_identity(source, target)

    if not target.description and source.description:
        target.description = source.description
    if target.category_id is None and source.category_id is not None:
        target.category = source.category
    if not target.image and source.image:
        target.image = source.image
    target.save()

    target.tags.add(*list(source.tags.names()))
    _merge_aliases(source, target, reviewed_by=reviewed_by)
    _merge_inventory(source, target)
    _merge_watchlists(source, target)
    _move_generic_comments(source, target)

    PriceReport.objects.filter(product=source).update(product=target)
    ProductImage.objects.filter(product=source).update(product=target)
    BulkImportRow.objects.filter(product=source).update(product=target)
    Notification.objects.filter(product=source).update(product=target)
    ShoppingListItem.objects.filter(product=source).update(product=target)

    # Duplicate-review rows are advisory. Once this product is merged, any
    # pair involving it is obsolete and can be rebuilt around the canonical ID.
    ProductDuplicateCandidate.objects.filter(
        Q(source_product=source) | Q(candidate_product=source)
    ).delete()

    remaining = _remaining_reverse_relations(source)
    # Generic comments are checked separately because GenericRelation is not a
    # normal reverse ForeignKey relation.
    product_type = ContentType.objects.get_for_model(Product)
    if Comment.objects.filter(content_type=product_type, object_id=source.pk).exists():
        remaining.append('comments.Comment')

    if remaining:
        raise ValueError(
            'Merge stopped because unhandled related records remain: '
            + ', '.join(sorted(set(remaining)))
        )

    source_id = source.pk
    source_name = source.name
    source.delete()
    return {
        'source_id': source_id,
        'source_name': source_name,
        'target_id': target.pk,
        'target_name': target.name,
    }
