from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from core.models import (
    BulkImportImage,
    BulkImportRow,
    BulkImportSession,
    BusinessInventoryItem,
    Category,
    PriceReport,
    Product,
)
from core.services.image_processor import create_product_image


def _unique_slug(model, value):
    base = slugify(value)[:220] or 'item'
    candidate = base
    index = 2
    while model.objects.filter(slug=candidate).exists():
        candidate = f'{base[:210]}-{index}'
        index += 1
    return candidate


def _resolve_product(row, user):
    product = Product.objects.filter(name__iexact=row.product_name).first()
    if product is None:
        product = Product.objects.create(
            name=row.product_name,
            slug=_unique_slug(Product, row.product_name),
            description=row.description,
            created_by=user,
            created_via='bulk_import',
        )
        created = True
    else:
        created = False

    changed_fields = []
    if row.description and not product.description:
        product.description = row.description
        changed_fields.append('description')
    if row.category_name and product.category_id is None:
        category = Category.objects.filter(name__iexact=row.category_name).first()
        if category is None:
            try:
                category = Category.objects.create(
                    name=row.category_name,
                    slug=_unique_slug(Category, row.category_name),
                )
            except IntegrityError:
                category = Category.objects.filter(name__iexact=row.category_name).first()
        product.category = category
        changed_fields.append('category')
    if changed_fields:
        product.save(update_fields=changed_fields)
    if row.tags:
        product.tags.add(*[
            tag.strip()
            for tag in row.tags.split(',')
            if tag.strip()
        ])
    return product, created


def _import_row(row, session):
    with transaction.atomic():
        product, created = _resolve_product(row, session.user)
        BusinessInventoryItem.objects.update_or_create(
            business=session.business,
            product=product,
            defaults={
                'sku': row.sku,
                'barcode': row.barcode,
                'description': row.description,
                'brand': row.brand,
                'unit': row.unit,
                'stock_quantity': row.stock_quantity,
                'last_import_session': session,
            },
        )
        latitude = longitude = None
        location = session.business.get_default_location()
        if location:
            latitude, longitude = location
        report = PriceReport.objects.create(
            product=product,
            business=session.business,
            user=session.user,
            price=row.price,
            currency=row.currency,
            latitude=latitude,
            longitude=longitude,
            notes=row.notes,
            created_via='bulk_import',
        )
        row.product = product
        row.price_report = report
        row.status = BulkImportRow.Status.IMPORTED
        row.imported_at = timezone.now()
        row.save(update_fields=[
            'product',
            'price_report',
            'status',
            'imported_at',
        ])
    return created


def _append_warning(session, message):
    warnings = list(session.warnings or [])
    warnings.append(message)
    session.warnings = warnings[-500:]


def _progress_payload(session):
    elapsed_seconds = 0
    if session.started_at:
        elapsed_seconds = max((timezone.now() - session.started_at).total_seconds(), 0)
    remaining_seconds = None
    if 0 < session.progress_percent < 100 and elapsed_seconds:
        remaining_seconds = round(
            elapsed_seconds * (100 - session.progress_percent) / session.progress_percent
        )
    return {
        'status': session.status,
        'stage': session.current_stage,
        'progress_percent': session.progress_percent,
        'products_created': session.products_created,
        'price_reports_created': session.price_reports_created,
        'photos_processed': session.photos_processed,
        'estimated_remaining_seconds': remaining_seconds,
        'completion_url': (
            f'/bulk-upload/{session.pk}/complete/'
            if session.status == BulkImportSession.Status.COMPLETED
            else None
        ),
    }


def process_import_batch(session, *, row_batch_size=50, image_batch_size=20):
    """Process one idempotent unit of work and return live progress data."""
    if session.status == BulkImportSession.Status.COMPLETED:
        return _progress_payload(session)
    if session.started_at is None:
        session.started_at = timezone.now()
    session.status = BulkImportSession.Status.PROCESSING

    pending_rows = list(
        session.rows.filter(status=BulkImportRow.Status.VALID)
        .order_by('row_number')[:row_batch_size]
    )
    if pending_rows:
        session.current_stage = 'Creating products and prices'
        for row in pending_rows:
            try:
                created = _import_row(row, session)
                if created:
                    session.products_created += 1
                session.price_reports_created += 1
            except Exception as exc:
                row.status = BulkImportRow.Status.FAILED
                row.validation_errors = [f'Import failed: {exc}']
                row.save(update_fields=['status', 'validation_errors'])
                _append_warning(session, f'Row {row.row_number}: {exc}')

        completed_rows = session.rows.filter(
            status__in=[
                BulkImportRow.Status.IMPORTED,
                BulkImportRow.Status.FAILED,
            ]
        ).count()
        denominator = max(session.valid_rows, 1)
        session.progress_percent = min(75, 40 + int(35 * completed_rows / denominator))
        session.save(update_fields=[
            'started_at',
            'status',
            'current_stage',
            'products_created',
            'price_reports_created',
            'progress_percent',
            'warnings',
            'updated_at',
        ])
        return _progress_payload(session)

    pending_images = list(
        session.images.filter(
            status=BulkImportImage.Status.MATCHED,
            matched_row__status=BulkImportRow.Status.IMPORTED,
        )
        .select_related(
            'matched_row__product',
            'session__business',
        )
        .order_by('sort_order', 'uploaded_at')[:image_batch_size]
    )
    if pending_images:
        session.current_stage = 'Optimising product photos'
        for image in pending_images:
            try:
                create_product_image(image)
                image.status = BulkImportImage.Status.IMPORTED
                image.imported_at = timezone.now()
                image.save(update_fields=['status', 'imported_at'])
                session.photos_processed += 1
            except Exception as exc:
                image.status = BulkImportImage.Status.REJECTED
                image.error = str(exc)
                image.save(update_fields=['status', 'error'])
                _append_warning(session, f'{image.original_filename}: {exc}')

        image_total = max(session.matched_images, 1)
        session.progress_percent = min(
            95,
            75 + int(20 * session.photos_processed / image_total),
        )
        session.save(update_fields=[
            'started_at',
            'status',
            'current_stage',
            'photos_processed',
            'progress_percent',
            'warnings',
            'updated_at',
        ])
        return _progress_payload(session)

    session.status = BulkImportSession.Status.COMPLETED
    session.current_stage = 'Import complete'
    session.progress_percent = 100
    session.completed_at = timezone.now()
    session.last_error = ''
    session.save(update_fields=[
        'started_at',
        'status',
        'current_stage',
        'progress_percent',
        'completed_at',
        'last_error',
        'warnings',
        'updated_at',
    ])
    return _progress_payload(session)
