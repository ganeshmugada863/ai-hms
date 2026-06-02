from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email Address")

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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            if CustomUser.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError("A user with this email address already exists.")
        return email