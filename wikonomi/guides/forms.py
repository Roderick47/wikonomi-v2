from django import forms

from .models import Guide


GUIDE_INPUT_CLASS = 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-purple/50 focus:border-brand-blue sm:text-sm'
GUIDE_TEXTAREA_CLASS = f'{GUIDE_INPUT_CLASS} min-h-[110px]'


class GuideForm(forms.ModelForm):
    organization_name = forms.CharField(
        label='Business or organization',
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'organization_search',
            'list': 'organization_list',
            'class': GUIDE_INPUT_CLASS,
            'placeholder': 'Type a business or organization name...',
        }),
    )
    category_name = forms.CharField(
        label='Category',
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'category_search',
            'list': 'category_list',
            'class': GUIDE_INPUT_CLASS,
            'placeholder': 'Type a category name...',
        }),
    )

    class Meta:
        model = Guide
        fields = ['title', 'organization_name', 'category_name', 'summary']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': GUIDE_INPUT_CLASS,
                'placeholder': 'e.g. How to compare school supply prices',
            }),
            'summary': forms.Textarea(attrs={
                'rows': 4,
                'class': GUIDE_TEXTAREA_CLASS,
                'placeholder': 'Briefly explain what this guide helps people do.',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.organization:
                self.fields['organization_name'].initial = self.instance.organization.name
            if self.instance.category:
                self.fields['category_name'].initial = self.instance.category.name


class GuideForkForm(forms.ModelForm):
    class Meta:
        model = Guide
        fields = ['organization']
