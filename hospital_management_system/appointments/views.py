from django.shortcuts import render, redirect, get_object_or_404
from authentication.decorators import doctor_required
from .forms import AppointmentForm, DoctorAppointmentForm, DoctorAppointmentEditForm
from .models import Appointment
from patients.models import PatientProfile


def book_appointment(request):
    # Ensure patient profile exists
    patient, created = PatientProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = patient
            appointment.save()
            
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

    return render(request, 'appointments/appointment_list.html', {
        'appointments': appointments,
        'is_doctor': is_doctor,
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
            return redirect('/doctor-dashboard/')
    else:
        form = DoctorAppointmentForm()

    return render(request, 'appointments/doctor_add_appointment.html', {
        'form': form,
    })


def edit_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    if request.method == 'POST':
        form = DoctorAppointmentEditForm(request.POST, instance=appointment)
        if form.is_valid():
            form.save()
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
        
        # Trigger status change notification to Patient
        from reminders.notifications_utils import send_status_change_notification
        send_status_change_notification(appointment, 'Completed')
    return redirect('/patients/create-profile/')


@doctor_required
def update_appointment_status(request, appointment_id, status):
    appointment = Appointment.objects.get(id=appointment_id)
    appointment.status = status
    appointment.save()

    # Trigger status change notification to Patient
    from reminders.notifications_utils import send_status_change_notification
    send_status_change_notification(appointment, status)

    return redirect('/doctor-dashboard/')

@doctor_required
def manage_appointments(request):
    doctor = getattr(request.user, 'doctorprofile', None)
    appointments = Appointment.objects.filter(doctor=doctor).order_by('-created_at')
    return render(request, 'appointments/manage_appointments.html', {
        'appointments': appointments
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
    
    return render(request, 'appointments/appointment_detail.html', {
        'appointment': appointment,
        'prescriptions': prescriptions,
        'medical_records': medical_records,
        'is_doctor': is_doctor,
        'is_patient': is_patient,
    })
