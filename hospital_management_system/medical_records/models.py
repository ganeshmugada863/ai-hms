from django.db import models
from patients.models import PatientProfile
from doctors.models import DoctorProfile

class MedicalRecord(models.Model):
    FILE_TYPE_CHOICES = [
        ('report', 'Medical Report'),
        ('xray', 'X-Ray'),
        ('ultrasound', 'Ultrasound'),
        ('bloodtest', 'Blood Test'),
        ('prescription', 'Prescription'),
        ('image', 'Image'),
        ('other', 'Other'),
    ]

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='medical_records')
    uploaded_by_doctor = models.ForeignKey(DoctorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_records')
    
    report_name = models.CharField(max_length=255)
    from_info = models.CharField(max_length=255, help_text="Sender of the report")
    to_info = models.CharField(max_length=255, help_text="Recipient of the report")
    file_type = models.CharField(max_length=50, choices=FILE_TYPE_CHOICES, default='other')
    report_file = models.FileField(upload_to='medical_reports/')
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by_patient = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.report_name} - {self.patient.user.username}"
