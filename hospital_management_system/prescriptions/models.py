from django.db import models

# Create your models here.
from django.db import models
from patients.models import PatientProfile
from doctors.models import DoctorProfile
from appointments.models import Appointment

class Prescription(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE)

    diagnosis = models.TextField()
    medicines = models.TextField()
    dosage_instructions = models.TextField()

    prescribed_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prescription for {self.patient.user.username}"