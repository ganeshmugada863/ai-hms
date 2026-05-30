from django import forms
from .models import Prescription

class PrescriptionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        if doctor:
            from appointments.models import Appointment
            from patients.models import PatientProfile
            self.fields['appointment'].queryset = Appointment.objects.filter(doctor=doctor)
            patient_ids = Appointment.objects.filter(doctor=doctor).values_list('patient_id', flat=True).distinct()
            self.fields['patient'].queryset = PatientProfile.objects.filter(id__in=patient_ids)

    class Meta:
        model = Prescription
        fields = [
            'patient',
            'appointment',
            'diagnosis',
            'medicines',
            'dosage_instructions',
        ]