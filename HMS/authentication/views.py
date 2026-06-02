from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserRegistrationForm


def role_based_redirect(user):
    if user.role == 'doctor':
        if hasattr(user, 'doctorprofile'):
            return redirect('/doctor-dashboard/')
        return redirect('/doctors/create-profile/')
    elif user.role == 'patient':
        if hasattr(user, 'patientprofile'):
            return redirect('/patient-dashboard/')
        return redirect('/patients/create-profile/')
    elif user.role == 'admin':
        return redirect('/admin-dashboard/')
    return redirect('/auth/login/')


def register_view(request):
    if request.method == 'POST':
        form = CustomUserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='authentication.backends.EmailOrUsernameBackend')
            return role_based_redirect(user)
    else:
        form = CustomUserRegistrationForm()

    return render(request, 'authentication/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return role_based_redirect(user)
    else:
        form = AuthenticationForm()

    return render(request, 'authentication/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')