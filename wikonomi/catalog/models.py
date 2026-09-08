from django.conf import settings
from django.db import models


class ProductIdentity(models.Model):
    class Unit(models.TextChoices):
        GRAM = 'g', 'Gram'
        KILOGRAM = 'kg', 'Kilogram'
        MILLILITRE = 'ml', 'Millilitre'
        LITRE = 'l', 'Litre'
        EACH = 'each', 'Each'
        METRE = 'm', 'Metre'
        CENTIMETRE = 'cm', 'Centimetre'
        OTHER = 'other', 'Other'

    class Source(models.TextChoices):
        INFERRED = 'inferred', 'Inferred from name'
        WEB = 'web', 'Website'
        BULK_IMPORT = 'bulk_import', 'Bulk import'
        MCP = 'mcp', 'MCP'
        MANUAL = 'manual', 'Manual review'

    product = models.OneToOneField(
        'core.Product',
        on_delete=models.CASCADE,
        related_name='identity',
    )
    brand = models.CharField(max_length=120, blank=True, db_index=True)
    variant = models.CharField(max_length=160, blank=True)
    package_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    package_unit = models.CharField(
        max_length=16,
        choices=Unit.choices,
        blank=True,
        db_index=True,
    )
    pack_count = models.PositiveIntegerField(null=True, blank=True)
    barcode = models.CharField(max_length=64, blank=True, db_index=True)
    normalized_barcode = models.CharField(max_length=64, blank=True, db_index=True)
    identity_signature = models.CharField(max_length=512, blank=True, db_index=True)
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.INFERRED,
        db_index=True,
    )
    confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['brand', 'package_unit']),
            models.Index(fields=['normalized_barcode']),
            models.Index(fields=['identity_signature']),
        ]

    def __str__(self):
        return f'Identity for {self.product.name}'


class ProductDuplicateCandidate(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        CONFIRMED = 'confirmed', 'Confirmed duplicate'
        REJECTED = 'rejected', 'Not a duplicate'

    source_product = models.ForeignKey(
        'core.Product',
        on_delete=models.CASCADE,
        related_name='duplicate_candidates_started',
    )
    candidate_product = models.ForeignKey(
        'core.Product',
        on_delete=models.CASCADE,
        related_name='duplicate_candidates_received',
    )
    similarity_score = models.DecimalField(max_digits=5, decimal_places=4)
    match_basis = models.CharField(max_length=80)
    details = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_product_duplicates',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['source_product', 'candidate_product'],
                name='unique_product_duplicate_candidate_pair',
            ),
            models.CheckConstraint(
                condition=~models.Q(source_product=models.F('candidate_product')),
                name='product_duplicate_candidate_not_self',
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-similarity_score']),
        ]
        ordering = ['status', '-similarity_score', '-created_at']

    def __str__(self):
        return f'{self.source_product} ~ {self.candidate_product} ({self.similarity_score})'
