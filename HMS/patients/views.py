from django.shortcuts import render, redirect
from .forms import PatientProfileForm
from .models import PatientProfile
from appointments.models import Appointment

def create_patient_profile(request):
    # Check if a profile already exists for the user to avoid IntegrityError on update
    profile = request.user.patientprofile if hasattr(request.user, 'patientprofile') else None

    if request.method == 'POST':
        form = PatientProfileForm(request.POST, instance=profile)
        if form.is_valid():
            patient = form.save(commit=False)
            patient.user = request.user
            patient.save()
            return redirect('/patient-dashboard/')
    else:
        form = PatientProfileForm(instance=profile)

    is_doctor = hasattr(request.user, 'doctorprofile')
    return render(request, 'patients/p_profile.html', {
        'form': form,
        'profile': profile,
        'is_doctor': is_doctor,
    })

def doctor_patient_list(request):
    doctor = getattr(request.user, 'doctorprofile', None)
    if not doctor:
        if request.user.role == 'doctor':
            return redirect('/doctors/create-profile/')
        return redirect('/auth/login/')
    
    # Get patients who have booked appointments with this doctor
    # Use distinct to avoid duplicates if a patient has multiple appointments
    patient_ids = Appointment.objects.filter(doctor=doctor).values_list('patient_id', flat=True).distinct()
    patients = PatientProfile.objects.filter(id__in=patient_ids)
    
    return render(request, 'patients/patient_list.html', {
        'patients': patients,
    })