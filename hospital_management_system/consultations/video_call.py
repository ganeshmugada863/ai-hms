# video_call.py
# Video consultation helper functions

def start_video_call(patient, doctor):
    """Start a video call session between a patient and doctor."""
    return {
        'status': 'started',
        'type': 'video',
        'patient': patient,
        'doctor': doctor,
    }
