from django.shortcuts import render, redirect, get_object_or_404
from .forms import MedicalRecordForm, PatientMedicalRecordForm
from .models import MedicalRecord
from patients.models import PatientProfile
from appointments.models import Appointment

def upload_medical_record(request):
    """Doctor uploads medical record for patient"""
    doctor = getattr(request.user, 'doctorprofile', None)
    if not doctor:
        if request.user.role == 'doctor':
            return redirect('/doctors/create-profile/')
        return redirect('/doctor-dashboard/')

    if request.method == 'POST':
        form = MedicalRecordForm(request.POST, request.FILES, doctor=doctor)
        if form.is_valid():
            record = form.save(commit=False)
            record.uploaded_by_doctor = doctor
            record.uploaded_by_patient = False
            record.save()
            
            # Send notification to patient
            from reminders.notifications_utils import send_medical_record_notification
            send_medical_record_notification(record)
            
            return redirect('/medical-records/view/')
    else:
        form = MedicalRecordForm(doctor=doctor)

    return render(request, 'medical_records/upload_record.html', {'form': form})

def patient_upload_medical_record(request):
    """Patient uploads their own medical record"""
    patient = get_object_or_404(PatientProfile, user=request.user)

    if request.method == 'POST':
        form = PatientMedicalRecordForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save(commit=False)
            record.patient = patient
            record.uploaded_by_patient = True
            record.save()
            return redirect('/medical-records/view/')
    else:
        form = PatientMedicalRecordForm()

    return render(request, 'medical_records/patient_upload.html', {'form': form})

def view_medical_records(request):
    """View medical records. Handles both patient (viewing own) and doctor (viewing patient's)"""
    is_doctor = hasattr(request.user, 'doctorprofile')
    
    if is_doctor:
        # If doctor provides a patient_id in GET, show that patient's records
        patient_id = request.GET.get('patient_id')
        if patient_id:
            patient = get_object_or_404(PatientProfile, id=patient_id)
            records = MedicalRecord.objects.filter(patient=patient).order_by('-uploaded_at')
        else:
            # Show all records for patients who have appointments with this doctor
            doctor = request.user.doctorprofile
            patient_ids = Appointment.objects.filter(doctor=doctor).values_list('patient_id', flat=True).distinct()
            records = MedicalRecord.objects.filter(patient_id__in=patient_ids).order_by('-uploaded_at')
            patient = None
    else:
        patient, created = PatientProfile.objects.get_or_create(user=request.user)
        records = MedicalRecord.objects.filter(patient=patient).order_by('-uploaded_at')
    
    # Prepare the appropriate upload form for the integrated section
    if is_doctor:
        upload_form = MedicalRecordForm(doctor=request.user.doctorprofile)
    else:
        upload_form = PatientMedicalRecordForm()
    
    return render(request, 'medical_records/view_records.html', {
        'records': records,
        'patient': patient,
        'is_doctor': is_doctor,
        'upload_form': upload_form,
    })

from django.http import HttpResponse, Http404
import os

def download_medical_record(request, record_id):
    record = get_object_or_404(MedicalRecord, id=record_id)
    
    # Check permissions (either doctor or the patient themselves)
    is_doctor = hasattr(request.user, 'doctorprofile')
    is_patient = hasattr(request.user, 'patientprofile') and record.patient == request.user.patientprofile
    
    if not (is_doctor or is_patient):
        raise Http404("You do not have permission to download this record.")

    if not record.report_file:
        raise Http404("No file attached to this record.")

    file_path = record.report_file.path
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/octet-stream")
            response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
            return response
    raise Http404
