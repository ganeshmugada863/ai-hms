# appointment_recommender.py
from datetime import datetime, timedelta

def recommend_slots(doctor):
    """
    Simulates finding available slots for a doctor.
    In a real app, this would query the Appointment model for occupied slots.
    """
    now = datetime.now()
    recommendations = []
    
    # Simple logic: suggest 3 slots for tomorrow
    tomorrow = now + timedelta(days=1)
    base_times = ["09:00", "11:30", "14:00", "16:30"]
    
    for time_str in base_times:
        recommendations.append({
            "date": tomorrow.strftime("%Y-%m-%d"),
            "time": time_str,
            "doctor_name": doctor.user.username
        })
        
    return recommendations[:3]