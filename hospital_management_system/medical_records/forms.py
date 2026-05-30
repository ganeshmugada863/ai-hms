from django import forms
from .models import MedicalRecord

class MedicalRecordForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        if doctor:
            from appointments.models import Appointment
            from patients.models import PatientProfile
            patient_ids = Appointment.objects.filter(doctor=doctor).values_list('patient_id', flat=True).distinct()
            self.fields['patient'].queryset = PatientProfile.objects.filter(id__in=patient_ids)

    class Meta:
        model = MedicalRecord
        fields = [
            'patient',
            'report_name',
            'from_info',
            'to_info',
            'file_type',
            'report_file',
        ]
        widgets = {
            'report_name': forms.TextInput(attrs={'placeholder': 'Enter report name', 'class': 'form-input'}),
            'from_info': forms.TextInput(attrs={'placeholder': 'Sender (e.g. Dr. Name, Lab)', 'class': 'form-input'}),
            'to_info': forms.TextInput(attrs={'placeholder': 'Recipient (e.g. Patient Name, Consultant)', 'class': 'form-input'}),
            'file_type': forms.Select(attrs={'class': 'form-input'}),
            'report_file': forms.FileInput(attrs={'accept': 'image/*,.pdf', 'class': 'form-input'}),
        }

class PatientMedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = [
            'report_name',
            'from_info',
            'to_info',
            'file_type',
            'report_file',
        ]
        widgets = {
            'report_name': forms.TextInput(attrs={'placeholder': 'Enter report name', 'class': 'form-input'}),
            'from_info': forms.TextInput(attrs={'placeholder': 'Sender (e.g. Lab, Self)', 'class': 'form-input'}),
            'to_info': forms.TextInput(attrs={'placeholder': 'Recipient (e.g. Dr. Name)', 'class': 'form-input'}),
            'file_type': forms.Select(attrs={'class': 'form-input'}),
            'report_file': forms.FileInput(attrs={'accept': 'image/*,.pdf', 'class': 'form-input'}),
        }
