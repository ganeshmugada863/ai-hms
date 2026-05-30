from django import forms
from .models import WebCollectedData

class DatasetUploadForm(forms.Form):
    CATEGORY_CHOICES = (
        ('symptom', 'Symptom Dataset'),
        ('disease', 'Disease Dataset'),
        ('medicine', 'Medicine Dataset'),
        ('conversation', 'Conversation Dataset'),
    )
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv'}))

class WebCollectedDataVerifyForm(forms.ModelForm):
    class Meta:
        model = WebCollectedData
        fields = ['category', 'is_verified', 'is_rejected']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_rejected': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional verification notes...'}),
        required=False
    )

class ChatMessageForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder': 'Describe your symptoms...', 'rows': 2, 'class': 'form-control'}),
        max_length=1000
    )
