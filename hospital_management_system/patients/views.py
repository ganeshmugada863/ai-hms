from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import PatientProfileForm
from .models import PatientProfile
from appointments.models import Appointment

@login_required
def create_patient_profile(request):
    # Ensure profile exists using get_or_create
    profile, created = PatientProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = PatientProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            user = request.user
            user.email = form.cleaned_data['email']
            user.phone = form.cleaned_data['phone']
            if 'profile_image' in request.FILES:
                user.profile_image = request.FILES['profile_image']
            user.save()

            patient = form.save(commit=False)
            patient.user = user
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

@login_required
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