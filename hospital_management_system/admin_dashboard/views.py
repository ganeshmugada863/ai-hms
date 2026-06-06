from django.shortcuts import render, redirect, get_object_or_404
from authentication.decorators import admin_required

# Create your views here.

from django.shortcuts import render
from doctors.models import DoctorProfile
from patients.models import PatientProfile
from appointments.models import Appointment
from appointments.forms import AdminAppointmentForm
from prescriptions.models import Prescription


from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from departments.models import Department
from medical_records.models import MedicalRecord


@admin_required
def admin_dashboard(request):
    q = request.GET.get('q', '').strip()

    # AI Ranking Logic for Best Doctor
    best_doctor = DoctorProfile.objects.annotate(
        appointment_count=Count('appointments'),
        completion_rate=Count('appointments', filter=Q(appointments__status='Completed'))
    ).order_by('-appointment_count', '-reviews').first()

    # ML System Insights (Simulated)
    ml_insights = {
        'efficiency_gain': '12%',
        'predicted_growth': '8%',
        'top_department': 'Cardiology'
    }

    # Monthly Trends (Simulated for Chart.js)
    monthly_data = Appointment.objects.annotate(month=TruncMonth('appointment_date')).values('month').annotate(count=Count('id')).order_by('month')
    labels = [d['month'].strftime('%b %Y') for d in monthly_data]
    data = [d['count'] for d in monthly_data]

    # If no data, provide defaults for demo
    if not labels:
        labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May']
        data = [10, 25, 45, 30, 60]

    # Search Logic
    search_doctors = None
    search_patients = None
    search_appointments = None
    if q:
        search_doctors = DoctorProfile.objects.filter(
            Q(user__username__icontains=q) |
            Q(specialization__icontains=q) |
            Q(doctor_id__icontains=q)
        )
        search_patients = PatientProfile.objects.filter(
            Q(user__username__icontains=q) |
            Q(patient_id__icontains=q)
        )
        search_appointments = Appointment.objects.filter(
            Q(appointment_id__icontains=q) |
            Q(doctor__user__username__icontains=q) |
            Q(patient__user__username__icontains=q) |
            Q(reason__icontains=q)
        ).order_by('-created_at')

    context = {
        'doctors_count': DoctorProfile.objects.count(),
        'patients_count': PatientProfile.objects.count(),
        'appointments_count': Appointment.objects.count(),
        'prescriptions_count': Prescription.objects.count(),
        'pending_appointments': Appointment.objects.filter(status='Pending').count(),
        'report_uploads': MedicalRecord.objects.count(),
        'departments_count': Department.objects.count(),
        'best_doctor': best_doctor,
        'ml_insights': ml_insights,
        'chart_labels': labels,
        'chart_data': data,
        
        # Additional data for charts
        'dept_usage': Department.objects.annotate(doc_count=Count('doctorprofile')),

        # Search parameters
        'search_query': q,
        'search_doctors': search_doctors,
        'search_patients': search_patients,
        'search_appointments': search_appointments,
    }

    return render(request, 'admin_dashboard/dashboard.html', context)


@admin_required
def admin_doctor_list(request):
    doctors = DoctorProfile.objects.all()
    return render(request, 'admin_dashboard/doctor_list.html', {'doctors': doctors})


@admin_required
def approve_doctor(request, doctor_id):
    doctor = DoctorProfile.objects.get(id=doctor_id)
    doctor.is_approved = True
    doctor.save()
    return redirect('admin_doctor_list')


@admin_required
def admin_patient_list(request):
    patients = PatientProfile.objects.all()
    return render(request, 'admin_dashboard/patient_list.html', {'patients': patients})


@admin_required
def admin_appointment_list(request):
    appointments = Appointment.objects.all().order_by('-created_at')
    return render(request, 'admin_dashboard/appointment_list.html', {'appointments': appointments})

@admin_required
def admin_book_appointment(request):
    if request.method == 'POST':
        form = AdminAppointmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_appointment_list')
    else:
        doctor_id = request.GET.get('doctor_id')
        initial = {}
        if doctor_id:
            initial['doctor'] = get_object_or_404(DoctorProfile, id=doctor_id)
        form = AdminAppointmentForm(initial=initial)
    
    return render(request, 'admin_dashboard/appointment_form.html', {
        'form': form,
        'title': 'Book New Appointment'
    })

@admin_required
def admin_edit_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    if request.method == 'POST':
        form = AdminAppointmentForm(request.POST, instance=appointment)
        if form.is_valid():
            form.save()
            return redirect('admin_appointment_list')
    else:
        form = AdminAppointmentForm(instance=appointment)
    
    return render(request, 'admin_dashboard/appointment_form.html', {
        'form': form,
        'title': 'Edit Appointment'
    })


@admin_required
def admin_prescription_list(request):
    prescriptions = Prescription.objects.all().order_by('-prescribed_date')
    return render(request, 'admin_dashboard/prescription_list.html', {'prescriptions': prescriptions})
