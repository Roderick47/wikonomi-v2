from django import forms
from .models import CabDriver

class ProfileCompletionForm(forms.ModelForm):
    class Meta:
        model = CabDriver
        fields = ['profile_photo','vehicle_photo','bio','home_area']
        widgets = {'bio': forms.Textarea(attrs={'rows': 4, 'maxlength': 300})}
