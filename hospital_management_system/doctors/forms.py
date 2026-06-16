from django import forms
from .models import DoctorProfile

class DoctorProfileForm(forms.ModelForm):
    SPECIALIZATION_CHOICES = [
        ('Cardiology', 'Cardiology'), ('Neurology', 'Neurology'), 
        ('Pediatrics', 'Pediatrics'), ('Orthopedics', 'Orthopedics'),
        ('Dermatology', 'Dermatology'), ('General Medicine', 'General Medicine'),
    ]
    DAYS_CHOICES = [
        ('Mon-Fri', 'Mon-Fri'), ('Mon-Sat', 'Mon-Sat'), ('Weekends', 'Weekends'),
    ]
    
    specialization = forms.ChoiceField(choices=SPECIALIZATION_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    available_days = forms.ChoiceField(choices=DAYS_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    # User model fields to support edit profile actions
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    profile_image = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))

    class Meta:
        model = DoctorProfile
        fields = [
            'department',
            'specialization',
            'qualification',
            'experience',
            'consultation_fee',
            'available_days',
        ]
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'qualification': forms.TextInput(attrs={'class': 'form-control'}),
            'experience': forms.NumberInput(attrs={'class': 'form-control'}),
            'consultation_fee': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].required = True
        self.fields['department'].empty_label = "Select Department"
        if self.instance and hasattr(self.instance, 'user') and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
            self.fields['phone'].initial = self.instance.user.phone