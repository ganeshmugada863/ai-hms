from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from authentication.decorators import doctor_required, patient_required
from .forms import PrescriptionForm
from .models import Prescription
from .pdf_generator import generate_prescription_pdf
from patients.models import PatientProfile

@doctor_required
def create_prescription(request):
    doctor = getattr(request.user, 'doctorprofile', None)
    if not doctor:
        if request.user.role == 'doctor':
            return redirect('/doctors/create-profile/')
        return redirect('/auth/login/')

    if request.method == 'POST':
        form = PrescriptionForm(request.POST, doctor=doctor)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.doctor = doctor
            prescription.save()
            
            # Send prescription notification to patient
            from reminders.notifications_utils import send_prescription_notification
            send_prescription_notification(prescription)
            
            return redirect('/doctor-dashboard/')
    else:
        initial = {}
        patient_id = request.GET.get('patient_id')
        appointment_id = request.GET.get('appointment_id')
        if patient_id:
            initial['patient'] = patient_id
        if appointment_id:
            initial['appointment'] = appointment_id
        form = PrescriptionForm(initial=initial, doctor=doctor)

    return render(request, 'prescriptions/create_prescription.html', {
        'form': form
    })

@patient_required
def view_prescriptions(request):
    """View all prescriptions for patient"""
    patient, created = PatientProfile.objects.get_or_create(user=request.user)
        
    prescriptions = Prescription.objects.filter(patient=patient).order_by('-prescribed_date')
    
    return render(request, 'prescriptions/view_prescriptions.html', {
        'prescriptions': prescriptions,
        'patient': patient,
    })

@doctor_required
def list_prescriptions(request):
    """View all prescriptions (Doctor side)"""
    doctor = getattr(request.user, 'doctorprofile', None)
    if not doctor:
        if request.user.role == 'doctor':
            return redirect('/doctors/create-profile/')
        return redirect('/doctor-dashboard/')
        
    prescriptions = Prescription.objects.filter(doctor=doctor).order_by('-prescribed_date')
    return render(request, 'prescriptions/prescription_list.html', {
        'prescriptions': prescriptions
    })

@doctor_required
def edit_prescription(request, prescription_id):
    prescription = get_object_or_404(Prescription, id=prescription_id)
    doctor = getattr(request.user, 'doctorprofile', None)
    
    if request.method == 'POST':
        form = PrescriptionForm(request.POST, instance=prescription, doctor=doctor)
        if form.is_valid():
            form.save()
            return redirect('/prescriptions/list/')
    else:
        form = PrescriptionForm(instance=prescription, doctor=doctor)
        
    return render(request, 'prescriptions/edit_prescription.html', {
        'form': form,
        'prescription': prescription
    })

def export_prescription_pdf(request, prescription_id):
    prescription = get_object_or_404(Prescription, id=prescription_id)
    buffer = generate_prescription_pdf(prescription)
    return FileResponse(buffer, as_attachment=True, filename=f'prescription_{prescription.id}.pdf')
