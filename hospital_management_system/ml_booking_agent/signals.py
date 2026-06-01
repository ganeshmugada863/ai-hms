import threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from patients.models import PatientProfile
from prescriptions.models import Prescription

# Thread-safe lock and flag to prevent multiple parallel overlapping training sessions
_training_lock = threading.Lock()
_is_training = False

def run_background_training():
    print("[ML Signals] Background training request received. Skipping dynamic retrain as ModelTrainer handles pipeline asynchronously via AutoRetrainer.")

@receiver(post_save, sender=PatientProfile)
def patient_profile_saved(sender, instance, created, **kwargs):
    print(f"[ML Signals] Patient profile saved for: {instance.user.username}. Triggering background ML training.")
    training_thread = threading.Thread(target=run_background_training, name="MlRetrainingThread")
    training_thread.daemon = True
    training_thread.start()

@receiver(post_save, sender=Prescription)
def prescription_saved(sender, instance, created, **kwargs):
    print(f"[ML Signals] Prescription saved for patient: {instance.patient.user.username}. Triggering background ML training.")
    training_thread = threading.Thread(target=run_background_training, name="MlRetrainingThread")
    training_thread.daemon = True
    training_thread.start()
