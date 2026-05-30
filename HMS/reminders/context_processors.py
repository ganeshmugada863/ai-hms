from .models import Notification
from appointments.models import Appointment
from django.db.models import Q

def notifications_processor(request):
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
        all_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]
        
        # Check if the user has any scheduled/approved video/audio appointments
        is_doctor = hasattr(request.user, 'doctorprofile')
        is_patient = hasattr(request.user, 'patientprofile')
        q_filter = Q(consultation_type__in=['video', 'audio'], status__in=['Approved', 'Pending', 'Scheduled'])
        
        has_upcoming_telehealth = False
        if is_doctor:
            has_upcoming_telehealth = Appointment.objects.filter(q_filter, doctor=request.user.doctorprofile).exists()
        elif is_patient:
            has_upcoming_telehealth = Appointment.objects.filter(q_filter, patient=request.user.patientprofile).exists()
            
        return {
            'unread_notifications_count': unread_notifications.count(),
            'unread_notifications': unread_notifications,
            'recent_notifications': all_notifications,
            'has_upcoming_telehealth': has_upcoming_telehealth,
        }
    return {
        'unread_notifications_count': 0,
        'unread_notifications': [],
        'recent_notifications': [],
        'has_upcoming_telehealth': False,
    }
