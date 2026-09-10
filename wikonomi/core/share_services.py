from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from .models import PriceReport
from .product_views import (
    COMPARISON_STALE_AFTER_DAYS,
    _freshness_metadata,
    _latest_store_price_ids,
    _product_family_ids,
    _store_key,
)


def _money(currency, value):
    if value is None:
        return None
    return f"{(currency or 'PGK').upper()} {Decimal(value):,.2f}"


def _observed_label(value):
    if not value:
        return 'date unknown'
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return date_format(value, 'M j, Y')


def _store_name(report):
    if not report:
        return 'Unknown store'
    return report.get_business_display() or 'Unknown store'


def _absolute(base_url, path):
    if not base_url:
        return path
    return f"{base_url.rstrip('/')}{path}"


def _truncate(value, limit=260):
    value = ' '.join((value or '').split())
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 1)].rstrip() + '…'


def build_price_share_context(report, *, base_url=''):
    """Build safe, current-price-aware copy for sharing one price observation.

    The shared report is always described as an observation. Current comparison
    uses the same latest-per-store and 90-day stale rules as the product page, so
    an older/stale report can never be advertised as the current winner.
    """
    product = report.product
    currency = (report.currency or 'PGK').upper()
    product_ids = _product_family_ids(product)

    analysis_reports = PriceReport.objects.filter(
        product_id__in=product_ids,
        marked_for_deletion=False,
        price__gt=0,
    ).exclude(currency='')

    current_ids = _latest_store_price_ids(analysis_reports)
    current_id_set = set(current_ids)
    current_reports = list(
        PriceReport.objects.filter(id__in=current_ids, currency=currency)
        .select_related('product', 'business', 'business_branch')
        .order_by('price', '-observed_at', '-id')
    )

    cutoff = timezone.now() - timedelta(days=COMPARISON_STALE_AFTER_DAYS)
    comparable = [row for row in current_reports if row.observed_at and row.observed_at >= cutoff]
    comparable.sort(key=lambda row: (row.price, -row.observed_at.timestamp(), -row.id))

    cheapest = comparable[0] if comparable else None
    highest = comparable[-1] if comparable else None
    store_keys = {_store_key(row) for row in comparable if _store_key(row) is not None}
    store_count = len(store_keys)

    shared_store_key = _store_key(report)
    same_store_latest = next(
        (
            row
            for row in current_reports
            if _store_key(row) == shared_store_key and row.currency == currency
        ),
        None,
    ) if shared_store_key is not None else None

    freshness = _freshness_metadata(report.observed_at)
    is_latest_store_observation = report.id in current_id_set
    is_current_comparable = (
        is_latest_store_observation
        and not report.marked_for_deletion
        and freshness['key'] != 'stale'
        and any(row.id == report.id for row in comparable)
    )

    report_url = _absolute(base_url, reverse('price_detail', args=[report.pk]))
    share_url = _absolute(base_url, reverse('price_share', args=[report.pk]))
    compare_url = _absolute(base_url, reverse('product_detail', args=[product.pk]))
    report_money = _money(currency, report.price)
    store_name = _store_name(report)
    observed_label = _observed_label(report.observed_at)

    if report.marked_for_deletion:
        status_line = 'This report is marked for deletion and is excluded from current price comparisons.'
    elif not is_latest_store_observation:
        if same_store_latest:
            status_line = (
                f"This is an older observation. Latest known at {store_name}: "
                f"{_money(currency, same_store_latest.price)} ({_observed_label(same_store_latest.observed_at)})."
            )
        else:
            status_line = 'This is an older observation and is not used as the current store price.'
    elif freshness['key'] == 'stale':
        age = freshness.get('age_days')
        age_text = f"{age} days old" if age is not None else 'older than the current-price window'
        status_line = (
            f"Latest known at {store_name}, but {age_text}; it is excluded from the current cheapest ranking."
        )
    else:
        status_line = f"Current Wikonomi observation • {freshness['label']}."

    comparison_line = ''
    savings_amount = None
    savings_percent = None
    gap_from_best = None
    gap_percent = None

    if store_count > 1 and cheapest and highest:
        if is_current_comparable and report.id == cheapest.id:
            savings_amount = highest.price - cheapest.price
            if highest.price > 0 and savings_amount > 0:
                savings_percent = (savings_amount / highest.price) * Decimal('100')
                comparison_line = (
                    f"Lowest current Wikonomi price across {store_count} stores — save up to "
                    f"{_money(currency, savings_amount)} ({savings_percent:.1f}%) versus the highest current price."
                )
            else:
                comparison_line = f"Lowest current Wikonomi price across {store_count} stores."
        elif is_current_comparable:
            gap_from_best = report.price - cheapest.price
            if cheapest.price > 0 and gap_from_best > 0:
                gap_percent = (gap_from_best / cheapest.price) * Decimal('100')
                comparison_line = (
                    f"Best current Wikonomi price: {_money(currency, cheapest.price)} at {_store_name(cheapest)}. "
                    f"This price is {_money(currency, gap_from_best)} ({gap_percent:.1f}%) higher; "
                    f"compared across {store_count} stores."
                )
            else:
                comparison_line = (
                    f"Best current Wikonomi price: {_money(currency, cheapest.price)} at {_store_name(cheapest)} "
                    f"across {store_count} stores."
                )
        else:
            comparison_line = (
                f"Current best: {_money(currency, cheapest.price)} at {_store_name(cheapest)} "
                f"across {store_count} stores."
            )
    elif store_count == 1 and cheapest:
        if is_current_comparable and report.id == cheapest.id:
            comparison_line = 'Only one current store price is available, so there is no store-to-store comparison yet.'
        else:
            comparison_line = (
                f"Only one current store price is available: {_money(currency, cheapest.price)} "
                f"at {_store_name(cheapest)}."
            )
    else:
        comparison_line = 'No non-stale current store comparison is available yet.'

    title = f"{product.name} — {report_money} at {store_name}"
    text_lines = [
        f"{product.name} — {report_money} at {store_name}",
        status_line,
        comparison_line,
        f"Observed {observed_label}.",
        f"Open on Wikonomi: {share_url}",
    ]
    text = '\n'.join(line for line in text_lines if line)
    preview_description = _truncate(
        f"{report_money} at {store_name}. {comparison_line} Observed {observed_label}."
    )

    return {
        'title': title,
        'text': text,
        'status_line': status_line,
        'comparison_line': comparison_line,
        'preview_description': preview_description,
        'report_url': report_url,
        'share_url': share_url,
        'compare_url': compare_url,
        'observed_label': observed_label,
        'report_money': report_money,
        'store_name': store_name,
        'currency': currency,
        'store_count': store_count,
        'freshness_key': freshness['key'],
        'freshness_label': freshness['label'],
        'freshness_age_days': freshness.get('age_days'),
        'is_latest_store_observation': is_latest_store_observation,
        'is_current_comparable': is_current_comparable,
        'best_current_price': str(cheapest.price) if cheapest else None,
        'best_current_price_label': _money(currency, cheapest.price) if cheapest else None,
        'best_current_store': _store_name(cheapest) if cheapest else None,
        'highest_current_price': str(highest.price) if highest else None,
        'highest_current_price_label': _money(currency, highest.price) if highest else None,
        'savings_amount': str(savings_amount) if savings_amount is not None else None,
        'savings_amount_label': _money(currency, savings_amount) if savings_amount is not None else None,
        'savings_percent': str(savings_percent) if savings_percent is not None else None,
        'gap_from_best': str(gap_from_best) if gap_from_best is not None else None,
        'gap_from_best_label': _money(currency, gap_from_best) if gap_from_best is not None else None,
        'gap_percent': str(gap_percent) if gap_percent is not None else None,
        'stale_after_days': COMPARISON_STALE_AFTER_DAYS,
    }
