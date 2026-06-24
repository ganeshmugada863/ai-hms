from django.shortcuts import render, redirect, get_object_or_404
from authentication.decorators import patient_required
from .forms import ReminderForm
from .models import Reminder

@patient_required
def create_reminder(request):
    if request.method == 'POST':
        form = ReminderForm(request.POST)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.user = request.user
            reminder.save()
            return redirect('/patient-dashboard/')
    else:
        form = ReminderForm()

    reminders = Reminder.objects.filter(user=request.user)

    return render(request, 'reminders/reminder_dashboard.html', {
        'form': form,
        'reminders': reminders
    })

from django.contrib.auth.decorators import login_required
from .models import Notification
from django.http import JsonResponse

@login_required
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    next_url = request.META.get('HTTP_REFERER', '/patient-dashboard/')
    return redirect(next_url)

@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true':
        return JsonResponse({'status': 'success'})
    next_url = request.META.get('HTTP_REFERER', '/patient-dashboard/')
    return redirect(next_url)

@login_required
def delete_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true':
        return JsonResponse({'status': 'success'})
    next_url = request.META.get('HTTP_REFERER', '/reminders/notifications/')
    return redirect(next_url)

@login_required
def clear_all_notifications(request):
    Notification.objects.filter(user=request.user).delete()
    next_url = request.META.get('HTTP_REFERER', '/reminders/notifications/')
    return redirect(next_url)

@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'reminders/notifications_list.html', {
        'notifications': notifications
    })