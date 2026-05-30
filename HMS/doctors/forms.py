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

    class Meta:
        model = DoctorProfile
        fields = [
            'specialization',
            'qualification',
            'experience',
            'consultation_fee',
            'available_days',
        ]
        widgets = {
            'qualification': forms.TextInput(attrs={'class': 'form-control'}),
            'experience': forms.NumberInput(attrs={'class': 'form-control'}),
            'consultation_fee': forms.NumberInput(attrs={'class': 'form-control'}),
        }