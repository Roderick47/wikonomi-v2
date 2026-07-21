from django import forms

from .models import CabDriver

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


class ProfileCompletionForm(forms.ModelForm):
    class Meta:
        model = CabDriver
        fields = ['profile_photo', 'vehicle_photo', 'bio', 'home_area']
        widgets = {
            'profile_photo': forms.ClearableFileInput(attrs={
                'accept': 'image/jpeg,image/png,image/webp',
                'data-max-file-size': str(MAX_UPLOAD_SIZE_BYTES),
                'data-allowed-types': 'image/jpeg,image/png,image/webp',
                'data-validation-label': 'Profile photo',
            }),
            'vehicle_photo': forms.ClearableFileInput(attrs={
                'accept': 'image/jpeg,image/png,image/webp',
                'data-max-file-size': str(MAX_UPLOAD_SIZE_BYTES),
                'data-allowed-types': 'image/jpeg,image/png,image/webp',
                'data-validation-label': 'Vehicle photo',
            }),
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'maxlength': 300,
                'placeholder': 'Tell riders how to recognise you and where you usually operate.',
            }),
            'home_area': forms.TextInput(attrs={
                'maxlength': 120,
                'placeholder': 'e.g. Waigani, Boroko, Gerehu',
            }),
        }
        help_texts = {
            'profile_photo': 'JPEG, PNG, or WebP. Max 5 MB.',
            'vehicle_photo': 'JPEG, PNG, or WebP. Max 5 MB.',
            'bio': 'Maximum 300 characters.',
        }

    def clean_bio(self):
        return (self.cleaned_data.get('bio') or '').strip()

    def clean_home_area(self):
        return (self.cleaned_data.get('home_area') or '').strip()

    def _clean_image(self, field_name):
        upload = self.cleaned_data.get(field_name)
        if not upload:
            return upload
        content_type = getattr(upload, 'content_type', '')
        if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise forms.ValidationError('Upload a JPEG, PNG, or WebP image.')
        if upload.size > MAX_UPLOAD_SIZE_BYTES:
            raise forms.ValidationError('Image must be 5 MB or smaller.')
        return upload

    def clean_profile_photo(self):
        return self._clean_image('profile_photo')

    def clean_vehicle_photo(self):
        return self._clean_image('vehicle_photo')
