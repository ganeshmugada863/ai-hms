from django.shortcuts import redirect

def doctor_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'doctor':
            return redirect('/auth/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


def patient_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'patient':
            return redirect('/auth/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'admin':
            return redirect('/auth/login/')
        return view_func(request, *args, **kwargs)
    return wrapper