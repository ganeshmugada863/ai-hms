from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import DoctorProfileForm

@login_required
def create_doctor_profile(request):
    # Check if a profile already exists for the user to avoid IntegrityError on update
    profile = request.user.doctorprofile if hasattr(request.user, 'doctorprofile') else None

    if request.method == 'POST':
        form = DoctorProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            user = request.user
            user.email = form.cleaned_data['email']
            user.phone = form.cleaned_data['phone']
            if 'profile_image' in request.FILES:
                user.profile_image = request.FILES['profile_image']
            user.save()

            doctor = form.save(commit=False)
            doctor.user = user
            doctor.save()
            return redirect('/doctor-dashboard/')
    else:
        form = DoctorProfileForm(instance=profile)

    return render(request, 'doctors/D_profile.html', {'form': form, 'profile': profile})