from decimal import Decimal

from django.db import transaction

from catalog.value import VALUE_STALE_AFTER_DAYS, build_basket_comparison
from core.models import Product, ShoppingList, ShoppingListItem

from .current_price_services import _absolute_url
from .models import MCPAuditLog


def _money(value):
    return str(value) if value is not None else None


def _owned_lists(actor):
    return ShoppingList.objects.filter(user=actor.user)


def _resolve_list(actor, shopping_list_id=None, *, create_default=False, for_update=False):
    queryset = _owned_lists(actor)
    if for_update:
        queryset = queryset.select_for_update()

    if shopping_list_id is not None:
        shopping_list = queryset.filter(pk=shopping_list_id).first()
        if not shopping_list:
            raise ValueError(f'Shopping list {shopping_list_id} was not found for the authenticated user.')
        return shopping_list, False

    count = queryset.count()
    if count > 1:
        raise ValueError('Multiple shopping lists exist. Call list_shopping_lists and provide shopping_list_id explicitly.')
    if count == 1:
        return queryset.first(), False
    if not create_default:
        raise ValueError('No shopping list exists for the authenticated user.')

    shopping_list = ShoppingList.objects.create(user=actor.user, name='My Shopping List')
    return shopping_list, True


def _touch(shopping_list):
    # Keep the list ordering meaningful when items are changed through MCP.
    shopping_list.save(update_fields=['updated_at'])


def _serialize_item(item):
    product = item.product
    return {
        'id': item.pk,
        'shopping_list_id': item.shopping_list_id,
        'product_id': item.product_id,
        'product_name': product.name if product else None,
        'item_name': item.item_name or (product.name if product else ''),
        'quantity': item.quantity,
        'is_checked': item.is_checked,
        'is_resolved_product': bool(item.product_id),
        'created_at': item.created_at,
        'product_url': _absolute_url(f'/product/{product.pk}/') if product else None,
    }


def _serialize_list_summary(shopping_list, items=None):
    items = list(items) if items is not None else list(shopping_list.items.all())
    unchecked = [item for item in items if not item.is_checked]
    checked = [item for item in items if item.is_checked]
    product_items = [item for item in unchecked if item.product_id]
    custom_items = [item for item in unchecked if not item.product_id]
    return {
        'id': shopping_list.pk,
        'name': shopping_list.name,
        'created_at': shopping_list.created_at,
        'updated_at': shopping_list.updated_at,
        'item_count': len(items),
        'unchecked_item_count': len(unchecked),
        'checked_item_count': len(checked),
        'unchecked_product_item_count': len(product_items),
        'unchecked_custom_item_count': len(custom_items),
        'url': _absolute_url('/shopping-list/'),
        'compare_url': _absolute_url('/shopping-list/compare/'),
    }


def _idempotent_add_replay(actor, idempotency_key, expected_arguments):
    key = (idempotency_key or '').strip()
    if not key:
        return None

    previous = MCPAuditLog.objects.filter(
        tool_name='add_shopping_list_item',
        user=actor.user,
        status=MCPAuditLog.Status.SUCCEEDED,
        arguments__idempotency_key=key,
    ).order_by('-completed_at', '-id').first()
    if not previous:
        return None

    for field in ('product_id', 'shopping_list_id', 'quantity'):
        if previous.arguments.get(field) != expected_arguments.get(field):
            raise ValueError('This idempotency_key was already used for a different shopping-list add request.')

    replay = dict(previous.response_summary or {})
    replay['idempotent_replay'] = True
    replay['idempotency_key'] = key
    return replay


def list_shopping_lists(actor):
    lists = list(_owned_lists(actor).prefetch_related('items').order_by('-updated_at', '-id'))
    return {
        'count': len(lists),
        'shopping_lists': [
            _serialize_list_summary(shopping_list, list(shopping_list.items.all()))
            for shopping_list in lists
        ],
        'selection_note': (
            'If more than one list exists, pass shopping_list_id explicitly to read, write, or compare tools. '
            'Read tools never create a list.'
        ),
    }


def get_shopping_list(actor, shopping_list_id=None, *, include_checked=True, limit=200):
    shopping_list, _created = _resolve_list(actor, shopping_list_id)
    queryset = shopping_list.items.select_related('product').order_by('is_checked', '-created_at', '-id')
    all_items = list(queryset)
    visible_items = all_items if include_checked else [item for item in all_items if not item.is_checked]
    limit = max(1, min(int(limit), 500))
    visible_items = visible_items[:limit]
    return {
        'shopping_list': _serialize_list_summary(shopping_list, all_items),
        'include_checked': bool(include_checked),
        'items_returned': len(visible_items),
        'items': [_serialize_item(item) for item in visible_items],
        'unresolved_item_count': sum(1 for item in all_items if not item.is_checked and not item.product_id),
        'note': (
            'Items without a product_id are preserved as unresolved custom items. MCP does not silently match or '
            'substitute them; use search_products and then add an exact product if the user chooses one.'
        ),
    }


def add_shopping_list_item(
    actor,
    product_id,
    *,
    shopping_list_id=None,
    quantity=1,
    idempotency_key=None,
):
    product_id = int(product_id)
    quantity = int(quantity)
    if product_id <= 0:
        raise ValueError('product_id must be greater than zero.')
    if quantity <= 0:
        raise ValueError('quantity must be greater than zero.')

    key = (idempotency_key or '').strip()[:120] or None
    replay = _idempotent_add_replay(actor, key, {
        'product_id': product_id,
        'shopping_list_id': shopping_list_id,
        'quantity': quantity,
    })
    if replay:
        return replay

    product = Product.objects.filter(pk=product_id).first()
    if not product:
        raise ValueError(f'Product {product_id} was not found.')

    with transaction.atomic():
        shopping_list, list_created = _resolve_list(
            actor,
            shopping_list_id,
            create_default=True,
            for_update=True,
        )
        existing = shopping_list.items.select_for_update().select_related('product').filter(
            product_id=product_id,
        ).order_by('is_checked', '-created_at', '-id').first()

        if existing:
            previous_quantity = existing.quantity
            existing.quantity += quantity
            fields = ['quantity']
            if existing.is_checked:
                existing.is_checked = False
                fields.append('is_checked')
            existing.save(update_fields=fields)
            _touch(shopping_list)
            return {
                'action': 'quantity_increased',
                'list_created': list_created,
                'shopping_list': _serialize_list_summary(shopping_list),
                'item': _serialize_item(existing),
                'previous_quantity': previous_quantity,
                'added_quantity': quantity,
                'idempotency_key': key,
                'note': (
                    'This matches Wikonomi website add behavior: an existing product quantity is increased rather than '
                    'creating a duplicate row. A previously checked item is made active again.'
                ),
            }

        item = ShoppingListItem.objects.create(
            shopping_list=shopping_list,
            product=product,
            item_name=product.name,
            quantity=quantity,
            is_checked=False,
        )
        _touch(shopping_list)
        return {
            'action': 'created',
            'list_created': list_created,
            'shopping_list': _serialize_list_summary(shopping_list),
            'item': _serialize_item(item),
            'added_quantity': quantity,
            'idempotency_key': key,
            'note': 'An exact Wikonomi product was added. No substitute product was inferred.',
        }


def update_shopping_list_item(actor, item_id, *, quantity=None, is_checked=None):
    if quantity is None and is_checked is None:
        raise ValueError('Provide quantity and/or is_checked to update the item.')
    if quantity is not None:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError('quantity must be greater than zero.')

    with transaction.atomic():
        item = ShoppingListItem.objects.select_for_update().select_related('shopping_list', 'product').filter(
            pk=item_id,
            shopping_list__user=actor.user,
        ).first()
        if not item:
            raise ValueError(f'Shopping list item {item_id} was not found for the authenticated user.')

        changed_fields = []
        if quantity is not None and item.quantity != quantity:
            item.quantity = quantity
            changed_fields.append('quantity')
        if is_checked is not None and item.is_checked != bool(is_checked):
            item.is_checked = bool(is_checked)
            changed_fields.append('is_checked')

        if changed_fields:
            item.save(update_fields=changed_fields)
            _touch(item.shopping_list)

        return {
            'action': 'updated' if changed_fields else 'unchanged',
            'changed_fields': changed_fields,
            'shopping_list': _serialize_list_summary(item.shopping_list),
            'item': _serialize_item(item),
        }


def remove_shopping_list_item(actor, item_id):
    with transaction.atomic():
        item = ShoppingListItem.objects.select_for_update().select_related('shopping_list', 'product').filter(
            pk=item_id,
            shopping_list__user=actor.user,
        ).first()
        if not item:
            return {
                'removed': False,
                'item_id': int(item_id),
                'reason': 'not_found_in_authenticated_user_lists',
                'note': 'Nothing was changed. This also makes a repeated remove call safe.',
            }

        shopping_list = item.shopping_list
        removed_item = _serialize_item(item)
        item.delete()
        _touch(shopping_list)
        return {
            'removed': True,
            'shopping_list': _serialize_list_summary(shopping_list),
            'removed_item': removed_item,
        }


def _serialize_basket_line(line):
    report = line['report']
    product = line['product']
    return {
        'product_id': product.pk,
        'product_name': product.name,
        'quantity': line['quantity'],
        'unit_price': _money(line['unit_price']),
        'line_total': _money(line['line_total']),
        'price_report_id': report.pk,
        'business': report.get_business_display(),
        'business_id': report.business_id,
        'business_branch_id': report.business_branch_id,
        'observed_at': report.observed_at,
    }


def _serialize_store(store):
    if not store:
        return None
    return {
        'store_name': store['store_name'],
        'business_id': store['business'].pk if store.get('business') else None,
        'business_branch_id': store['business_branch'].pk if store.get('business_branch') else None,
        'coverage_count': store['coverage_count'],
        'coverage_total': store['coverage_total'],
        'coverage_percent': _money(store['coverage_percent']),
        'is_full_basket': store['is_full_basket'],
        'total': _money(store['total']),
        'items': [_serialize_basket_line(line) for line in store['items']],
    }


def compare_shopping_list(actor, shopping_list_id=None, *, currency='PGK'):
    shopping_list, _created = _resolve_list(actor, shopping_list_id)
    items = list(
        shopping_list.items.select_related(
            'product',
            'product__category',
            'product__identity',
        ).order_by('is_checked', '-created_at', '-id')
    )
    comparison = build_basket_comparison(
        items,
        currency=(currency or 'PGK').upper()[:3],
        stale_after_days=VALUE_STALE_AFTER_DAYS,
    )

    unresolved = list(comparison['custom_items'])
    checked = [item for item in items if item.is_checked]
    return {
        'shopping_list': _serialize_list_summary(shopping_list, items),
        'currency': comparison['currency'],
        'stale_after_days': comparison['stale_after_days'],
        'product_item_count': comparison['product_item_count'],
        'checked_item_count_excluded': len(checked),
        'unresolved_custom_items': [_serialize_item(item) for item in unresolved],
        'full_basket_store_count': comparison['full_basket_store_count'],
        'cheapest_full_store': _serialize_store(comparison['cheapest_full_store']),
        'best_coverage_store': _serialize_store(comparison['best_coverage_store']),
        'stores': [_serialize_store(store) for store in comparison['store_rows']],
        'split_store': {
            'complete': comparison['split_complete'],
            'total': _money(comparison['split_total']),
            'items': [_serialize_basket_line(line) for line in comparison['split_lines']],
            'saving_vs_cheapest_complete_store': {
                'amount': _money(comparison['full_store_savings_amount']),
                'percent': _money(comparison['full_store_savings_percent']),
            },
        },
        'missing_current_price_products': [
            {'id': product.pk, 'name': product.name}
            for product in comparison['missing_products']
        ],
        'note': (
            'Only unchecked items linked to exact Wikonomi product IDs are compared. Checked items are excluded, '
            'unresolved custom items are surfaced separately, no substitutions are made, and split-store totals '
            'exclude transport, time, and other shopping costs.'
        ),
    }
