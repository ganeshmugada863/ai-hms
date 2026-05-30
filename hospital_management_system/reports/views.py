from django.shortcuts import render
from .report_generator import generate_report
from .email_notifications import send_report_email
from .sms_notifications import send_report_sms

# Create your views here.


def analytics_view(request):
    report = generate_report({'user': request.user.id})
    return render(request, 'reports/analytics.html', {'report': report})
