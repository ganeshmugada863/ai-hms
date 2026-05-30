from django import forms
from .models import PatientProfile

class PatientProfileForm(forms.ModelForm):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'), ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]
    GENDER_CHOICES = [
        ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')
    ]
    
    blood_group = forms.ChoiceField(choices=BLOOD_GROUP_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    gender = forms.ChoiceField(choices=GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = PatientProfile
        fields = [
            'age',
            'gender',
            'blood_group',
            'medical_history',
            'emergency_contact',
        ]
        widgets = {
            'medical_history': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'age': forms.NumberInput(attrs={'class': 'form-control'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control'}),
        }