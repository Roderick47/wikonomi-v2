from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from categories.models import Category, Subcategory
from core.models import Business, BusinessBranch, Product

from .models import Promotion, PromotionTarget


FIELD_CLASS = (
    'block w-full rounded-xl border border-gray-300 bg-white px-3 py-2.5 '
    'text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 '
    'focus:ring-brand-purple/20'
)


class PromotionForm(forms.ModelForm):
    class Duration(forms.TextChoices):
        TODAY = 'today', 'Today only'
        THREE_DAYS = '3', '3 days'
        ONE_WEEK = '7', '1 week'
        TWO_WEEKS = '14', '2 weeks'
        ONE_MONTH = '30', '1 month'
        CUSTOM = 'custom', 'Custom end date'
        UNKNOWN = 'unknown', "I don't know — assume 7 days"

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
            'business',
            'business_branch',
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
            'business': forms.Select(attrs={'class': FIELD_CLASS, 'data-promotion-business': ''}),
            'business_branch': forms.Select(attrs={'class': FIELD_CLASS}),
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
        self.fields['business'].queryset = Business.objects.order_by('name')
        self.fields['business_branch'].queryset = BusinessBranch.objects.select_related(
            'canonical_business'
        ).filter(is_active=True).order_by('canonical_business__name', 'name')
        self.fields['start_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_at'].input_formats = ['%Y-%m-%dT%H:%M']

        if not self.is_bound and not self.initial.get('start_at'):
            self.initial['start_at'] = timezone.localtime().strftime('%Y-%m-%dT%H:%M')

        business_id = self.data.get('business') or self.initial.get('business')
        if business_id:
            try:
                business_id = int(getattr(business_id, 'pk', business_id))
                self.fields['business_branch'].queryset = self.fields['business_branch'].queryset.filter(
                    canonical_business_id=business_id
                )
            except (TypeError, ValueError):
                pass

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
        start_at = cleaned.get('start_at') or timezone.now()
        business = cleaned.get('business')
        branch = cleaned.get('business_branch')

        if branch and business and branch.canonical_business_id != business.id:
            self.add_error('business_branch', 'Choose a branch belonging to this store.')

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
                local_start = timezone.localtime(start_at)
                local_end = local_start.replace(hour=23, minute=59, second=59, microsecond=0)
                cleaned['end_at'] = local_end
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
