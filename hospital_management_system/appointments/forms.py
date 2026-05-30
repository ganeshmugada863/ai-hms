from django import forms
from .models import Appointment

DATE_TIME_WIDGETS = {
    'appointment_date': forms.DateInput(
        attrs={
            'type': 'date',
            'class': 'form-input',
        }
    ),
    'appointment_time': forms.TimeInput(
        attrs={
            'type': 'time',
            'class': 'form-input',
            'step': '900',
        }
    ),
}

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'doctor',
            'appointment_date',
            'appointment_time',
            'consultation_type',
            'is_emergency',
            'reason',
            'disease',
        ]
        widgets = {
            **DATE_TIME_WIDGETS,
            'doctor': forms.Select(
                attrs={
                    'class': 'form-input',
                }
            ),
            'consultation_type': forms.Select(
                attrs={
                    'class': 'form-input',
                }
            ),
            'is_emergency': forms.CheckboxInput(
                attrs={
                    'class': 'form-checkbox',
                    'style': 'width: 20px !important; height: 20px !important; cursor: pointer;',
                }
            ),
            'disease': forms.TextInput(
                attrs={
                    'placeholder': 'Enter symptoms or disease name...',
                    'class': 'form-input',
                }
            ),
            'reason': forms.Textarea(
                attrs={
                    'placeholder': 'Brief details about the checkup reason...',
                    'rows': 4,
                    'class': 'form-input',
                }
            ),
        }

class DoctorAppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'patient',
            'appointment_date',
            'appointment_time',
            'reason',
            'disease',
        ]
        widgets = DATE_TIME_WIDGETS

class DoctorAppointmentEditForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'patient',
            'appointment_date',
            'appointment_time',
            'reason',
            'disease',
        ]
        widgets = DATE_TIME_WIDGETS

class AdminAppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'patient',
            'doctor',
            'appointment_date',
            'appointment_time',
            'reason',
            'disease',
            'status',
        ]
        widgets = DATE_TIME_WIDGETS
