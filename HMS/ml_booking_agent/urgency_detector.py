# urgency_detector.py

def detect_urgency(symptoms_text):
    """
    Detects if the situation is an emergency or high priority.
    """
    critical_keywords = [
        'heart attack', 'stroke', 'bleeding', 'unconscious', 
        'poison', 'suicide', 'breathing difficulty', 'severe chest pain'
    ]
    
    symptoms_text = symptoms_text.lower()
    is_emergency = any(kw in symptoms_text for kw in critical_keywords)
    
    priority = "Normal"
    if is_emergency:
        priority = "Critical"
    elif len(symptoms_text.split()) > 20: # Detailed descriptions might imply concern
        priority = "High"
        
    return {
        "priority": priority,
        "is_emergency": is_emergency,
        "action_required": "Emergency Room" if is_emergency else "Standard Appointment"
    }