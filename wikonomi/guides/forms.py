from django import forms

from .models import Guide


class GuideForm(forms.ModelForm):
    class Meta:
        model = Guide
        fields = ['title', 'organization', 'category', 'summary']
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 4}),
        }


class GuideForkForm(forms.ModelForm):
    class Meta:
        model = Guide
        fields = ['organization']
