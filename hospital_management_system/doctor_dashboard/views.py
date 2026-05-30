from django.shortcuts import render
from authentication.decorators import doctor_required

# Create your views here.
from django.shortcuts import render
from django.db.models import Q
from appointments.models import Appointment
from prescriptions.models import Prescription
from patients.models import PatientProfile


@doctor_required
def doctor_dashboard(request):
    doctor = request.user.doctorprofile if hasattr(request.user, 'doctorprofile') else None

    search_query = request.GET.get('search', '')
    patients = PatientProfile.objects.all()

    if search_query:
        patients = patients.filter(
            Q(user__username__icontains=search_query) |
            Q(medical_history__icontains=search_query)
        )

    import json
    if doctor:
        appointments = Appointment.objects.filter(doctor=doctor).order_by('-created_at')
        prescriptions_count = Prescription.objects.filter(doctor=doctor).count()
        
        # Serialize appointments list with patient details for the doctor calendar
        appointments_list = []
        for appt in Appointment.objects.filter(doctor=doctor):
            pat_name = appt.patient.user.username if appt.patient else "Unknown"
            pat_image = appt.patient.user.profile_image.url if appt.patient and appt.patient.user.profile_image else ""
            appointments_list.append({
                'id': appt.id,
                'patient_name': pat_name,
                'patient_image': pat_image,
                'date': appt.appointment_date.strftime('%Y-%m-%d'),
                'time': appt.appointment_time.strftime('%I:%M %p') if hasattr(appt.appointment_time, 'strftime') else str(appt.appointment_time),
                'status': appt.status,
            })
        appointments_json = json.dumps(appointments_list)
        appt_dates = [appt.appointment_date.strftime('%Y-%m-%d') for appt in appointments]
    else:
        appointments = Appointment.objects.none()
        prescriptions_count = 0
        appointments_json = json.dumps([])
        appt_dates = []
    
    # AI Urgency Alerts (Simulated)
    critical_cases = appointments.filter(Q(reason__icontains='severe') | Q(reason__icontains='emergency')).count()

    context = {
        'appointments_count': appointments.count(),
        'prescriptions_count': prescriptions_count,
        'appointments': appointments[:10],
        'patients': patients,
        'search_query': search_query,
        'appointments_json': appointments_json,
        'appt_dates_json': json.dumps(appt_dates),
        'critical_cases': critical_cases,
    }

    return render(request, 'doctor_dashboard/dashboard.html', context)
