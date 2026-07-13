from django import forms

from .models import Guide, GuideAnswer, GuideQuestion, StepTip


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
        fields = ['title', 'photo', 'organization_name', 'category_name', 'summary']
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
            'photo': forms.FileInput(attrs={
                'class': 'sr-only',
                'accept': 'image/jpeg,image/png,image/webp',
                'data-guide-photo-input': '',
            }),
        }

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and photo.size > 8 * 1024 * 1024:
            raise forms.ValidationError('Guide photos must be 8 MB or smaller.')
        return photo

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.organization:
                self.fields['organization_name'].initial = self.instance.organization.name
            if self.instance.category:
                self.fields['category_name'].initial = self.instance.category.name


class GuideForkForm(forms.Form):
    organization_name = forms.CharField(
        label='Business or organization',
        widget=forms.TextInput(attrs={
            'id': 'fork_organization_search',
            'list': 'fork_organization_list',
            'class': GUIDE_INPUT_CLASS,
            'placeholder': 'Start typing a business or organization...',
            'autocomplete': 'off',
        }),
    )


class StepTipForm(forms.ModelForm):
    photo = forms.ImageField(required=False)

    class Meta:
        model = StepTip
        fields = ['body']

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise forms.ValidationError('Tip text is required.')
        return body

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Tip images must be 5MB or smaller.')
        return photo


class GuideQuestionForm(forms.ModelForm):
    class Meta:
        model = GuideQuestion
        fields = ['body']

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise forms.ValidationError('Write a question before posting.')
        return body


class GuideAnswerForm(forms.ModelForm):
    class Meta:
        model = GuideAnswer
        fields = ['body']

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise forms.ValidationError('Write an answer before posting.')
        return body
