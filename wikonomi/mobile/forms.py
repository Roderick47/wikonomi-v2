import uuid
from datetime import timedelta

from django import forms
from django.utils import timezone

from core.models import BusinessBranch, Product
from .models import MobileSubmission


class MobileSubmissionForm(forms.ModelForm):
    client_submission_id = forms.UUIDField(widget=forms.HiddenInput)
    observed_at = forms.DateTimeField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = MobileSubmission
        fields = (
            "product", "business_branch", "price", "photo",
            "client_submission_id", "observed_at",
        )
        widgets = {
            "product": forms.HiddenInput(),
            "business_branch": forms.HiddenInput(),
            "price": forms.NumberInput(attrs={
                "min": "0.01", "step": "0.01", "inputmode": "decimal",
                "placeholder": "e.g. 8.50", "autocomplete": "off",
            }),
            "photo": forms.FileInput(attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "capture": "environment",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.all()
        self.fields["business_branch"].queryset = (
            BusinessBranch.objects.filter(is_active=True)
        )
        self.fields["photo"].required = True
        self.fields["client_submission_id"].initial = uuid.uuid4()

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price <= 0:
            raise forms.ValidationError("Price must be greater than zero.")
        return price

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        if photo.size > 8 * 1024 * 1024:
            raise forms.ValidationError("Photo must be smaller than 8 MB.")
        if photo.content_type not in (
            "image/jpeg", "image/png", "image/webp"
        ):
            raise forms.ValidationError("Choose a JPEG, PNG or WebP image.")
        return photo

    def clean_observed_at(self):
        observed = self.cleaned_data.get("observed_at") or timezone.now()
        now = timezone.now()
        if observed > now + timedelta(minutes=5):
            raise forms.ValidationError("Photo date cannot be in the future.")
        if observed < now - timedelta(days=30):
            raise forms.ValidationError("Please upload a price seen within 30 days.")
        return observed
