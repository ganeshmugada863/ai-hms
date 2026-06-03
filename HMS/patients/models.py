from django.db import models

# Create your models here.
from django.db import models
from authentication.models import CustomUser

class PatientProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)

    patient_id = models.CharField(max_length=10, unique=True, null=True, blank=True, db_index=True)
    age = models.IntegerField(default=0)
    gender = models.CharField(max_length=20, blank=True, null=True, default='Not Specified')
    blood_group = models.CharField(max_length=10, blank=True, null=True, default='N/A')
    medical_history = models.TextField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=15, blank=True, null=True, default='N/A')

    def __str__(self):
        return self.user.username

    def save(self, *args, **kwargs):
        if not self.patient_id:
            import random
            while True:
                candidate = f"P{random.randint(100, 999)}"
                if not PatientProfile.objects.filter(patient_id=candidate).exists():
                    self.patient_id = candidate
                    break
        super().save(*args, **kwargs)