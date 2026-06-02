from django.shortcuts import render
from authentication.decorators import patient_required
from django.db.models import Q
from appointments.models import Appointment
from prescriptions.models import Prescription
from medical_records.models import MedicalRecord
from patients.models import PatientProfile
import json
from django.utils import timezone
import datetime

@patient_required
def patient_dashboard(request):
    patient, created = PatientProfile.objects.get_or_create(user=request.user)
    search_query = request.GET.get('q', '')

    inactive_statuses = ['Completed', 'Cancelled', 'Finished', 'Consultation Done', 'Closed', 'Expired']
    tomorrow = timezone.localdate() + datetime.timedelta(days=1)

    if patient:
        upcoming_appointments = Appointment.objects.filter(patient=patient).exclude(status__in=inactive_statuses).order_by('appointment_date')
        active_appointments = Appointment.objects.filter(patient=patient).exclude(status__in=inactive_statuses)
        prescriptions = Prescription.objects.filter(patient=patient).order_by('-prescribed_date')
        medical_records = MedicalRecord.objects.filter(patient=patient).order_by('-uploaded_at')

        if search_query:
            upcoming_appointments = upcoming_appointments.filter(
                Q(doctor__user__username__icontains=search_query) |
                Q(reason__icontains=search_query) |
                Q(disease__icontains=search_query)
            )
            prescriptions = prescriptions.filter(
                Q(diagnosis__icontains=search_query) |
                Q(medicines__icontains=search_query) |
                Q(dosage_instructions__icontains=search_query)
            )
            medical_records = medical_records.filter(
                Q(report_name__icontains=search_query) |
                Q(from_info__icontains=search_query) |
                Q(to_info__icontains=search_query)
            )
        
        prescriptions_count = prescriptions.count()
        medical_records_count = medical_records.count()

        # Serialize active appointments for the calendar
        appointments_list = []
        for appt in active_appointments:
            doc_name = appt.doctor.user.username if appt.doctor else "Unknown"
            doc_image = appt.doctor.user.profile_image.url if appt.doctor and appt.doctor.user.profile_image else ""
            appointments_list.append({
                'id': appt.id,
                'doctor_name': doc_name,
                'doctor_image': doc_image,
                'date': appt.appointment_date.strftime('%Y-%m-%d'),
                'time': appt.appointment_time.strftime('%I:%M %p') if hasattr(appt.appointment_time, 'strftime') else str(appt.appointment_time),
                'status': appt.status,
                'appointment_id': appt.appointment_id,
            })
        appointments_json = json.dumps(appointments_list)
    else:
        upcoming_appointments = Appointment.objects.none()
        prescriptions_count = 0
        medical_records_count = 0
        appointments_json = json.dumps([])

    context = {
        'upcoming_appointments': upcoming_appointments[:5],
        'prescriptions_count': prescriptions_count,
        'medical_records_count': medical_records_count,
        'search_query': search_query,
        'appointments_json': appointments_json,
        'tomorrow': tomorrow,
    }

    return render(request, 'patient_dashboard/dashboard.html', context)