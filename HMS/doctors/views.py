from django.shortcuts import render, redirect
from .forms import DoctorProfileForm

def create_doctor_profile(request):
    # Check if a profile already exists for the user to avoid IntegrityError on update
    profile = request.user.doctorprofile if hasattr(request.user, 'doctorprofile') else None

    if request.method == 'POST':
        form = DoctorProfileForm(request.POST, instance=profile)
        if form.is_valid():
            doctor = form.save(commit=False)
            doctor.user = request.user
            doctor.save()
            return redirect('/doctor-dashboard/')
    else:
        form = DoctorProfileForm(instance=profile)

    return render(request, 'doctors/D_profile.html', {'form': form, 'profile': profile})