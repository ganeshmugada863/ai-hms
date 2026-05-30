from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
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

@login_required
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    next_url = request.META.get('HTTP_REFERER', '/patient-dashboard/')
    return redirect(next_url)