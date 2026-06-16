from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    phone = models.CharField(max_length=15, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return self.username

# Automatically create associated profiles (Doctor or Patient) upon CustomUser creation
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == 'doctor':
            from doctors.models import DoctorProfile
            if not hasattr(instance, 'doctorprofile'):
                from departments.models import Department
                default_dept = Department.objects.filter(name__iexact="General Physician").first() or Department.objects.first()
                DoctorProfile.objects.create(
                    user=instance,
                    department=default_dept,
                    specialization="General Physician",
                    qualification="MBBS",
                    experience=1,
                    consultation_fee=500.00,
                    available_days="Mon-Fri",
                    is_approved=False
                )
        elif instance.role == 'patient':
            from patients.models import PatientProfile
            if not hasattr(instance, 'patientprofile'):
                PatientProfile.objects.create(
                    user=instance,
                    medical_history="No history recorded"
                )