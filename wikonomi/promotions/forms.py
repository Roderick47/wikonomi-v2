from datetime import timedelta
from zoneinfo import ZoneInfo

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from categories.models import Category, Subcategory
from core.models import Business, BusinessBranch, Product

from .models import Promotion, PromotionTarget


FIELD_CLASS = (
    'block w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 '
    'text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 '
    'focus:ring-brand-purple/20'
)
PNG_TIME_ZONE = ZoneInfo('Pacific/Port_Moresby')


def _png_wall_time(value):
    """Interpret datetime-local form values as Papua New Guinea local time."""
    if value is None:
        return None
    if timezone.is_aware(value):
        value = value.replace(tzinfo=None)
    return timezone.make_aware(value, PNG_TIME_ZONE)


class PromotionForm(forms.ModelForm):
    class Duration(models.TextChoices):
        TODAY = 'today', 'Today only'
        THREE_DAYS = '3', '3 days'
        ONE_WEEK = '7', '1 week'
        TWO_WEEKS = '14', '2 weeks'
        ONE_MONTH = '30', '1 month'
        CUSTOM = 'custom', 'Custom end date'
        UNKNOWN = 'unknown', "I don't know — assume 7 days"

    business_name = forms.CharField(
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': FIELD_CLASS,
            'id': 'business_search',
            'list': 'business_list',
            'placeholder': 'Type a business name...',
            'autocomplete': 'off',
            'data-promotion-business': '',
        }),
        help_text='Select an existing business or type a new name to add it.',
    )
    branch_name = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': FIELD_CLASS,
            'id': 'branch_search',
            'list': 'branch_list',
            'placeholder': 'Type a branch or location...',
            'autocomplete': 'off',
            'data-promotion-branch': '',
        }),
        help_text='Select an existing branch or type a new branch/location to add it.',
    )
    duration = forms.ChoiceField(
        choices=Duration.choices,
        initial=Duration.ONE_WEEK,
        required=True,
        widget=forms.Select(attrs={'class': FIELD_CLASS, 'data-duration-select': ''}),
        help_text='Wikonomi will stop showing the promotion as active automatically.',
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label='Choose a category',
        widget=forms.Select(attrs={'class': FIELD_CLASS, 'data-promotion-category': ''}),
    )
    subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.select_related('category').all(),
        required=False,
        empty_label='Optional: narrow to a subcategory',
        widget=forms.Select(attrs={'class': FIELD_CLASS}),
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.order_by('name'),
        required=False,
        empty_label='Choose a product',
        widget=forms.Select(attrs={'class': FIELD_CLASS}),
    )

    class Meta:
        model = Promotion
        fields = [
            'title',
            'kind',
            'deal_type',
            'scope',
            'discount_value',
            'special_price',
            'description',
            'terms',
            'start_at',
            'end_at',
            'evidence',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': FIELD_CLASS,
                'placeholder': 'e.g. Easter Sale, Weekend Special',
            }),
            'kind': forms.Select(attrs={'class': FIELD_CLASS}),
            'deal_type': forms.Select(attrs={'class': FIELD_CLASS, 'data-deal-type': ''}),
            'scope': forms.Select(attrs={'class': FIELD_CLASS, 'data-promotion-scope': ''}),
            'discount_value': forms.NumberInput(attrs={
                'class': FIELD_CLASS,
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'e.g. 20',
            }),
            'special_price': forms.NumberInput(attrs={
                'class': FIELD_CLASS,
                'step': '0.01',
                'min': '0',
                'placeholder': 'e.g. 6.95',
            }),
            'description': forms.Textarea(attrs={
                'class': FIELD_CLASS,
                'rows': 3,
                'placeholder': 'What did the sign, shelf label or advert say?',
            }),
            'terms': forms.Textarea(attrs={
                'class': FIELD_CLASS,
                'rows': 2,
                'placeholder': 'Optional exclusions or conditions',
            }),
            'start_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': FIELD_CLASS, 'type': 'datetime-local'},
            ),
            'end_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': FIELD_CLASS, 'type': 'datetime-local', 'data-custom-end': ''},
            ),
            'evidence': forms.FileInput(attrs={
                'class': FIELD_CLASS,
                'accept': 'image/jpeg,image/png,image/webp',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_at'].input_formats = ['%Y-%m-%dT%H:%M']

        if not self.is_bound and not self.initial.get('start_at'):
            self.initial['start_at'] = timezone.now().astimezone(PNG_TIME_ZONE).strftime('%Y-%m-%dT%H:%M')

        initial_business = self.initial.get('business')
        if not self.is_bound and initial_business and not self.initial.get('business_name'):
            try:
                business = initial_business if isinstance(initial_business, Business) else Business.objects.get(pk=initial_business)
            except (Business.DoesNotExist, TypeError, ValueError):
                business = None
            if business:
                self.initial['business_name'] = business.name

        initial_branch = self.initial.get('business_branch')
        if not self.is_bound and initial_branch and not self.initial.get('branch_name'):
            try:
                branch = (
                    initial_branch
                    if isinstance(initial_branch, BusinessBranch)
                    else BusinessBranch.objects.select_related('canonical_business').get(pk=initial_branch)
                )
            except (BusinessBranch.DoesNotExist, TypeError, ValueError):
                branch = None
            if branch:
                self.initial['branch_name'] = branch.name
                self.initial.setdefault('business_name', branch.canonical_business.name)

        category_id = self.data.get('category') or self.initial.get('category')
        if category_id:
            try:
                category_id = int(getattr(category_id, 'pk', category_id))
                self.fields['subcategory'].queryset = self.fields['subcategory'].queryset.filter(
                    category_id=category_id
                )
            except (TypeError, ValueError):
                pass

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get('scope')
        deal_type = cleaned.get('deal_type')
        duration = cleaned.get('duration')

        business_name = (cleaned.get('business_name') or '').strip()
        if not business_name:
            self.add_error('business_name', 'Enter the store or business where you saw this special.')
        cleaned['business_name'] = business_name
        cleaned['branch_name'] = (cleaned.get('branch_name') or '').strip()

        start_at = _png_wall_time(cleaned.get('start_at'))
        if start_at is None:
            start_at = timezone.now().astimezone(PNG_TIME_ZONE)
        cleaned['start_at'] = start_at

        if cleaned.get('end_at'):
            cleaned['end_at'] = _png_wall_time(cleaned['end_at'])

        if scope == Promotion.Scope.CATEGORY:
            if not cleaned.get('category') and not cleaned.get('subcategory'):
                raise ValidationError('Choose the category or subcategory this promotion applies to.')
        elif scope == Promotion.Scope.PRODUCT and not cleaned.get('product'):
            raise ValidationError('Choose the product this promotion applies to.')

        if deal_type in {Promotion.DealType.MULTIBUY, Promotion.DealType.OTHER}:
            if not (cleaned.get('description') or '').strip():
                self.add_error('description', 'Describe the offer so shoppers know what the deal is.')

        if duration != self.Duration.CUSTOM:
            if duration == self.Duration.TODAY:
                cleaned['end_at'] = start_at.replace(hour=23, minute=59, second=59, microsecond=0)
            else:
                days = 7 if duration == self.Duration.UNKNOWN else int(duration or 7)
                cleaned['end_at'] = start_at + timedelta(days=days)
        elif not cleaned.get('end_at'):
            self.add_error('end_at', 'Choose when this promotion ends.')

        end_at = cleaned.get('end_at')
        if end_at and start_at and end_at <= start_at:
            self.add_error('end_at', 'End time must be after the start time.')

        return cleaned

    def save(self, commit=True):
        promotion = super().save(commit=False)
        promotion.start_at = self.cleaned_data.get('start_at')
        promotion.end_at = self.cleaned_data.get('end_at')
        if commit:
            promotion.save()
            self.save_target(promotion)
        return promotion

    def save_target(self, promotion):
        promotion.targets.all().delete()
        if promotion.scope == Promotion.Scope.STOREWIDE:
            return

        if promotion.scope == Promotion.Scope.PRODUCT:
            PromotionTarget.objects.create(
                promotion=promotion,
                product=self.cleaned_data['product'],
            )
            return

        subcategory = self.cleaned_data.get('subcategory')
        if subcategory:
            PromotionTarget.objects.create(promotion=promotion, subcategory=subcategory)
        else:
            PromotionTarget.objects.create(
                promotion=promotion,
                category=self.cleaned_data['category'],
            )
