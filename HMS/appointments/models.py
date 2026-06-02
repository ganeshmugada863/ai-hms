from django.db import models

# Create your models here.
from django.db import models
from patients.models import PatientProfile
from doctors.models import DoctorProfile

class Appointment(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )

    appointment_id = models.IntegerField(unique=True, db_index=True, null=True, blank=True)

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='appointments'
    )

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='appointments'
    )

    appointment_date = models.DateField()
    appointment_time = models.TimeField()

    reason = models.TextField()
    disease = models.CharField(max_length=255, blank=True, null=True)

    CONSULTATION_TYPE_CHOICES = (
        ('video', 'Video Call'),
        ('audio', 'Audio Call'),
        ('discussion', 'Discussions & Suggestions'),
        ('in_person', 'In-Person Consultation'),
    )
    consultation_type = models.CharField(
        max_length=20,
        choices=CONSULTATION_TYPE_CHOICES,
        default='in_person'
    )

    is_emergency = models.BooleanField(default=False)

    call_session_status = models.CharField(
        max_length=20,
        choices=(
            ('idle', 'Idle'),
            ('ringing', 'Ringing'),
            ('active', 'Active'),
            ('ended', 'Ended'),
        ),
        default='idle'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.user.username} → Dr. {self.doctor.user.username}"

    def save(self, *args, **kwargs):
        import random
        if not self.appointment_id:
            while True:
                new_id = random.randint(1000, 9999)
                if not Appointment.objects.filter(appointment_id=new_id).exists():
                    self.appointment_id = new_id
                    break
        super().save(*args, **kwargs)