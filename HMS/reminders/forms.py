from django import forms
from .models import Reminder

class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = [
            'reminder_title',
            'reminder_type',
            'reminder_date',
            'reminder_time',
        ]
        widgets = {
            'reminder_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'reminder_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
        }