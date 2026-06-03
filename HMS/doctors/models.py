from django.db import models

# Create your models here.
from django.db import models
from authentication.models import CustomUser
from departments.models import Department

class DoctorProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    specialization = models.CharField(max_length=100)
    qualification = models.CharField(max_length=150)
    experience = models.IntegerField()
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2)
    available_days = models.CharField(max_length=200)

    doctor_id = models.CharField(max_length=10, unique=True, null=True, blank=True, db_index=True)
    reviews = models.IntegerField(default=0)
    rating = models.FloatField(default=4.5)
    is_online = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Dr. {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.doctor_id:
            import random
            while True:
                candidate = f"D{random.randint(100, 999)}"
                if not DoctorProfile.objects.filter(doctor_id=candidate).exists():
                    self.doctor_id = candidate
                    break
        super().save(*args, **kwargs)