# audio_call.py
# Audio consultation helper functions

def start_audio_call(patient, doctor):
    """Start an audio call session between a patient and doctor."""
    return {
        'status': 'started',
        'type': 'audio',
        'patient': patient,
        'doctor': doctor,
    }
