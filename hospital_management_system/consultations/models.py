from django.db import models
from patients.models import PatientProfile
from doctors.models import DoctorProfile

class Consultation(models.Model):
    CONSULTATION_TYPE_CHOICES = [
        ('video', 'Video Call'),
        ('audio', 'Audio Call'),
        ('chat', 'Chat'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='consultations')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='consultations')
    
    consultation_type = models.CharField(max_length=20, choices=CONSULTATION_TYPE_CHOICES, default='video')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    scheduled_date = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient.user.username} - {self.doctor.user.username} ({self.consultation_type})"

def get_secure_upload_path(instance, filename):
    # secure path format: uploads/patient_{id}/doctor_{id}/file_name
    return f"uploads/patient_{instance.patient.id}/doctor_{instance.doctor.id}/{filename}"

class ConsultationMedia(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True, related_name='media_files')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='uploaded_media')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='received_media')
    file = models.FileField(upload_to=get_secure_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Media {self.file.name} for patient {self.patient.user.username}"

class ConsultationCallLog(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='call_logs')
    duration_seconds = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    connection_quality = models.CharField(max_length=50, blank=True, default='Good')
    camera_used = models.BooleanField(default=False)
    mic_used = models.BooleanField(default=False)
    screen_share_used = models.BooleanField(default=False)

    def __str__(self):
        return f"CallLog for {self.consultation} ({self.duration_seconds}s)"
