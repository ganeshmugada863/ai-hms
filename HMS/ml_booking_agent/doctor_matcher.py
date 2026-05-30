# doctor_matcher.py
from doctors.models import DoctorProfile

def match_doctors(department_name, severity):
    """
    Match doctors based on department and patient severity.
    """
    # Find department based specialists
    doctors = DoctorProfile.objects.filter(
        department__name__icontains=department_name,
        is_approved=True
    )
    
    if not doctors.exists():
        # Fallback to General Medicine if specific dept not found
        doctors = DoctorProfile.objects.filter(
            department__name__icontains='General',
            is_approved=True
        )

    # Sort by experience if severity is high
    if severity == "High":
        doctors = doctors.order_by('-experience')
    else:
        doctors = doctors.order_by('-reviews')

    return doctors[:5] # Return top 5 matches