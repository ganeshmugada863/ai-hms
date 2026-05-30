from django.shortcuts import render
from .models import Department
from doctors.models import DoctorProfile

# Create your views here.

def departments_list(request):
    departments = Department.objects.all()
    return render(request, 'departments/departments_list.html', {'departments': departments})

def department_doctors(request, dept_id):
    department = Department.objects.get(id=dept_id)
    doctors = DoctorProfile.objects.filter(department=department)
    return render(request, 'departments/department_doctors.html', {
        'department': department,
        'doctors': doctors
    })
