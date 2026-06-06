from django.shortcuts import render
from .models import Department
from doctors.models import DoctorProfile
from django.db.models import Count, Q

# Create your views here.

def departments_list(request):
    departments = Department.objects.annotate(
        approved_count=Count('doctorprofile', filter=Q(doctorprofile__is_approved=True))
    )
    return render(request, 'departments/departments_list.html', {'departments': departments})

def department_doctors(request, dept_id):
    department = Department.objects.get(id=dept_id)
    doctors = DoctorProfile.objects.filter(department=department, is_approved=True)
    return render(request, 'departments/department_doctors.html', {
        'department': department,
        'doctors': doctors
    })
