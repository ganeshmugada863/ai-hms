from django.shortcuts import render, redirect, get_object_or_404
from authentication.decorators import doctor_required
from .forms import AppointmentForm, DoctorAppointmentForm, DoctorAppointmentEditForm
from .models import Appointment
from patients.models import PatientProfile
from django.http import JsonResponse
from django.utils import timezone
import datetime


def book_appointment(request):
    # Ensure patient profile exists
    patient, created = PatientProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = patient
            appointment.save()
            print(f"[AUDIT LOG] New Appointment booked (ID: {appointment.appointment_id}) for Patient {appointment.patient.user.username} with Doctor {appointment.doctor.user.username}")
            
            # Send notifications (DB, Email, SMS) to the doctor
            from reminders.notifications_utils import send_appointment_notifications
            send_appointment_notifications(appointment)
            
            return redirect('/patient-dashboard/')
    else:
        doctor_id = request.GET.get('doctor_id')
        initial = {}
        if doctor_id:
            from doctors.models import DoctorProfile
            initial['doctor'] = get_object_or_404(DoctorProfile, id=doctor_id)
        form = AppointmentForm(initial=initial)

    # Fetch doctor detail mapping
    from doctors.models import DoctorProfile
    import json
    doctors = DoctorProfile.objects.all()
    doctor_data_map = {
        d.id: {
            'fee': float(d.consultation_fee),
            'specialization': d.specialization,
            'available_days': d.available_days,
            'is_online': d.is_online
        } for d in doctors
    }

    return render(request, 'appointments/book_appointment.html', {
        'form': form,
        'doctor_data_json': json.dumps(doctor_data_map)
    })


def appointment_list(request):
    is_doctor = hasattr(request.user, 'doctorprofile')
    if is_doctor:
        appointments = Appointment.objects.filter(doctor=request.user.doctorprofile).order_by('-appointment_date', '-appointment_time')
    else:
        # If it's a patient, they should only see their own appointments (added security/UX)
        if hasattr(request.user, 'patientprofile'):
            appointments = Appointment.objects.filter(patient=request.user.patientprofile).order_by('-appointment_date', '-appointment_time')
        else:
            appointments = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')

    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    return render(request, 'appointments/appointment_list.html', {
        'appointments': appointments,
        'is_doctor': is_doctor,
        'tomorrow': tomorrow,
    })


def doctor_add_appointment(request):
    doctor = getattr(request.user, 'doctorprofile', None)
    if not doctor:
        return redirect('/doctor-dashboard/')

    if request.method == 'POST':
        form = DoctorAppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.doctor = doctor
            appointment.save()
            print(f"[AUDIT LOG] New Appointment created by Doctor (ID: {appointment.appointment_id}) for Patient {appointment.patient.user.username}")
            return redirect('/doctor-dashboard/')
    else:
        form = DoctorAppointmentForm()

    return render(request, 'appointments/doctor_add_appointment.html', {
        'form': form,
    })


def edit_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    # Check lock rule:
    # Edit is only allowed if current_date >= appointment.appointment_date - 1 day
    current_date = timezone.localdate()
    lock_limit = appointment.appointment_date - datetime.timedelta(days=1)
    if current_date < lock_limit:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_ACCEPT') == 'application/json':
            return JsonResponse({"success": False, "message": "Appointment editing is only allowed starting one day before the appointment date."}, status=400)
        from django.contrib import messages
        messages.error(request, "Appointment editing is only allowed starting one day before the appointment date.")
        return redirect('/doctor-dashboard/')

    if request.method == 'POST':
        form = DoctorAppointmentEditForm(request.POST, instance=appointment)
        if form.is_valid():
            form.save()
            print(f"[AUDIT LOG] Appointment ID {appointment.appointment_id} (DB ID: {appointment.id}) was successfully updated/rescheduled by User {request.user.username}")
            return redirect('/doctor-dashboard/')
    else:
        form = DoctorAppointmentEditForm(instance=appointment)

    return render(request, 'appointments/edit_appointment.html', {
        'form': form,
        'appointment': appointment,
    })


def complete_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = 'Completed'
    appointment.save()
    print(f"[AUDIT LOG] Appointment ID {appointment.appointment_id} marked as Completed by {request.user.username}")

    # Trigger status change notification to Patient
    from reminders.notifications_utils import send_status_change_notification
    send_status_change_notification(appointment, 'Completed')

    patient = appointment.patient
    note = f"Appointment completed on {appointment.appointment_date}."
    current_history = patient.medical_history or ''
    if note not in current_history:
        patient.medical_history = (current_history + '\n' + note).strip()
        patient.save()

    return redirect('/doctor-dashboard/')


def acknowledge_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    if request.method == 'POST' and appointment.patient.user == request.user:
        appointment.status = 'Completed'
        appointment.save()
        print(f"[AUDIT LOG] Appointment ID {appointment.appointment_id} marked as Completed via patient acknowledgement by {request.user.username}")
        
        # Trigger status change notification to Patient
        from reminders.notifications_utils import send_status_change_notification
        send_status_change_notification(appointment, 'Completed')
    return redirect('/patients/create-profile/')


@doctor_required
def update_appointment_status(request, appointment_id, status):
    appointment = Appointment.objects.get(id=appointment_id)
    appointment.status = status
    appointment.save()
    print(f"[AUDIT LOG] Appointment ID {appointment.appointment_id} status updated to '{status}' by Doctor {request.user.username}")

    # Trigger status change notification to Patient
    from reminders.notifications_utils import send_status_change_notification
    send_status_change_notification(appointment, status)

    return redirect('/doctor-dashboard/')

@doctor_required
def manage_appointments(request):
    doctor = getattr(request.user, 'doctorprofile', None)
    appointments = Appointment.objects.filter(doctor=doctor).order_by('-created_at')
    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    return render(request, 'appointments/manage_appointments.html', {
        'appointments': appointments,
        'tomorrow': tomorrow,
    })

def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check permissions: only doctor, patient or admin can view
    is_doctor = hasattr(request.user, 'doctorprofile') and appointment.doctor == request.user.doctorprofile
    is_patient = hasattr(request.user, 'patientprofile') and appointment.patient == request.user.patientprofile
    
    if not (is_doctor or is_patient or request.user.role == 'admin'):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You do not have permission to view this appointment.")
        
    from prescriptions.models import Prescription
    from medical_records.models import MedicalRecord
    
    # Fetch related prescriptions specifically for this appointment
    prescriptions = Prescription.objects.filter(appointment=appointment)
    
    # Fetch related medical records uploaded by this doctor for this patient
    medical_records = MedicalRecord.objects.filter(patient=appointment.patient, uploaded_by_doctor=appointment.doctor).order_by('-uploaded_at')
    
    print(f"[AUDIT LOG] Appointment ID {appointment.appointment_id} details viewed by {request.user.username}")

    tomorrow = timezone.localdate() + datetime.timedelta(days=1)

    return render(request, 'appointments/appointment_detail.html', {
        'appointment': appointment,
        'prescriptions': prescriptions,
        'medical_records': medical_records,
        'is_doctor': is_doctor,
        'is_patient': is_patient,
        'tomorrow': tomorrow,
    })

@doctor_required
def api_search_appointments(request):
    q = request.GET.get('q', '').strip()
    print(f"[AUDIT LOG] Doctor {request.user.username} (ID: {request.user.id}) initiated search for Appointment ID: '{q}'")
    
    if not q:
        return JsonResponse({"success": False, "message": "Search query is empty."}, status=400)
    
    if not (q.isdigit() and len(q) == 4):
        return JsonResponse({"success": False, "message": "Please enter a valid 4-digit Appointment ID."}, status=400)
    
    doctor = getattr(request.user, 'doctorprofile', None)
    if not doctor:
        return JsonResponse({"success": False, "message": "User does not have a doctor profile."}, status=403)
        
    try:
        appointment = Appointment.objects.get(doctor=doctor, appointment_id=int(q))
    except Appointment.DoesNotExist:
        return JsonResponse({"success": False, "message": "No matching appointment found for your patients."}, status=404)
        
    from prescriptions.models import Prescription
    from medical_records.models import MedicalRecord
    
    prescriptions = Prescription.objects.filter(appointment=appointment)
    medical_records = MedicalRecord.objects.filter(patient=appointment.patient, uploaded_by_doctor=appointment.doctor).order_by('-uploaded_at')
    
    prescription_list = []
    for p in prescriptions:
        prescription_list.append({
            "diagnosis": p.diagnosis,
            "medicines": p.medicines,
            "dosage_instructions": p.dosage_instructions,
            "prescribed_date": p.prescribed_date.strftime("%Y-%m-%d %H:%M")
        })
        
    records_list = []
    for mr in medical_records:
        records_list.append({
            "report_name": mr.report_name,
            "from_info": mr.from_info,
            "to_info": mr.to_info,
            "file_type": mr.get_file_type_display(),
            "report_file_url": mr.report_file.url if mr.report_file else "",
            "uploaded_at": mr.uploaded_at.strftime("%Y-%m-%d %H:%M")
        })
        
    patient = appointment.patient
    print(f"[AUDIT LOG] Doctor {request.user.username} viewed details of Appointment ID: {appointment.appointment_id} for Patient {patient.user.username}")
    
    data = {
        "success": True,
        "appointment": {
            "id": appointment.id,
            "appointment_id": appointment.appointment_id,
            "appointment_date": appointment.appointment_date.strftime("%Y-%m-%d"),
            "appointment_time": appointment.appointment_time.strftime("%H:%M"),
            "reason": appointment.reason,
            "disease": appointment.disease,
            "consultation_type": appointment.get_consultation_type_display(),
            "status": appointment.status,
            "is_emergency": appointment.is_emergency,
        },
        "patient": {
            "username": patient.user.username,
            "full_name": patient.user.get_full_name() or patient.user.username,
            "email": patient.user.email,
            "age": patient.age,
            "gender": patient.gender,
            "blood_group": patient.blood_group,
            "medical_history": patient.medical_history,
            "emergency_contact": patient.emergency_contact
        },
        "prescriptions": prescription_list,
        "medical_records": records_list
    }
    return JsonResponse(data)
