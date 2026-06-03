import re
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q

from patients.models import PatientProfile
from doctors.models import DoctorProfile
from appointments.models import Appointment
from prescriptions.models import Prescription
from medical_records.models import MedicalRecord
from departments.models import Department
from .models import ChatSession, ChatMessage, AIAuditLog
from .symptom_engine import SymptomEngine

logger = logging.getLogger(__name__)

# Ensure lazy-loaded SymptomEngine singleton instance is shared across queries on CPU
_symptom_engine_instance = None

def get_symptom_engine():
    global _symptom_engine_instance
    if _symptom_engine_instance is None:
        _symptom_engine_instance = SymptomEngine()
    return _symptom_engine_instance


@login_required
def chat_view(request):
    """
    Renders the custom dark theme ChatGPT-style AI assistant dashboard.
    """
    # Verify user profile exists
    patient = None
    if request.user.role == 'patient':
        patient, _ = PatientProfile.objects.get_or_create(user=request.user)
    elif request.user.role == 'doctor':
        pass  # Doctors can use the chat as well
    elif request.user.is_staff or request.user.is_superuser:
        pass  # Admins can use the chat

    # Setup context: Filter sessions strictly belonging to the logged-in user and dashboard role
    recent_sessions = ChatSession.objects.filter(user=request.user, assistant_role=request.user.role).order_by('-started_at')[:8]

    return render(request, 'ai_assistant/chat.html', {
        'recent_sessions': recent_sessions,
        'user': request.user,
        'title': 'Medicare AI Assistant Portal'
    })


@login_required
@require_POST
def api_send_message(request):
    """
    Intelligent chatbot query processing with DB integration, RBAC checks, and HIPAA Auditing.
    """
    # 1. AUTHENTICATION & ROLE-BASED ACCESS CONTROL
    user = request.user
    patient = None
    doctor = None
    
    if user.role == 'patient':
        patient = PatientProfile.objects.filter(user=user).first()
        if not patient:
            patient, _ = PatientProfile.objects.get_or_create(user=user)
    elif user.role == 'doctor':
        doctor = getattr(user, 'doctorprofile', None)

    # Resolve or create ChatSession
    try:
        data = json.loads(request.body)
        message_text = data.get('message', '').strip()
        session_id_str = data.get('session_id', '').strip()
    except Exception:
        return JsonResponse({'error': 'Invalid request payload.'}, status=400)

    if not message_text:
        return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

    session = None
    if session_id_str:
        try:
            # Secure ownership check: Session must belong to the logged-in user and current dashboard role
            session = ChatSession.objects.filter(user=user, assistant_role=user.role, session_id=session_id_str, is_active=True).first()
        except Exception:
            pass

    if not session:
        # Create session belonging to the logged-in user and role
        session = ChatSession.objects.create(user=user, assistant_role=user.role, patient=patient, is_active=True)

    # Save user message to database
    ChatMessage.objects.create(session=session, role='user', content=message_text)

    # Resolve IP & Device metadata
    ip_addr = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown Device')

    # Get memory context
    memory = session.get_memory()

    # 2. INTELLIGENT ROUTER & DATABASE ACCESS LAYER
    clean_msg = message_text.lower().strip()
    action_taken = 'General Chat Query'
    result_summary = 'Returned conversational fallback response'
    response_html = ""

    # Standard "not available" message
    not_found_message = "<p>Requested information is not available in the HMS database.</p>"

    # Check for emergency symptoms (Patient Dashboard focus)
    is_emergency_keyword = any(k in clean_msg for k in ['chest pain', 'breathing difficulty', 'heart pain', 'heart attack', 'sudden bleeding', 'unconscious', 'severe allergy'])

    # ------------------ ROLE-BASED ACCESS CONTROL (RBAC) & ROUTING ------------------
    if user.role == 'patient':
        if not patient:
            patient, _ = PatientProfile.objects.get_or_create(user=user)

        # Emergency Mode Response
        if is_emergency_keyword:
            action_taken = 'Emergency Mode Triggered'
            result_summary = 'Emergency alert generated for critical symptoms'
            
            # Fetch cardiologists
            cardio_docs = DoctorProfile.objects.filter(
                Q(specialization__icontains='Cardiologist') | Q(department__name__icontains='Cardiology'),
                is_approved=True
            ).order_by('-experience')
            
            cardio_list = ""
            for doc in cardio_docs[:3]:
                cardio_list += f"""
                <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px; margin-bottom: 8px;">
                    <div style="font-weight: bold; font-size:12.5px;">Dr. {doc.user.first_name} {doc.user.last_name} ({doc.doctor_id})</div>
                    <div style="font-size:11px; color: var(--text-muted);">{doc.specialization} | Fee: ${doc.consultation_fee}</div>
                    <div style="text-align: right; margin-top: 6px;">
                        <button class="chat-btn" data-value="book_doc_{doc.doctor_id}" style="padding: 4px 10px; font-size: 11px; border-radius: 6px; background: #EF4444; color: white; border: none; font-weight: bold; cursor: pointer;">Book Immediate Appointment</button>
                    </div>
                </div>
                """

            response_html = f"""
            <div class="chat-custom-card emergency-card" style="border: 2px solid #EF4444; background: rgba(239, 68, 68, 0.05);">
                <div class="card-header" style="color: #EF4444; font-weight: bold; background: rgba(239, 68, 68, 0.1);"><i class="fas fa-exclamation-triangle"></i> EMERGENCY ALERT: Chest Pain / Breathing Difficulty</div>
                <div class="card-body">
                    <p style="margin: 0 0 10px 0; font-size: 13.5px; font-weight: 500; color: #ECECEC;">If you are experiencing chest pain, pressure, or difficulty breathing, please seek immediate emergency care.</p>
                    <p style="margin: 0 0 12px 0; font-size: 12.5px; color: #B4B4B4;">Call the nearest ambulance line or contact our emergency help desk immediately: <strong>+1-800-555-0199</strong>.</p>
                    <div style="margin-top: 10px;">
                        <strong style="display:block; margin-bottom: 6px; font-size: 12px; color: #EF4444;"><i class="fas fa-user-md"></i> Nearest Available Cardiologists:</strong>
                        {cardio_list if cardio_list else "<p style='font-size:11px; color:#B4B4B4;'>No cardiologists online right now. Contact emergency staff immediately.</p>"}
                    </div>
                </div>
            </div>
            """

        # Form submissions (In-chat Appointment Booking)
        elif clean_msg.startswith('submit_booking:'):
            action_taken = 'Process In-Chat Appointment Booking'
            try:
                params = {}
                parts = clean_msg[len('submit_booking:'):].split(',')
                for p in parts:
                    if '=' in p:
                        k, v = p.split('=', 1)
                        params[k.strip().lower()] = v.strip()

                doc_id = params.get('doctor_id', '').upper()
                symptoms = params.get('symptoms', 'General consultation')
                pref_date = params.get('date', '')
                pref_time = params.get('time', '')
                
                # Fetch doctor profile
                doctor_profile = DoctorProfile.objects.filter(doctor_id=doc_id).first()
                if not doctor_profile:
                    doctor_profile = DoctorProfile.objects.filter(is_approved=True).first()

                if not pref_date or not pref_time:
                    raise ValueError("Date and time are required.")

                from django.utils.dateparse import parse_date, parse_time
                appointment = Appointment.objects.create(
                    patient=patient,
                    doctor=doctor_profile,
                    appointment_date=parse_date(pref_date),
                    appointment_time=parse_time(pref_time),
                    reason=symptoms,
                    status='Pending'
                )

                result_summary = f"Booked in-chat appointment ID {appointment.appointment_id}"
                response_html = f"""
                <div class="chat-custom-card success-card" style="border-left: 4px solid #10B981;">
                    <div class="card-header" style="color: #10B981; font-weight: bold;"><i class="fas fa-check-circle"></i> Appointment Booked Successfully!</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Appointment ID:</span> A{appointment.appointment_id}</div>
                        <div class="card-field"><span class="label">Doctor ID:</span> {doctor_profile.doctor_id if doctor_profile else 'N/A'}</div>
                        <div class="card-field"><span class="label">Patient ID:</span> {patient.patient_id}</div>
                        <div class="card-field"><span class="label">Doctor:</span> Dr. {doctor_profile.user.first_name} {doctor_profile.user.last_name} ({doctor_profile.specialization})</div>
                        <div class="card-field"><span class="label">Patient:</span> {params.get('patient_name', user.first_name or user.username)} (Age: {params.get('age', patient.age)})</div>
                        <div class="card-field"><span class="label">Date/Time:</span> {pref_date} at {pref_time}</div>
                        <div class="card-field"><span class="label">Symptoms:</span> {symptoms}</div>
                        <div style="margin-top: 10px; font-size: 11px; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px;">
                            🔔 Reminder notifications scheduled for 24 Hours, 1 Hour, and 15 Minutes before via SMS/Email.
                        </div>
                    </div>
                </div>
                """
            except Exception as e:
                result_summary = f"Failed in-chat booking: {str(e)}"
                response_html = f"<div class='chat-custom-card warning-card'><div class='card-header'><i class='fas fa-exclamation-triangle'></i> Booking Failed</div><div class='card-body'><p>Could not process appointment: {str(e)}. Please check date/time inputs and try again.</p></div></div>"

        # Show Booking Form triggers
        elif clean_msg.startswith('book_doc_') or clean_msg.startswith('book doc '):
            action_taken = 'Render Chat Booking Form'
            target_id = clean_msg.replace('book_doc_', '').replace('book doc ', '').strip()
            doc_profile = None
            if target_id.isdigit():
                doc_profile = DoctorProfile.objects.filter(id=int(target_id)).first()
            if not doc_profile:
                doc_profile = DoctorProfile.objects.filter(doctor_id__iexact=target_id).first()

            if doc_profile:
                result_summary = f"Rendering booking form for Dr. {doc_profile.user.username}"
                response_html = f"""
                <div class="chat-custom-card booking-form-card" style="max-width: 450px;">
                    <div class="card-header"><i class="fas fa-file-medical"></i> Book Appointment with Dr. {doc_profile.user.first_name} {doc_profile.user.last_name}</div>
                    <div class="card-body">
                        <form class="chat-booking-form" onsubmit="event.preventDefault(); submitChatBooking(this);">
                            <input type="hidden" name="doctor_id" value="{doc_profile.doctor_id}">
                            <div style="margin-bottom: 8px;">
                                <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Patient Name</label>
                                <input type="text" name="patient_name" value="{user.first_name} {user.last_name}" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                            </div>
                            <div style="display:flex; gap:10px; margin-bottom:8px;">
                                <div style="flex:1;">
                                    <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Age</label>
                                    <input type="number" name="age" value="{patient.age}" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                                </div>
                                <div style="flex:1;">
                                    <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Gender</label>
                                    <input type="text" name="gender" value="{patient.gender or ''}" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                                </div>
                            </div>
                            <div style="display:flex; gap:10px; margin-bottom:8px;">
                                <div style="flex:1;">
                                    <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Mobile Number</label>
                                    <input type="text" name="mobile" value="{user.phone or ''}" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                                </div>
                                <div style="flex:1;">
                                    <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Email</label>
                                    <input type="email" name="email" value="{user.email or ''}" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                                </div>
                            </div>
                            <div style="margin-bottom: 8px;">
                                <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Symptoms / Reason</label>
                                <input type="text" name="symptoms" required placeholder="Describe what you feel..." style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                            </div>
                            <div style="display:flex; gap:10px; margin-bottom:8px;">
                                <div style="flex:1;">
                                    <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Preferred Date</label>
                                    <input type="date" name="preferred_date" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                                </div>
                                <div style="flex:1;">
                                    <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Preferred Time</label>
                                    <input type="time" name="preferred_time" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                                </div>
                            </div>
                            <div style="margin-bottom: 12px;">
                                <label style="font-size:11px; display:block; margin-bottom:3px; color:var(--text-muted);">Notes (Optional)</label>
                                <textarea name="notes" rows="2" style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white; resize:none;"></textarea>
                            </div>
                            <button type="submit" style="width:100%; padding:8px; background:#2563EB; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">Submit Appointment</button>
                        </form>
                    </div>
                </div>
                """
            else:
                result_summary = "Doctor profile not found for booking form"
                response_html = not_found_message

        # Specific Doctor Profile Retrieval by patient: Matches e.g. "find d101", "show doctor d101", "d101"
        elif re.search(r'\b(d\d{3})\b', clean_msg):
            action_taken = 'Doctor ID Profile Retrieval'
            doc_id_match = re.search(r'\b(d\d{3})\b', clean_msg).group(1).upper()
            doc = DoctorProfile.objects.filter(doctor_id=doc_id_match, is_approved=True).first()
            if doc:
                result_summary = f"Retrieved profile of doctor ID {doc_id_match}"
                dept_name = doc.department.name if doc.department else 'Specialist'
                response_html = f"""
                <div class="chat-custom-card doctor-card">
                    <div class="card-header"><i class="fas fa-user-md"></i> Doctor Profile: Dr. {doc.user.first_name} {doc.user.last_name}</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Doctor ID:</span> {doc.doctor_id}</div>
                        <div class="card-field"><span class="label">Specialization:</span> {doc.specialization}</div>
                        <div class="card-field"><span class="label">Department:</span> {dept_name}</div>
                        <div class="card-field"><span class="label">Qualification:</span> {doc.qualification}</div>
                        <div class="card-field"><span class="label">Experience:</span> {doc.experience} Years</div>
                        <div class="card-field"><span class="label">Consultation Fee:</span> ${doc.consultation_fee}</div>
                        <div class="card-field"><span class="label">Availability:</span> {doc.available_days}</div>
                        <div class="card-field"><span class="label">Rating:</span> ⭐ {doc.rating} / 5.0</div>
                        <div style="text-align: right; margin-top: 12px;">
                            <button class="chat-btn" data-value="book_doc_{doc.doctor_id}" style="padding: 6px 14px; font-size: 12px; border-radius: 8px; background: #2563EB; color: white; border: none; font-weight: bold; cursor: pointer;">Book Appointment</button>
                        </div>
                    </div>
                </div>
                """
            else:
                result_summary = "Doctor ID profile not found"
                response_html = not_found_message

        # Appointments lookup
        elif any(k in clean_msg for k in ['previous appointment', 'last appointment', 'appointment history', 'past appointment']):
            action_taken = 'Query Appointment History'
            appts = Appointment.objects.filter(patient=patient).order_by('-appointment_date', '-appointment_time')
            if appts.exists():
                appt = appts.first()
                status_class = 'pending' if appt.status.lower() == 'pending' else 'success'
                result_summary = f"Returned last appointment ID {appt.appointment_id}"
                
                presc_count = Prescription.objects.filter(appointment=appt).count()
                report_count = MedicalRecord.objects.filter(patient=patient, uploaded_at__date=appt.appointment_date).count()

                presc_text = "Available" if presc_count > 0 else "None Available"
                report_text = f"{report_count} Reports Available" if report_count > 0 else "None Available"

                response_html = f"""
                <div class="chat-custom-card appointment-card">
                    <div class="card-header"><i class="fas fa-calendar-check"></i> Previous Appointment Details</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Appointment ID:</span> A{appt.appointment_id}</div>
                        <div class="card-field"><span class="label">Doctor ID:</span> {appt.doctor.doctor_id if appt.doctor else 'N/A'}</div>
                        <div class="card-field"><span class="label">Doctor:</span> Dr. {appt.doctor.user.first_name} {appt.doctor.user.last_name if appt.doctor else ''}</div>
                        <div class="card-field"><span class="label">Date:</span> {appt.appointment_date.strftime('%B %d, %Y')}</div>
                        <div class="card-field"><span class="label">Time:</span> {appt.appointment_time}</div>
                        <div class="card-field"><span class="label">Status:</span> <span class="status-badge {status_class}">{appt.status}</span></div>
                        <div class="card-field"><span class="label">Prescription:</span> {presc_text}</div>
                        <div class="card-field"><span class="label">Lab Reports:</span> {report_text}</div>
                    </div>
                </div>
                """
            else:
                result_summary = "No appointments found"
                response_html = not_found_message

        # Next/upcoming appointment
        elif any(k in clean_msg for k in ['next appointment', 'upcoming appointment', 'future appointment']):
            action_taken = 'Query Upcoming Appointments'
            now_date = timezone.now().date()
            appts = Appointment.objects.filter(patient=patient, appointment_date__gte=now_date).order_by('appointment_date', 'appointment_time')
            if appts.exists():
                appt = appts.first()
                status_class = 'pending' if appt.status.lower() == 'pending' else 'success'
                result_summary = f"Returned next appointment ID {appt.appointment_id}"
                response_html = f"""
                <div class="chat-custom-card appointment-card">
                    <div class="card-header"><i class="fas fa-clock"></i> Next Scheduled Appointment</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Appointment ID:</span> A{appt.appointment_id}</div>
                        <div class="card-field"><span class="label">Doctor ID:</span> {appt.doctor.doctor_id if appt.doctor else 'N/A'}</div>
                        <div class="card-field"><span class="label">Doctor:</span> Dr. {appt.doctor.user.first_name} {appt.doctor.user.last_name if appt.doctor else ''}</div>
                        <div class="card-field"><span class="label">Date:</span> {appt.appointment_date.strftime('%B %d, %Y')}</div>
                        <div class="card-field"><span class="label">Time:</span> {appt.appointment_time}</div>
                        <div class="card-field"><span class="label">Status:</span> <span class="status-badge {status_class}">{appt.status}</span></div>
                    </div>
                </div>
                """
            else:
                result_summary = "No upcoming appointments"
                response_html = not_found_message

        # Prescription search
        elif any(k in clean_msg for k in ['prescription', 'medicine', 'prescribed', 'medication']):
            action_taken = 'Query Prescription History'
            prescs = Prescription.objects.filter(patient=patient).order_by('-prescribed_date')
            if prescs.exists():
                pr = prescs.first()
                result_summary = f"Returned latest prescription ID {pr.id}"
                med_lines = pr.medicines.split('\n')
                med_rows = ""
                for line in med_lines:
                    if line.strip():
                        parts = line.split('-')
                        med_name = parts[0].strip()
                        dosage = parts[1].strip() if len(parts) > 1 else "As directed"
                        med_rows += f"<tr><td style='padding: 8px; border-bottom: 1px solid var(--border-color);'>{med_name}</td><td style='padding: 8px; border-bottom: 1px solid var(--border-color);'>{dosage}</td></tr>"

                response_html = f"""
                <div class="chat-custom-card prescription-card">
                    <div class="card-header"><i class="fas fa-file-prescription"></i> Medication & Prescription Details</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Doctor Name:</span> Dr. {pr.doctor.user.first_name} {pr.doctor.user.last_name}</div>
                        <div class="card-field"><span class="label">Doctor ID:</span> {pr.doctor.doctor_id if pr.doctor else 'N/A'}</div>
                        <div class="card-field"><span class="label">Visit Date:</span> {pr.prescribed_date.strftime('%B %d, %Y')}</div>
                        <div class="card-field"><span class="label">Diagnosis Notes:</span> {pr.diagnosis}</div>
                        <div style="margin-top: 10px; font-weight: bold; font-size: 13px; color: var(--text-main);"><i class="fas fa-pills"></i> Medication List:</div>
                        <table style="width: 100%; border-collapse: collapse; font-size: 12.5px; color: var(--text-muted); margin-top: 6px;">
                            <thead>
                                <tr style="background: rgba(255,255,255,0.05); text-align: left;">
                                    <th style="padding: 8px;">Medicine</th>
                                    <th style="padding: 8px;">Instructions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {med_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
                """
            else:
                result_summary = "No prescriptions found"
                response_html = not_found_message

        # Lab reports
        elif any(k in clean_msg for k in ['blood test', 'lab report', 'blood report', 'reports', 'medical report']):
            action_taken = 'Query Lab Reports'
            records = MedicalRecord.objects.filter(patient=patient).order_by('-uploaded_at')
            if records.exists():
                rec = records.first()
                result_summary = f"Returned latest lab report ID {rec.id}"
                file_url = rec.report_file.url if rec.report_file else "#"
                response_html = f"""
                <div class="chat-custom-card lab-card">
                    <div class="card-header"><i class="fas fa-vial"></i> Latest Medical Lab Report</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Report Name:</span> {rec.report_name}</div>
                        <div class="card-field"><span class="label">Date:</span> {rec.uploaded_at.strftime('%B %d, %Y')}</div>
                        <div class="card-field"><span class="label">Source:</span> {rec.from_info}</div>
                        <div class="card-field"><span class="label">Recipient:</span> {rec.to_info}</div>
                        <div class="card-field"><span class="label">Type:</span> {rec.get_file_type_display()}</div>
                        <div class="card-actions" style="margin-top: 12px;">
                            <a href="{file_url}" target="_blank" class="btn-card-action" style="padding: 8px 14px; background: #2563EB; color: white !important; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 13px; display: inline-flex; align-items: center; gap: 6px;">
                                <i class="fas fa-download"></i> View / Download Report
                            </a>
                        </div>
                    </div>
                </div>
                """
            else:
                result_summary = "No reports found"
                response_html = not_found_message

        # Patient health timeline
        elif 'timeline' in clean_msg:
            action_taken = 'Query Patient Health Timeline'
            timeline = []
            appts = Appointment.objects.filter(patient=patient).order_by('-appointment_date')[:5]
            for a in appts:
                timeline.append({
                    'date': timezone.make_aware(timezone.datetime.combine(a.appointment_date, timezone.datetime.min.time())),
                    'type': 'Appointment',
                    'title': f"Consultation with Dr. {a.doctor.user.last_name}",
                    'desc': f"Appointment ID: A{a.appointment_id}, Status: {a.status}"
                })

            records = MedicalRecord.objects.filter(patient=patient).order_by('-uploaded_at')[:5]
            for r in records:
                timeline.append({
                    'date': r.uploaded_at,
                    'type': 'Lab Report',
                    'title': f"Report: {r.report_name}",
                    'desc': f"Source: {r.from_info}"
                })

            prescs = Prescription.objects.filter(patient=patient).order_by('-prescribed_date')[:5]
            for p in prescs:
                timeline.append({
                    'date': p.prescribed_date,
                    'type': 'Prescription',
                    'title': f"Prescription from Dr. {p.doctor.user.last_name}",
                    'desc': f"Diagnosis: {p.diagnosis[:40]}..."
                })

            timeline.sort(key=lambda x: x['date'], reverse=True)

            if timeline:
                timeline_rows = ""
                for idx, item in enumerate(timeline):
                    color = "#2563EB" if item['type'] == 'Appointment' else "#10B981" if item['type'] == 'Lab Report' else "#F59E0B"
                    timeline_rows += f"""
                    <div style="display: flex; gap: 15px; margin-bottom: 15px; position: relative;">
                        <div style="display: flex; flex-direction: column; align-items: center;">
                            <div style="width: 14px; height: 14px; border-radius: 50%; background: {color}; border: 3px solid var(--panel-bg); z-index: 1;"></div>
                            { '<div style="width: 2px; flex: 1; background: var(--border-color);"></div>' if idx < len(timeline)-1 else '' }
                        </div>
                        <div style="padding-bottom: 10px;">
                            <span style="font-size: 11px; font-weight: bold; color: var(--text-muted);">{item['date'].strftime('%b %d, %Y')}</span>
                            <h6 style="margin: 2px 0; font-size: 13px; font-weight: bold; color: var(--text-main);">{item['title']}</h6>
                            <p style="margin: 0; font-size: 11.5px; color: var(--text-muted);">{item['desc']}</p>
                        </div>
                    </div>
                    """

                result_summary = f"Returned timeline of {len(timeline)} events"
                response_html = f"""
                <div class="chat-custom-card timeline-card">
                    <div class="card-header"><i class="fas fa-history"></i> Patient Health Timeline</div>
                    <div class="card-body" style="padding-top: 15px;">
                        {timeline_rows}
                    </div>
                </div>
                """
            else:
                result_summary = "Timeline empty"
                response_html = not_found_message

        # ICU beds / Resource check
        elif any(k in clean_msg for k in ['bed', 'icu', 'ambulance', 'emergency contact', 'branch']):
            action_taken = 'Query Hospital Operations'
            result_summary = 'Returned real-time mock data for ICU beds / Ambulance availability'
            response_html = """
            <div class="chat-custom-card operations-card">
                <div class="card-header"><i class="fas fa-hospital-symbol"></i> Hospital Resource Status</div>
                <div class="card-body">
                    <div class="card-field"><span class="label"><i class="fas fa-bed" style="color: #2563EB;"></i> ICU Bed Status:</span> <span style="font-weight: bold; color: #10B981;">4 Beds Available</span> (Triage Room 204)</div>
                    <div class="card-field"><span class="label"><i class="fas fa-ambulance" style="color: #EF4444;"></i> Ambulance Triage:</span> <span style="font-weight: bold; color: #10B981;">2 Fleet Units Active</span> (Main Branch)</div>
                    <div class="card-field"><span class="label"><i class="fas fa-phone-alt"></i> Emergency Line:</span> <span style="font-weight: bold; color: var(--text-main);">+1-800-555-0199</span> (24/7 Support)</div>
                    <div class="card-field"><span class="label"><i class="fas fa-map-marker-alt"></i> Nearest Branch:</span> <span style="font-size:12px;">Medicare Central Hospital, Block C, Downtown</span></div>
                </div>
            </div>
            """

        # General symptom parsing / recommendations engine
        else:
            symptom_spec_map = {
                'fever': ('General Physician', 'General Physician', 'Low-Medium'),
                'cough': ('General Physician', 'General Physician', 'Low'),
                'cold': ('General Physician', 'General Physician', 'Low'),
                'skin allergy': ('Dermatologist', 'Dermatology', 'Low'),
                'allergy': ('Dermatologist', 'Dermatology', 'Low'),
                'rash': ('Dermatologist', 'Dermatology', 'Low'),
                'eye issues': ('Ophthalmologist', 'Ophthalmology', 'Low'),
                'eye problems': ('Ophthalmologist', 'Ophthalmology', 'Low'),
                'dental problems': ('Dentist', 'Dental', 'Low'),
                'dental pain': ('Dentist', 'Dental', 'Low'),
                'toothache': ('Dentist', 'Dental', 'Low'),
                'diabetes': ('Endocrinologist', 'Endocrinology', 'Medium'),
                'sugar': ('Endocrinologist', 'Endocrinology', 'Medium'),
                'bone pain': ('Orthopedic', 'Orthopedics', 'Low-Medium'),
                'back pain': ('Orthopedic', 'Orthopedics', 'Low-Medium'),
                'joint pain': ('Orthopedic', 'Orthopedics', 'Low-Medium'),
                'mental stress': ('Psychiatrist', 'Psychiatry', 'Low-Medium'),
                'stress': ('Psychiatrist', 'Psychiatry', 'Low-Medium'),
                'heart pain': ('Cardiologist', 'Cardiology', 'High'),
                'chest pain': ('Cardiologist', 'Cardiology', 'High'),
                'headache': ('Neurologist', 'Neurology', 'Low-Medium'),
                'migraine': ('Neurologist', 'Neurology', 'Low-Medium'),
            }

            matched_symptom = None
            for key in symptom_spec_map:
                if key in clean_msg:
                    matched_symptom = key
                    break

            if matched_symptom:
                spec, dept_name, risk_level = symptom_spec_map[matched_symptom]
                docs = DoctorProfile.objects.filter(
                    Q(specialization__icontains=spec) | Q(department__name__icontains=dept_name),
                    is_approved=True
                ).order_by('-experience', '-rating')
                
                doc_cards = ""
                for doc in docs[:4]:
                    doc_cards += f"""
                    <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 12px; padding: 12px; margin-bottom: 8px; color: var(--text-main);">
                        <h6 style="margin: 0; font-size: 13.0px; font-weight: bold;">Dr. {doc.user.first_name} {doc.user.last_name} ({doc.doctor_id})</h6>
                        <p style="margin: 2px 0; font-size: 11px; color: var(--text-muted);">{doc.specialization} | Experience: {doc.experience} Years | Fee: ${doc.consultation_fee} | Rating: ⭐ {doc.rating}</p>
                        <div style="text-align: right; margin-top: 6px;">
                            <button class="chat-btn" data-value="book_doc_{doc.doctor_id}" style="padding: 4px 10px; font-size: 11px; border-radius: 6px; background: #2563EB; color: white; border: none; font-weight: bold; cursor: pointer;">Book Appointment</button>
                        </div>
                    </div>
                    """

                action_taken = 'Extracted Symptoms & Suggested Specialist'
                result_summary = f"Extracted: {matched_symptom}, Mapped to Specialization: {spec}"

                risk_color = "#10B981" if risk_level == 'Low' else "#F59E0B" if 'Medium' in risk_level else "#EF4444"
                response_html = f"""
                <div class="chat-custom-card symptom-result-card">
                    <div class="card-header"><i class="fas fa-stethoscope"></i> Symptom Analysis Result</div>
                    <div class="card-body">
                        <p style="margin: 0 0 10px 0; font-size: 13px; color: var(--text-main);">Based on your described symptom (<strong>{matched_symptom}</strong>), you may consult a <strong>{spec}</strong>.</p>
                        
                        <div style="margin-bottom: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                            <span class="status-badge" style="background-color: rgba(255,255,255,0.05); color: var(--text-main);">Health Risk: <strong style="color: {risk_color};">{risk_level} Risk</strong></span>
                            <span class="status-badge" style="background-color: rgba(16, 185, 129, 0.1); color: #10B981;">📅 Follow-up: 7 Days</span>
                        </div>

                        { f"<div style='margin-top: 10px;'><strong>Available {spec} Doctors:</strong></div><div style='margin-top: 6px;'>{doc_cards}</div>" if doc_cards else "<p style='font-size:11.5px; color:var(--text-muted);'>No active specialists available for booking in this department at the moment.</p>" }
                        
                        <p style="font-size: 11.5px; color: var(--text-muted); font-style: italic; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px; margin-top: 10px;">
                            ⚠️ Disclaimer: I am not a doctor. I cannot diagnose diseases or prescribe medications. Please consult a doctor for proper medical evaluation.
                        </p>
                    </div>
                </div>
                """
            else:
                response_html = f"""
                <div class="welcome-card-premium" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 18px; padding: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.02); margin-bottom: 15px;">
                    <h4 style="font-size: 18px; font-weight: 700; color: #2563EB; margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px;">
                        <i class="fas fa-robot"></i> Welcome to MediCore AI 🏥
                    </h4>
                    <p style="font-size: 14px; color: var(--text-main); margin: 0 0 10px 0;">I am your intelligent <strong>MediCore AI Health Assistant</strong>.</p>
                    <p style="font-size: 13px; color: var(--text-muted); line-height: 1.4; margin: 0 0 12px 0;">Describe your symptoms (e.g. <i>"I have a fever and cough"</i> or <i>"chest pain"</i>) to consult a recommended specialist doctor, lookup prescriptions, view previous appointments or check timeline logs.</p>
                    <div style="font-size: 11px; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px;">
                        Patient ID: <strong>{patient.patient_id}</strong>
                    </div>
                </div>
                """

    elif user.role == 'doctor':
        if not doctor:
            doctor = getattr(user, 'doctorprofile', None)

        if not doctor:
            response_html = "<p>Please complete your Doctor Profile before using the AI assistant portal.</p>"
        
        # Prescription draft approval & save handler
        elif clean_msg.startswith('save_prescription:'):
            action_taken = 'Save Drafted Prescription'
            try:
                params = {}
                parts = clean_msg[len('save_prescription:'):].split(',')
                for p in parts:
                    if '=' in p:
                        k, v = p.split('=', 1)
                        params[k.strip().lower()] = v.strip()

                pat_id = params.get('patient_id', '').upper()
                diagnosis = params.get('diagnosis', 'Consultation')
                medicines = params.get('medicines', '')

                target_pat = PatientProfile.objects.filter(patient_id=pat_id).first()
                if not target_pat:
                    response_html = not_found_message
                else:
                    authorized = Appointment.objects.filter(doctor=doctor, patient=target_pat).exists()
                    if not authorized:
                        response_html = not_found_message
                    else:
                        appt = Appointment.objects.filter(doctor=doctor, patient=target_pat).order_by('-appointment_date').first()
                        prescription = Prescription.objects.create(
                            patient=target_pat,
                            doctor=doctor,
                            appointment=appt,
                            diagnosis=diagnosis,
                            medicines=medicines.replace(';', '\n')
                        )
                        result_summary = f"Saved prescription ID {prescription.id} for doctor {doctor.doctor_id}"
                        response_html = f"""
                        <div class="chat-custom-card success-card" style="border-left: 4px solid #10B981;">
                            <div class="card-header" style="color: #10B981; font-weight: bold;"><i class="fas fa-check-circle"></i> Prescription Approved & Saved</div>
                            <div class="card-body">
                                <div class="card-field"><span class="label">Patient ID:</span> {target_pat.patient_id}</div>
                                <div class="card-field"><span class="label">Patient Name:</span> {target_pat.user.username}</div>
                                <div class="card-field"><span class="label">Diagnosis:</span> {prescription.diagnosis}</div>
                                <div style="margin-top: 10px; font-weight: bold; font-size:12px;"><i class="fas fa-pills"></i> Medicines list:</div>
                                <pre style="background: rgba(255,255,255,0.02); padding: 8px; border-radius: 6px; font-size: 12px; margin-top: 4px; border: 1px solid rgba(255,255,255,0.05); color: var(--text-muted);">{prescription.medicines}</pre>
                            </div>
                        </div>
                        """
            except Exception as e:
                response_html = f"<p>Error saving prescription: {str(e)}</p>"

        # Search Patient by ID: e.g. "P1045" or "Show Patient P205" or "P205"
        elif re.search(r'\b(p\d{3})\b', clean_msg):
            action_taken = 'Doctor Patient ID Search'
            pat_id_match = re.search(r'\b(p\d{3})\b', clean_msg).group(1).upper()
            target_pat = PatientProfile.objects.filter(patient_id=pat_id_match).first()

            if not target_pat:
                result_summary = f"Patient ID {pat_id_match} not found"
                response_html = not_found_message
            else:
                # Strict Doctor Access Rules: only patients assigned to doctor
                authorized = Appointment.objects.filter(doctor=doctor, patient=target_pat).exists()
                if not authorized:
                    result_summary = f"Unauthorized access attempt by Doctor {doctor.doctor_id} to Patient {pat_id_match}"
                    response_html = not_found_message
                else:
                    result_summary = f"Retrieved patient {pat_id_match} details"
                    appts = Appointment.objects.filter(doctor=doctor, patient=target_pat).order_by('-appointment_date')
                    prescs = Prescription.objects.filter(doctor=doctor, patient=target_pat).order_by('-prescribed_date')
                    records = MedicalRecord.objects.filter(patient=target_pat).order_by('-uploaded_at')

                    appt_list_html = ""
                    for a in appts[:3]:
                        appt_list_html += f"<li>A{a.appointment_id} - {a.appointment_date} (Status: {a.status})</li>"

                    presc_list_html = ""
                    for p in prescs[:3]:
                        presc_list_html += f"<li>{p.prescribed_date.strftime('%Y-%m-%d')}: {p.diagnosis}</li>"

                    report_list_html = ""
                    for r in records[:3]:
                        file_url = r.report_file.url if r.report_file else "#"
                        report_list_html += f"<li><a href='{file_url}' target='_blank' style='color:#2563EB;'>{r.report_name}</a> ({r.uploaded_at.strftime('%Y-%m-%d')})</li>"

                    response_html = f"""
                    <div class="chat-custom-card patient-record-card">
                        <div class="card-header"><i class="fas fa-file-medical-alt"></i> Patient Records: {target_pat.user.first_name} {target_pat.user.last_name}</div>
                        <div class="card-body">
                            <div class="card-field"><span class="label">Patient ID:</span> {target_pat.patient_id}</div>
                            <div class="card-field"><span class="label">Age / Gender:</span> {target_pat.age} / {target_pat.gender}</div>
                            <div class="card-field"><span class="label">Blood Group:</span> {target_pat.blood_group}</div>
                            <div class="card-field"><span class="label">Medical History:</span> {target_pat.medical_history or 'None'}</div>
                            
                            <div style="margin-top: 12px;">
                                <strong>Appointment History:</strong>
                                <ul style="margin: 4px 0 0 16px; padding: 0; font-size:12px; color: var(--text-muted);">{appt_list_html if appt_list_html else '<li>No appointments found.</li>'}</ul>
                            </div>
                            <div style="margin-top: 10px;">
                                <strong>Prescriptions:</strong>
                                <ul style="margin: 4px 0 0 16px; padding: 0; font-size:12px; color: var(--text-muted);">{presc_list_html if presc_list_html else '<li>No prescriptions found.</li>'}</ul>
                            </div>
                            <div style="margin-top: 10px;">
                                <strong>Medical Reports & Scans:</strong>
                                <ul style="margin: 4px 0 0 16px; padding: 0; font-size:12px; color: var(--text-muted);">{report_list_html if report_list_html else '<li>No reports uploaded.</li>'}</ul>
                            </div>
                        </div>
                    </div>
                    """

        # Doctor profile retrieval
        elif any(k in clean_msg for k in ['my profile', 'doctor profile', 'doctor id', 'my id']):
            action_taken = 'Retrieve Own Doctor Profile'
            result_summary = f"Doctor {doctor.doctor_id} queried profile info"
            response_html = f"""
            <div class="chat-custom-card doctor-card">
                <div class="card-header"><i class="fas fa-id-card"></i> Your Doctor Profile</div>
                <div class="card-body">
                    <div class="card-field"><span class="label">Doctor ID:</span> {doctor.doctor_id}</div>
                    <div class="card-field"><span class="label">Name:</span> Dr. {doctor.user.first_name} {doctor.user.last_name}</div>
                    <div class="card-field"><span class="label">Specialization:</span> {doctor.specialization}</div>
                    <div class="card-field"><span class="label">Consultation Fee:</span> ${doctor.consultation_fee}</div>
                    <div class="card-field"><span class="label">Available Days:</span> {doctor.available_days}</div>
                    <div class="card-field"><span class="label">Rating / Reviews:</span> ⭐ {doctor.rating} ({doctor.reviews} Reviews)</div>
                </div>
            </div>
            """

        # Show appointments today / how many appointments
        elif any(k in clean_msg for k in ['appointment', 'appointments', 'schedule']):
            action_taken = 'Retrieve Doctor Appointments'
            today = timezone.now().date()
            doctor_appts = Appointment.objects.filter(doctor=doctor)

            if 'today' in clean_msg or 'how many' in clean_msg:
                today_appts = doctor_appts.filter(appointment_date=today)
                today_count = today_appts.count()
                pending_count = today_appts.filter(status='Pending').count()
                completed_count = today_appts.filter(status='Completed').count()
                result_summary = f"Returned today appointments stats for doctor {doctor.doctor_id}"

                appt_rows = ""
                for a in today_appts.order_by('appointment_time')[:5]:
                    appt_rows += f"<li>A{a.appointment_id} at {a.appointment_time} - Patient ID: {a.patient.patient_id} ({a.status})</li>"

                response_html = f"""
                <div class="chat-custom-card appointment-card">
                    <div class="card-header"><i class="fas fa-calendar-check"></i> Today's Schedule Stats</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Total Appointments Today:</span> {today_count}</div>
                        <div class="card-field"><span class="label">Pending:</span> {pending_count}</div>
                        <div class="card-field"><span class="label">Completed:</span> {completed_count}</div>
                        <div style="margin-top: 10px;">
                            <strong>Today's List:</strong>
                            <ul style="margin: 4px 0 0 16px; padding: 0; font-size:12px; color: var(--text-muted);">{appt_rows if appt_rows else '<li>No appointments today.</li>'}</ul>
                        </div>
                    </div>
                </div>
                """
            else:
                upcoming_appts = doctor_appts.filter(appointment_date__gte=today).order_by('appointment_date', 'appointment_time')[:5]
                result_summary = f"Returned upcoming appointments list for doctor {doctor.doctor_id}"
                appt_rows = ""
                for a in upcoming_appts:
                    appt_rows += f"<li>A{a.appointment_id} - {a.appointment_date} at {a.appointment_time} - Patient ID: {a.patient.patient_id} ({a.status})</li>"

                response_html = f"""
                <div class="chat-custom-card appointment-card">
                    <div class="card-header"><i class="fas fa-calendar-alt"></i> Upcoming Appointments</div>
                    <div class="card-body">
                        <ul style="margin: 0; padding-left: 16px; font-size:12.5px; color: var(--text-muted);">{appt_rows if appt_rows else '<li>No upcoming appointments scheduled.</li>'}</ul>
                    </div>
                </div>
                """

        # Prescription Generation Assistant
        elif 'diagnosed with' in clean_msg or 'prescription for' in clean_msg or 'prescribe' in clean_msg:
            action_taken = 'Generate Draft Prescription'
            disease = 'Viral Fever'
            medicines = "Paracetamol 650mg - Thrice daily after food (3 days)\nCough Syrup - 10ml twice daily (5 days)\nVitamin C - Once daily (10 days)"
            
            if 'cough' in clean_msg:
                disease = 'Bronchitis / Cough'
                medicines = "Expectorant Syrup - 10ml thrice daily (5 days)\nAmoxicillin 500mg - Twice daily (5 days)\nLoratadine 10mg - Once daily at night (7 days)"
            elif 'stomach' in clean_msg or 'gastric' in clean_msg:
                disease = 'Gastroenteritis / Acid Reflux'
                medicines = "Pantoprazole 40mg - Once daily before breakfast (10 days)\nAntacid Gel - 10ml after food as needed\nDomperidone 10mg - Thrice daily before food (5 days)"
            elif 'infection' in clean_msg:
                disease = 'Bacterial Infection'
                medicines = "Azithromycin 500mg - Once daily (3 days)\nProbiotics Capsule - Once daily after food (10 days)"

            result_summary = f"Generated draft prescription for: {disease}"
            response_html = f"""
            <div class="chat-custom-card prescription-draft-card" style="max-width: 420px; border-left: 4px solid #F59E0B;">
                <div class="card-header" style="color: #F59E0B; font-weight: bold;"><i class="fas fa-magic"></i> Prescription Assistant (Draft)</div>
                <div class="card-body">
                    <p style="font-size:12.5px; margin: 0 0 10px 0; color: var(--text-main);">AI suggested template for diagnosis: <strong>{disease}</strong></p>
                    <form onsubmit="event.preventDefault(); saveDraftPrescription(this);">
                        <div style="margin-bottom: 8px;">
                            <label style="font-size:11px; display:block; margin-bottom:3px; color: var(--text-muted);">Diagnosis</label>
                            <input type="text" name="diagnosis" value="{disease}" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                        </div>
                        <div style="margin-bottom: 8px;">
                            <label style="font-size:11px; display:block; margin-bottom:3px; color: var(--text-muted);">Medicines & Dosage</label>
                            <textarea name="medicines" rows="4" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white; font-size:12px; line-height: 1.4; resize:none;">{medicines}</textarea>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <label style="font-size:11px; display:block; margin-bottom:3px; color: var(--text-muted);">Enter Patient ID to Approve</label>
                            <input type="text" name="patient_id" placeholder="e.g. P205" required style="width:100%; padding:6px; background:#212124; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:white;">
                        </div>
                        <button type="submit" style="width:100%; padding:8px; background:#10B981; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;"><i class="fas fa-check"></i> Approve & Save Prescription</button>
                    </form>
                </div>
            </div>
            """

        else:
            response_html = f"""
            <div class="welcome-card-premium" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 18px; padding: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.02); margin-bottom: 15px;">
                <h4 style="font-size: 18px; font-weight: 700; color: #2563EB; margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-user-md"></i> Doctor Portal AI 👋
                </h4>
                <p style="font-size: 14px; color: var(--text-main); margin: 0 0 10px 0;">Hello, Dr. {user.last_name}! You are in the secure Doctor AI Assistant.</p>
                <p style="font-size: 13px; color: var(--text-muted); line-height: 1.4; margin: 0 0 12px 0;">Enter a Patient ID (e.g. <i>"P205"</i>) to pull authorized records, query schedule stats (<i>"appointments today"</i>), or type clinical diagnosis phrases (<i>"diagnosed with viral fever"</i>) to draft prescriptions.</p>
                <div style="font-size: 11px; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px;">
                    Doctor ID: <strong>{doctor.doctor_id if doctor else 'N/A'}</strong>
                </div>
            </div>
            """

    elif user.is_staff or user.is_superuser or user.role == 'admin':
        doc_id_match = None
        doc_match_obj = re.search(r'\b(d\d{3})\b', clean_msg)
        if doc_match_obj:
            doc_id_match = doc_match_obj.group(1).upper()

        if doc_id_match:
            action_taken = 'Admin Doctor Query'
            doc = DoctorProfile.objects.filter(doctor_id=doc_id_match).first()
            if not doc:
                result_summary = f"Doctor ID {doc_id_match} query by admin, but not found"
                response_html = not_found_message
            else:
                result_summary = f"Admin fetched Doctor ID {doc_id_match} details"
                appts = Appointment.objects.filter(doctor=doc)
                appts_count = appts.count()
                pending_count = appts.filter(status='Pending').count()
                completed_count = appts.filter(status='Completed').count()

                response_html = f"""
                <div class="chat-custom-card admin-doctor-card">
                    <div class="card-header"><i class="fas fa-stethoscope"></i> Admin Doctor View: Dr. {doc.user.first_name} {doc.user.last_name}</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Doctor ID:</span> {doc.doctor_id}</div>
                        <div class="card-field"><span class="label">Specialization:</span> {doc.specialization}</div>
                        <div class="card-field"><span class="label">Rating / Active:</span> ⭐ {doc.rating} / {'Online' if doc.is_online else 'Offline'} (Approved: {doc.is_approved})</div>
                        <div class="card-field"><span class="label">Total Appointments:</span> {appts_count}</div>
                        <div class="card-field"><span class="label">Completed / Pending:</span> {completed_count} / {pending_count}</div>
                        <div style="font-size:11px; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px; margin-top: 10px;">
                            ⭐ Rating details and clinical metrics authorized.
                        </div>
                    </div>
                </div>
                """

        # Patient ID Search
        elif re.search(r'\b(p\d{3})\b', clean_msg):
            action_taken = 'Admin Patient Query'
            pat_id_match = re.search(r'\b(p\d{3})\b', clean_msg).group(1).upper()
            target_pat = PatientProfile.objects.filter(patient_id=pat_id_match).first()

            if not target_pat:
                result_summary = f"Patient ID {pat_id_match} query by admin, but not found"
                response_html = not_found_message
            else:
                result_summary = f"Admin fetched Patient ID {pat_id_match} details"
                appts = Appointment.objects.filter(patient=target_pat).order_by('-appointment_date')
                prescs = Prescription.objects.filter(patient=target_pat).order_by('-prescribed_date')

                response_html = f"""
                <div class="chat-custom-card admin-patient-card">
                    <div class="card-header"><i class="fas fa-user-shield"></i> Admin Patient View: {target_pat.user.first_name} {target_pat.user.last_name}</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Patient ID:</span> {target_pat.patient_id}</div>
                        <div class="card-field"><span class="label">Age / Gender:</span> {target_pat.age} / {target_pat.gender}</div>
                        <div class="card-field"><span class="label">Medical History:</span> {target_pat.medical_history or 'None'}</div>
                        <div class="card-field"><span class="label">Total Appointments:</span> {appts.count()}</div>
                        <div class="card-field"><span class="label">Total Prescriptions:</span> {prescs.count()}</div>
                    </div>
                </div>
                """

        # Hospital Analytics
        elif any(k in clean_msg for k in ['hospital analytics', 'analytics', 'revenue', 'occupancy']):
            action_taken = 'Query Hospital Analytics'
            total_doctors = DoctorProfile.objects.count()
            total_patients = PatientProfile.objects.count()
            total_appts_today = Appointment.objects.filter(appointment_date=timezone.now().date()).count()
            
            # Revenue estimation from completions
            completed_appts = Appointment.objects.filter(status__in=['Approved', 'Completed'])
            total_revenue = 0
            for a in completed_appts:
                if a.doctor and a.doctor.consultation_fee:
                    total_revenue += a.doctor.consultation_fee
                    
            result_summary = f"Returned hospital analytics. Revenue: ${total_revenue}"

            response_html = f"""
            <div class="chat-custom-card hospital-analytics-card">
                <div class="card-header"><i class="fas fa-chart-bar"></i> Hospital Real-Time Analytics</div>
                <div class="card-body">
                    <div class="card-field"><span class="label">Total Active Doctors:</span> {total_doctors}</div>
                    <div class="card-field"><span class="label">Total Registered Patients:</span> {total_patients}</div>
                    <div class="card-field"><span class="label">Appointments Today:</span> {total_appts_today}</div>
                    <div class="card-field"><span class="label">Estimated Revenue:</span> ${total_revenue:.2f}</div>
                    <div class="card-field"><span class="label">Bed Occupancy:</span> 82% (ICU: 4 available)</div>
                    <div class="card-field"><span class="label">Active Departments:</span> 7</div>
                </div>
            </div>
            """

        # Patient Analytics
        elif 'patient analytics' in clean_msg or 'total patients' in clean_msg:
            action_taken = 'Query Patient Analytics'
            total_patients = PatientProfile.objects.count()
            appts = Appointment.objects.all()
            total_appts = appts.count()
            pending_appts = appts.filter(status='Pending').count()
            cancelled_appts = appts.filter(status='Cancelled').count()
            completed_appts = appts.filter(status='Completed').count()

            result_summary = f"Returned patient analytics stats"
            response_html = f"""
            <div class="chat-custom-card patient-analytics-card">
                <div class="card-header"><i class="fas fa-users"></i> Patient & Appointments Analytics</div>
                <div class="card-body">
                    <div class="card-field"><span class="label">Total Unique Patients:</span> {total_patients}</div>
                    <div class="card-field"><span class="label">Total Appointments Booked:</span> {total_appts}</div>
                    <div class="card-field"><span class="label">Pending:</span> {pending_appts}</div>
                    <div class="card-field"><span class="label">Completed:</span> {completed_appts}</div>
                    <div class="card-field"><span class="label">Cancelled:</span> {cancelled_appts}</div>
                </div>
            </div>
            """

        # Doctor list
        elif 'inactive doctor' in clean_msg or 'top rated doctor' in clean_msg or 'cardiologist' in clean_msg:
            action_taken = 'Admin Doctor Management'
            if 'inactive' in clean_msg:
                docs = DoctorProfile.objects.filter(is_approved=False)
                title = "Inactive / Pending Approvals Doctors"
            elif 'top rated' in clean_msg:
                docs = DoctorProfile.objects.filter(is_approved=True).order_by('-rating')[:5]
                title = "Top Rated Specialists"
            else:
                docs = DoctorProfile.objects.filter(specialization__icontains='Cardiologist')
                title = "Cardiologists Department List"

            doc_rows = ""
            for doc in docs:
                status = "Approved" if doc.is_approved else "Pending Approval"
                doc_rows += f"<li>Dr. {doc.user.first_name} {doc.user.last_name} ({doc.doctor_id}) - {doc.specialization} ({status})</li>"

            result_summary = f"Returned {docs.count()} doctors for {title}"
            response_html = f"""
            <div class="chat-custom-card doctor-manage-card">
                <div class="card-header"><i class="fas fa-user-cog"></i> {title}</div>
                <div class="card-body">
                    <ul style="margin: 0; padding-left: 16px; font-size:12.5px; color: var(--text-muted);">{doc_rows if doc_rows else '<li>No matching doctors found.</li>'}</ul>
                </div>
            </div>
            """

        else:
            response_html = f"""
            <div class="welcome-card-premium" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 18px; padding: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.02); margin-bottom: 15px;">
                <h4 style="font-size: 18px; font-weight: 700; color: #2563EB; margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-user-shield"></i> Admin Portal AI 👋
                </h4>
                <p style="font-size: 14px; color: var(--text-main); margin: 0 0 10px 0;">Logged in as: <strong>Admin / Staff</strong>.</p>
                <p style="font-size: 13px; color: var(--text-muted); line-height: 1.4; margin: 0;">You have global analytics permissions. Type <i>"hospital analytics"</i> for revenue stats, <i>"patient analytics"</i> for appointment counts, or search any doctor ID (<i>"D101"</i>) or patient ID (<i>"P205"</i>).</p>
            </div>
            """

    # 3. AUDIT LOGGING RECORD
    AIAuditLog.objects.create(
        user=user,
        query=message_text,
        action=action_taken,
        result=result_summary,
        ip_address=ip_addr,
        device=user_agent
    )

    # Save bot message to history
    ChatMessage.objects.create(session=session, role='bot', content=response_html)

    return JsonResponse({
        'response': response_html,
        'session_id': str(session.session_id)
    })


@login_required
def api_chat_history(request):
    """
    AJAX endpoint to load message logs of a specific chat session.
    """
    session_id_str = request.GET.get('session_id', '')
    if not session_id_str:
        return JsonResponse({'error': 'session_id parameter is required.'}, status=400)
        
    session = get_object_or_404(ChatSession, session_id=session_id_str)
    
    # Secure ownership check: Strict ownership check for all roles and dashboard roles
    if session.user != request.user or session.assistant_role != request.user.role:
        return JsonResponse({'error': 'Unauthorized access.'}, status=403)

    msgs = session.messages.all().order_by('timestamp')
    history = []
    for m in msgs:
        history.append({
            'role': m.role,
            'content': m.content,
            'timestamp': m.timestamp.strftime('%I:%M %p')
        })

    return JsonResponse({
        'session_id': str(session.session_id),
        'messages': history
    })


@login_required
def api_sessions(request):
    """
    AJAX endpoint to return dynamic list of chat logs in sidebar.
    """
    # Secure session list check: Filter strictly by logged-in user and assistant role
    sessions = ChatSession.objects.filter(user=request.user, assistant_role=request.user.role).order_by('-started_at')

    data = []
    for s in sessions:
        first_msg = s.messages.filter(role='user').first()
        snippet = first_msg.content[:40] + "..." if first_msg else "New Health Consultation"
        data.append({
            'session_id': str(s.session_id),
            'started_at': s.started_at.strftime('%Y-%m-%d %I:%M %p'),
            'snippet': snippet
        })
    return JsonResponse({'sessions': data})
