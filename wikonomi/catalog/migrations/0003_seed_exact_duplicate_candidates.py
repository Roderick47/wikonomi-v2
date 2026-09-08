from decimal import Decimal

from django.db import migrations


def seed_candidates(apps, schema_editor):
    ProductIdentity = apps.get_model('catalog', 'ProductIdentity')
    ProductDuplicateCandidate = apps.get_model('catalog', 'ProductDuplicateCandidate')

    seen_barcodes = {}
    seen_signatures = {}
    candidates = {}

    identities = ProductIdentity.objects.exclude(product_id__isnull=True).order_by('product_id')
    for identity in identities.iterator(chunk_size=500):
        if identity.normalized_barcode:
            existing = seen_barcodes.get(identity.normalized_barcode)
            if existing and existing != identity.product_id:
                pair = tuple(sorted((existing, identity.product_id)))
                candidates[pair] = (Decimal('1.0000'), 'duplicate_barcode', {
                    'barcode': identity.normalized_barcode,
                })
            else:
                seen_barcodes[identity.normalized_barcode] = identity.product_id

        if identity.identity_signature and identity.package_quantity is not None:
            existing = seen_signatures.get(identity.identity_signature)
            if existing and existing != identity.product_id:
                pair = tuple(sorted((existing, identity.product_id)))
                candidates.setdefault(pair, (Decimal('1.0000'), 'duplicate_structured_identity', {
                    'identity_signature': identity.identity_signature,
                }))
            else:
                seen_signatures[identity.identity_signature] = identity.product_id

    rows = [
        ProductDuplicateCandidate(
            source_product_id=source_id,
            candidate_product_id=candidate_id,
            similarity_score=score,
            match_basis=basis,
            details=details,
            status='pending',
        )
        for (source_id, candidate_id), (score, basis, details) in candidates.items()
    ]
    ProductDuplicateCandidate.objects.bulk_create(rows, ignore_conflicts=True, batch_size=500)


def reverse_seed(apps, schema_editor):
    ProductDuplicateCandidate = apps.get_model('catalog', 'ProductDuplicateCandidate')
    ProductDuplicateCandidate.objects.filter(
        match_basis__in=['duplicate_barcode', 'duplicate_structured_identity']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_backfill_product_identities'),
    ]

    operations = [
        migrations.RunPython(seed_candidates, reverse_seed),
    ]
