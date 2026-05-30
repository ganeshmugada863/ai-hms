from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserRegistrationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = [
            'username',
            'email',
            'role',
            'phone',
            'profile_image',
            'password1',
            'password2'
        ]

        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }