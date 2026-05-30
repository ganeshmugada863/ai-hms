from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from appointments.models import Appointment
from doctors.models import DoctorProfile
from .video_call import start_video_call
from .audio_call import start_audio_call
from .chat import process_chat_message

def index(request):
    """Consultations main page showing the three options."""
    active_doctors = DoctorProfile.objects.filter(is_online=True)
    
    appointments = []
    is_doctor = False
    is_patient = False
    if request.user.is_authenticated:
        is_doctor = hasattr(request.user, 'doctorprofile')
        is_patient = hasattr(request.user, 'patientprofile')
        q_filter = Q(status__in=['Approved', 'Pending', 'Scheduled'])
        if is_doctor:
            appointments = Appointment.objects.filter(q_filter, doctor=request.user.doctorprofile).order_by('appointment_date', 'appointment_time')
        elif is_patient:
            appointments = Appointment.objects.filter(q_filter, patient=request.user.patientprofile).order_by('appointment_date', 'appointment_time')
            
    return render(request, 'consultations/index.html', {
        'active_doctors': active_doctors,
        'appointments': appointments,
        'is_doctor': is_doctor,
        'is_patient': is_patient,
    })

def get_active_appointment(user, appointment_id=None):
    """Helper to find and validate an appointment for a video/audio call."""
    is_doctor = hasattr(user, 'doctorprofile')
    is_patient = hasattr(user, 'patientprofile')
    
    if not appointment_id:
        return None
        
    try:
        appointment = Appointment.objects.get(id=appointment_id)
        # Check permission
        if is_doctor and appointment.doctor == user.doctorprofile:
            return appointment
        if is_patient and appointment.patient == user.patientprofile:
            return appointment
    except Appointment.DoesNotExist:
        pass
    return None

def video_call_view(request):
    """Start video call - requires an approved/scheduled/pending appointment."""
    appointment_id = request.GET.get('appointment_id')
    appointment = get_active_appointment(request.user, appointment_id)
    
    if not appointment:
        messages.error(request, "Access Denied: Calls can only be joined through a booked and scheduled appointment page.")
        return redirect('consultations_index')
        
    is_doctor = hasattr(request.user, 'doctorprofile')
    is_patient = hasattr(request.user, 'patientprofile')
    
    if is_doctor:
        # Doctor starts the call -> set call_session_status to 'ringing'
        appointment.call_session_status = 'ringing'
        appointment.save()
    elif is_patient:
        # Patient can only enter if call is ringing or active
        if appointment.call_session_status not in ['ringing', 'active']:
            messages.error(request, "Access Denied: The doctor has not started the call yet.")
            return redirect('consultations_index')
        
        # If it was ringing and patient enters, set to active
        if appointment.call_session_status == 'ringing':
            appointment.call_session_status = 'active'
            appointment.save()
            
    result = start_video_call(appointment.patient.user, appointment.doctor.user)
    return render(request, 'consultations/video_call.html', {
        'result': result,
        'appointment': appointment,
        'is_doctor': is_doctor,
        'is_patient': is_patient,
    })

def audio_call_view(request):
    """Start audio call - requires an approved/scheduled/pending appointment."""
    appointment_id = request.GET.get('appointment_id')
    appointment = get_active_appointment(request.user, appointment_id)
    
    if not appointment:
        messages.error(request, "Access Denied: Calls can only be joined through a booked and scheduled appointment page.")
        return redirect('consultations_index')
        
    is_doctor = hasattr(request.user, 'doctorprofile')
    is_patient = hasattr(request.user, 'patientprofile')
    
    if is_doctor:
        # Doctor starts the call -> set call_session_status to 'ringing'
        appointment.call_session_status = 'ringing'
        appointment.save()
    elif is_patient:
        # Patient can only enter if call is ringing or active
        if appointment.call_session_status not in ['ringing', 'active']:
            messages.error(request, "Access Denied: The doctor has not started the call yet.")
            return redirect('consultations_index')
        
        # If it was ringing and patient enters, set to active
        if appointment.call_session_status == 'ringing':
            appointment.call_session_status = 'active'
            appointment.save()
            
    result = start_audio_call(appointment.patient.user, appointment.doctor.user)
    return render(request, 'consultations/audio_call.html', {
        'result': result,
        'appointment': appointment,
        'is_doctor': is_doctor,
        'is_patient': is_patient,
    })

def chat_view(request):
    """Start chat - requires an approved/scheduled/pending appointment."""
    appointment_id = request.GET.get('appointment_id')
    appointment = get_active_appointment(request.user, appointment_id)
    
    if not appointment:
        messages.error(request, "You do not have a valid scheduled/approved appointment to start a chat.")
        return redirect('consultations_index')
        
    result = process_chat_message(request.user, 'Hello')
    return render(request, 'consultations/chat.html', {
        'result': result,
        'appointment': appointment,
        'is_doctor': hasattr(request.user, 'doctorprofile'),
    })

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def check_incoming_call(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'patientprofile'):
        return JsonResponse({'incoming': False})
        
    appointment = Appointment.objects.filter(
        patient=request.user.patientprofile,
        call_session_status='ringing',
        status__in=['Approved', 'Pending', 'Scheduled']
    ).first()
    
    if appointment:
        return JsonResponse({
            'incoming': True,
            'appointment_id': appointment.id,
            'doctor_name': appointment.doctor.user.username,
            'call_type': appointment.consultation_type,
        })
        
    return JsonResponse({'incoming': False})

@csrf_exempt
def update_call_status(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Unauthenticated'}, status=401)
        
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        appointment_id = data.get('appointment_id')
        new_status = data.get('status')
        
        if not appointment_id or not new_status:
            return JsonResponse({'success': False, 'error': 'Missing fields'}, status=400)
            
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        is_doctor = hasattr(request.user, 'doctorprofile') and appointment.doctor == request.user.doctorprofile
        is_patient = hasattr(request.user, 'patientprofile') and appointment.patient == request.user.patientprofile
        
        if not (is_doctor or is_patient):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
            
        if new_status in ['idle', 'ringing', 'active', 'ended']:
            appointment.call_session_status = new_status
            appointment.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_call_status(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthenticated'}, status=401)
        
    appointment_id = request.GET.get('appointment_id')
    if not appointment_id:
        return JsonResponse({'error': 'Missing appointment_id'}, status=400)
        
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    is_doctor = hasattr(request.user, 'doctorprofile') and appointment.doctor == request.user.doctorprofile
    is_patient = hasattr(request.user, 'patientprofile') and appointment.patient == request.user.patientprofile
    
    if not (is_doctor or is_patient):
        return JsonResponse({'error': 'Permission denied'}, status=403)
        
    return JsonResponse({
        'status': appointment.call_session_status,
        'is_doctor': is_doctor,
    })

