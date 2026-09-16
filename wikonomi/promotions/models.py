from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class PromotionQuerySet(models.QuerySet):
    def active(self, at=None):
        at = at or timezone.now()
        return self.filter(start_at__lte=at).filter(
            Q(end_at__isnull=True) | Q(end_at__gte=at)
        )

    def upcoming(self, at=None):
        at = at or timezone.now()
        return self.filter(start_at__gt=at)

    def expired(self, at=None):
        at = at or timezone.now()
        return self.filter(end_at__isnull=False, end_at__lt=at)


class Promotion(models.Model):
    class Kind(models.TextChoices):
        SALE = 'sale', 'Sale / special'
        CLEARANCE = 'clearance', 'Clearance'
        EVENT = 'event', 'Promotional event'

    class DealType(models.TextChoices):
        PERCENT = 'percent', 'Percentage off'
        AMOUNT_OFF = 'amount_off', 'Kina amount off'
        FIXED_PRICE = 'fixed_price', 'Special price'
        MULTIBUY = 'multibuy', 'Multi-buy / buy X get Y'
        OTHER = 'other', 'Other offer'

    class Scope(models.TextChoices):
        STOREWIDE = 'storewide', 'Entire store'
        CATEGORY = 'category', 'Category / subcategory'
        PRODUCT = 'product', 'Specific product'

    class Source(models.TextChoices):
        COMMUNITY = 'community', 'Community report'
        BUSINESS = 'business', 'Business-posted'
        ADMIN = 'admin', 'Wikonomi verified/admin'

    business = models.ForeignKey(
        'core.Business',
        on_delete=models.CASCADE,
        related_name='promotions',
    )
    business_branch = models.ForeignKey(
        'core.BusinessBranch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promotions',
        help_text='Optional: limit this promotion to one branch/location.',
    )
    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SALE, db_index=True)
    deal_type = models.CharField(max_length=20, choices=DealType.choices, default=DealType.PERCENT)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.STOREWIDE, db_index=True)
    discount_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Percent or kina amount, depending on deal type.',
    )
    special_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Used for a directly observed special price.',
    )
    description = models.TextField(blank=True)
    terms = models.TextField(blank=True, help_text='Exclusions or conditions shown on the promotion.')
    start_at = models.DateTimeField(default=timezone.now, db_index=True)
    end_at = models.DateTimeField(null=True, blank=True, db_index=True)
    evidence = models.ImageField(upload_to='promotions/evidence/%Y/%m/', null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reported_promotions',
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.COMMUNITY, db_index=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PromotionQuerySet.as_manager()

    class Meta:
        ordering = ['-start_at', '-created_at']
        indexes = [
            models.Index(fields=['business', 'start_at', 'end_at']),
            models.Index(fields=['scope', 'start_at', 'end_at']),
            models.Index(fields=['is_verified', 'start_at']),
        ]

    def __str__(self):
        return f'{self.title} — {self.business.name}'

    def get_absolute_url(self):
        return reverse('promotions:detail', args=[self.pk])

    def clean(self):
        errors = {}
        if self.business_branch_id and self.business_id:
            if self.business_branch.canonical_business_id != self.business_id:
                errors['business_branch'] = 'The selected branch must belong to the selected business.'

        if self.end_at and self.start_at and self.end_at <= self.start_at:
            errors['end_at'] = 'End time must be after the start time.'

        if self.deal_type == self.DealType.PERCENT:
            if self.discount_value is None:
                errors['discount_value'] = 'Enter the percentage discount.'
            elif self.discount_value <= 0 or self.discount_value > 100:
                errors['discount_value'] = 'Percentage discounts must be greater than 0 and no more than 100.'
        elif self.deal_type == self.DealType.AMOUNT_OFF:
            if self.discount_value is None or self.discount_value <= 0:
                errors['discount_value'] = 'Enter a kina amount greater than 0.'
        elif self.deal_type == self.DealType.FIXED_PRICE:
            if self.special_price is None or self.special_price < 0:
                errors['special_price'] = 'Enter the advertised special price.'

        if errors:
            raise ValidationError(errors)

    @property
    def status(self):
        now = timezone.now()
        if self.start_at > now:
            return 'scheduled'
        if self.end_at and self.end_at < now:
            return 'expired'
        return 'active'

    @property
    def is_active(self):
        return self.status == 'active'

    @staticmethod
    def _format_number(value):
        if value is None:
            return ''
        value = Decimal(value)
        if value == value.to_integral():
            return str(int(value))
        return f'{value:.2f}'.rstrip('0').rstrip('.')

    @property
    def display_deal(self):
        if self.deal_type == self.DealType.PERCENT and self.discount_value is not None:
            return f'{self._format_number(self.discount_value)}% off'
        if self.deal_type == self.DealType.AMOUNT_OFF and self.discount_value is not None:
            return f'K{self.discount_value:,.2f} off'
        if self.deal_type == self.DealType.FIXED_PRICE and self.special_price is not None:
            return f'K{self.special_price:,.2f} special price'
        if self.deal_type == self.DealType.MULTIBUY:
            return 'Multi-buy offer'
        return 'Special offer'

    @property
    def scope_label(self):
        if self.scope == self.Scope.STOREWIDE:
            return 'Storewide'
        target = self.targets.select_related('product', 'category', 'subcategory').first()
        return target.label if target else self.get_scope_display()


class PromotionTarget(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='targets')
    product = models.ForeignKey(
        'core.Product',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='promotion_targets',
    )
    category = models.ForeignKey(
        'categories.Category',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='promotion_targets',
    )
    subcategory = models.ForeignKey(
        'categories.Subcategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='promotion_targets',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.promotion.title}: {self.label}'

    def clean(self):
        targets = [self.product_id, self.category_id, self.subcategory_id]
        if sum(bool(value) for value in targets) != 1:
            raise ValidationError('A promotion target must point to exactly one product, category, or subcategory.')

    @property
    def label(self):
        if self.product_id:
            return self.product.name
        if self.subcategory_id:
            return str(self.subcategory)
        if self.category_id:
            return self.category.name
        return 'Unknown target'

    @property
    def target_type(self):
        if self.product_id:
            return 'product'
        if self.subcategory_id:
            return 'subcategory'
        if self.category_id:
            return 'category'
        return None


class PromotionConfirmation(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='confirmations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promotion_confirmations')
    is_still_active = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['promotion', 'user'],
                name='unique_promotion_confirmation_per_user',
            )
        ]
        ordering = ['-updated_at']

    def __str__(self):
        state = 'active' if self.is_still_active else 'ended'
        return f'{self.user} says {self.promotion} is {state}'
