from django.core.cache import cache
from .models import Notification
from appointments.models import Appointment
from django.db.models import Q


def notifications_processor(request):
    if not request.user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'unread_notifications': [],
            'recent_notifications': [],
            'has_upcoming_telehealth': False,
        }

    user_id = request.user.id
    cache_key = f'notifications_ctx_{user_id}'

    # Try to get cached result first (30 second cache per user)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Single DB query for last 10 notifications
    all_notifications = list(
        Notification.objects.filter(user=request.user)
        .order_by('-created_at')
        .select_related('user')[:10]
    )
    unread_notifications = [n for n in all_notifications if not n.is_read]
    unread_count = len(unread_notifications)

    # Telehealth check — only if needed
    has_upcoming_telehealth = False
    q_filter = Q(
        consultation_type__in=['video', 'audio'],
        status__in=['Approved', 'Pending', 'Scheduled']
    )
    if hasattr(request.user, 'doctorprofile'):
        has_upcoming_telehealth = Appointment.objects.filter(
            q_filter, doctor=request.user.doctorprofile
        ).exists()
    elif hasattr(request.user, 'patientprofile'):
        has_upcoming_telehealth = Appointment.objects.filter(
            q_filter, patient=request.user.patientprofile
        ).exists()

    result = {
        'unread_notifications_count': unread_count,
        'unread_notifications': unread_notifications,
        'recent_notifications': all_notifications,
        'has_upcoming_telehealth': has_upcoming_telehealth,
    }

    # Cache for 30 seconds to avoid repeated DB hits on rapid navigation
    cache.set(cache_key, result, 30)

    return result
