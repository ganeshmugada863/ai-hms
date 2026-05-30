import threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from patients.models import PatientProfile
from prescriptions.models import Prescription

# Thread-safe lock and flag to prevent multiple parallel overlapping training sessions
_training_lock = threading.Lock()
_is_training = False

def run_background_training():
    global _is_training
    with _training_lock:
        if _is_training:
            print("[ML Signals] Retraining already in progress. Skipping.")
            return
        _is_training = True
    
    try:
        print("[ML Signals] Initiating background medical model training...")
        from ml_booking_agent.train_bot import train_medical_model
        # Run training
        train_medical_model()
        print("[ML Signals] Background medical model training completed successfully.")
    except Exception as e:
        print(f"[ML Signals] Error in background training: {e}")
    finally:
        with _training_lock:
            _is_training = False

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
