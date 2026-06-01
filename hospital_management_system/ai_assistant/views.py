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

    # Setup context
    recent_sessions = []
    if request.user.role == 'patient' and patient:
        recent_sessions = ChatSession.objects.filter(patient=patient).order_by('-started_at')[:8]

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
        patient = getattr(user, 'patientprofile', None)
        if not patient:
            patient = PatientProfile.objects.create(user=user)
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
            if user.role == 'patient':
                session = ChatSession.objects.filter(patient=patient, session_id=session_id_str, is_active=True).first()
            else:
                session = ChatSession.objects.filter(session_id=session_id_str, is_active=True).first()
        except Exception:
            pass

    if not session:
        if user.role == 'patient' and patient:
            session = ChatSession.objects.create(patient=patient, is_active=True)
        else:
            # For non-patients, look up or create a dummy/admin session
            temp_patient = PatientProfile.objects.first()
            if not temp_patient:
                # Need at least one patient record to attach session
                return JsonResponse({'error': 'No patient profiles exist in the system.'}, status=400)
            session = ChatSession.objects.create(patient=temp_patient, is_active=True)

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

    # SECURITY SANITIZATION (Expose no other user's ID)
    # Check for other patient keywords
    security_flag = False
    if user.role == 'patient':
        # Check if user attempts to pass another patient's ID
        digit_ids = re.findall(r'\b\d{2,}\b', clean_msg)
        for d in digit_ids:
            if d != str(user.id) and d != str(patient.id):
                security_flag = True
                action_taken = 'Security Block'
                result_summary = 'User query blocked due to potential cross-patient access attempt'
                response_html = "<div class='chat-custom-card warning-card'><div class='card-header'><i class='fas fa-shield-alt'></i> Security Warning</div><div class='card-body'><p>Access denied. You are only authorized to query your own patient records.</p></div></div>"

    if security_flag:
        AIAuditLog.objects.create(
            user=user,
            query=message_text,
            action=action_taken,
            result=result_summary,
            ip_address=ip_addr,
            device=user_agent
        )
        ChatMessage.objects.create(session=session, role='bot', content=response_html)
        return JsonResponse({'response': response_html, 'session_id': str(session.session_id)})

    # ROUTING LOGIC:
    
    # 2a. APPOINTMENT QUERIES
    if any(k in clean_msg for k in ['previous appointment', 'last appointment', 'appointment history', 'past appointment']):
        action_taken = 'Query Appointment History'
        if user.role == 'patient':
            appts = Appointment.objects.filter(patient=patient).order_by('-appointment_date', '-appointment_time')
            if appts.exists():
                appt = appts.first()
                # Store doctor ID in memory
                memory['last_discussed_doctor_id'] = appt.doctor.id
                session.set_memory(memory)

                status_class = 'pending' if appt.status.lower() == 'pending' else 'success'
                result_summary = f"Returned last appointment ID {appt.id}"
                
                # Check for prescriptions or records associated
                presc_count = Prescription.objects.filter(appointment=appt).count()
                report_count = MedicalRecord.objects.filter(patient=patient, uploaded_at__date=appt.appointment_date).count()

                presc_text = "Available" if presc_count > 0 else "None Available"
                report_text = f"{report_count} Reports Available" if report_count > 0 else "None Available"

                response_html = f"""
                <div class="chat-custom-card appointment-card">
                    <div class="card-header"><i class="fas fa-calendar-check"></i> Previous Appointment Details</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Doctor:</span> Dr. {appt.doctor.user.first_name} {appt.doctor.user.last_name}</div>
                        <div class="card-field"><span class="label">Department:</span> {appt.doctor.department.name if appt.doctor.department else 'General Medicine'}</div>
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
                response_html = "<p>No previous appointments found in your account history.</p>"
        else:
            result_summary = "Blocked doctor/staff from querying previous patient appointments directly"
            response_html = "<p>Please search by a specific Patient ID to query appointment records.</p>"

    elif any(k in clean_msg for k in ['next appointment', 'upcoming appointment', 'future appointment']):
        action_taken = 'Query Upcoming Appointments'
        if user.role == 'patient':
            now_date = timezone.now().date()
            appts = Appointment.objects.filter(patient=patient, appointment_date__gte=now_date).order_by('appointment_date', 'appointment_time')
            if appts.exists():
                appt = appts.first()
                status_class = 'pending' if appt.status.lower() == 'pending' else 'success'
                result_summary = f"Returned next appointment ID {appt.id}"
                response_html = f"""
                <div class="chat-custom-card appointment-card">
                    <div class="card-header"><i class="fas fa-clock"></i> Next Scheduled Appointment</div>
                    <div class="card-body">
                        <div class="card-field"><span class="label">Doctor:</span> Dr. {appt.doctor.user.first_name} {appt.doctor.user.last_name}</div>
                        <div class="card-field"><span class="label">Department:</span> {appt.doctor.department.name if appt.doctor.department else 'General Medicine'}</div>
                        <div class="card-field"><span class="label">Date:</span> {appt.appointment_date.strftime('%B %d, %Y')}</div>
                        <div class="card-field"><span class="label">Time:</span> {appt.appointment_time}</div>
                        <div class="card-field"><span class="label">Status:</span> <span class="status-badge {status_class}">{appt.status}</span></div>
                    </div>
                </div>
                """
            else:
                result_summary = "No upcoming appointments"
                response_html = "<p>You have no upcoming scheduled appointments.</p>"
        else:
            response_html = "<p>Access limited. Patient role required to retrieve scheduled next appointments.</p>"

    # 2b. LAB REPORT / BLOOD TEST QUERIES
    elif any(k in clean_msg for k in ['blood test', 'lab report', 'blood report', 'reports', 'medical report']):
        action_taken = 'Query Lab Reports'
        if user.role == 'patient':
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
                response_html = "<p>No medical lab reports found in your records.</p>"
        else:
            response_html = "<p>Access denied. Triage reports can only be pulled for registered patient logins.</p>"

    # 2c. PRESCRIPTION QUERIES
    elif any(k in clean_msg for k in ['medicine', 'prescription', 'prescribed', 'medication']):
        action_taken = 'Query Prescription History'
        if user.role == 'patient':
            prescs = Prescription.objects.filter(patient=patient).order_by('-prescribed_date')
            if prescs.exists():
                pr = prescs.first()
                result_summary = f"Returned latest prescription ID {pr.id}"
                
                # Parse medicines list into rows
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
                response_html = "<p>No prescriptions have been issued to your account yet.</p>"
        else:
            response_html = "<p>Access restricted. You must log in as a patient to query your prescriptions.</p>"

    # 2d. PATIENT TIMELINE QUERY
    elif 'timeline' in clean_msg:
        action_taken = 'Query Patient Health Timeline'
        if user.role == 'patient':
            # Gather appointments, prescriptions, and reports
            timeline = []
            appts = Appointment.objects.filter(patient=patient).order_by('-appointment_date')[:5]
            for a in appts:
                timeline.append({
                    'date': timezone.make_aware(timezone.datetime.combine(a.appointment_date, timezone.datetime.min.time())),
                    'type': 'Appointment',
                    'title': f"Consultation with Dr. {a.doctor.user.last_name}",
                    'desc': f"Department: {a.doctor.department.name if a.doctor.department else 'General'}, Status: {a.status}"
                })

            records = MedicalRecord.objects.filter(patient=patient).order_by('-uploaded_at')[:5]
            for r in records:
                timeline.append({
                    'date': r.uploaded_at,
                    'type': 'Lab Report',
                    'title': f"Report Uploaded: {r.report_name}",
                    'desc': f"Type: {r.get_file_type_display()}, Source: {r.from_info}"
                })

            prescs = Prescription.objects.filter(patient=patient).order_by('-prescribed_date')[:5]
            for p in prescs:
                timeline.append({
                    'date': p.prescribed_date,
                    'type': 'Prescription',
                    'title': f"Prescription from Dr. {p.doctor.user.last_name}",
                    'desc': f"Diagnosis: {p.diagnosis[:40]}..."
                })

            # Sort timeline by date descending
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
                response_html = "<p>No entries available to compile your health timeline.</p>"
        else:
            response_html = "<p>Timeline requests are only authorized for patient profiles.</p>"

    # 2e. DOCTOR AVAILABILITY QUERY
    elif any(k in clean_msg for k in ['available', 'doctor schedule', 'cardiologist', 'physician', 'specialist']):
        action_taken = 'Query Doctor Availability'
        docs = DoctorProfile.objects.filter(is_online=True, is_approved=True)
        if 'cardiologist' in clean_msg:
            docs = docs.filter(department__name__icontains='Cardiology')
        elif 'physician' in clean_msg:
            docs = docs.filter(department__name__icontains='Physician')
            
        if docs.exists():
            doc_rows = ""
            for doc in docs[:4]:
                doc_rows += f"""
                <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 12px; padding: 12px; margin-bottom: 8px;">
                    <h6 style="margin: 0 0 4px 0; font-size: 13px; font-weight: bold; color: var(--text-main);">Dr. {doc.user.first_name} {doc.user.last_name}</h6>
                    <p style="margin: 0 0 6px 0; font-size: 11px; color: var(--text-muted);">{doc.department.name if doc.department else 'Specialist'} | Experience: {doc.experience_years if hasattr(doc, 'experience_years') else '10+'} yrs</p>
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px;">
                        <span style="font-size: 11px; color: #10B981; font-weight: bold;"><i class="fas fa-check-circle"></i> Available Tomorrow</span>
                        <button class="chat-btn" data-value="book_doc_{doc.id}" style="padding: 4px 10px; font-size: 11px; border-radius: 6px; background: #2563EB; border: none; color: white; font-weight: bold; cursor: pointer;">Book</button>
                    </div>
                </div>
                """
            result_summary = f"Returned {docs.count()} online doctors"
            response_html = f"""
            <div class="chat-custom-card doctor-card">
                <div class="card-header"><i class="fas fa-user-md"></i> Available Specialists</div>
                <div class="card-body" style="max-height: 250px; overflow-y: auto;">
                    {doc_rows}
                </div>
            </div>
            """
        else:
            result_summary = "No online doctors found"
            response_html = "<p>No specialist doctors are currently active for online booking in this department. Please check back later.</p>"

    # 2f. ICU BED & HOSPITAL RESOURCES
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

    # 2g. FALLBACK FOR SYMPTOM EXTRACTION OR GENERAL BOT RESPONSE
    else:
        se = get_symptom_engine()
        extracted_symptoms = se.extract_symptoms(message_text)
        
        if extracted_symptoms:
            # Map symptom to Department
            sympt = extracted_symptoms[0]['name']
            mapped_dept_name = 'General Physician'
            
            # Search for department matching category
            cat_map = {
                'cardiovascular': 'Cardiology',
                'dermatological': 'Dermatology',
                'ophthalmological': 'Ophthalmology',
                'ent': 'ENT',
                'dental': 'Dental',
                'musculoskeletal': 'Orthopedics',
                'gynecological': 'Gynecology',
                'pediatric': 'Pediatrics',
                'psychiatric': 'Psychiatry',
                'gastrointestinal': 'Gastroenterology',
                'renal': 'Nephrology',
                'respiratory': 'Pulmonology'
            }
            mapped_cat = cat_map.get(extracted_symptoms[0]['category'], 'General Physician')
            
            dept = Department.objects.filter(name__icontains=mapped_cat).first()
            dept_name = dept.name if dept else 'General Physician'
            
            # Doctor match list
            docs = DoctorProfile.objects.filter(department__name__icontains=dept_name, is_approved=True)
            doc_cards = ""
            for doc in docs[:3]:
                doc_cards += f"""
                <div style="background: white; border: 1px solid var(--border-color); border-radius: 12px; padding: 12px; margin-bottom: 8px; color: var(--text-main);">
                    <h6 style="margin: 0; font-size: 13.0px; font-weight: bold;">Dr. {doc.user.first_name} {doc.user.last_name}</h6>
                    <p style="margin: 2px 0; font-size: 11px; color: var(--text-muted);">{doc.department.name} | Fee: ${doc.consultation_fee if hasattr(doc, 'consultation_fee') else '100.00'}</p>
                    <div style="text-align: right; margin-top: 6px;">
                        <button class="chat-btn" data-value="book_doc_{doc.id}" style="padding: 4px 10px; font-size: 11px; border-radius: 6px; background: #2563EB; color: white; border: none; font-weight: bold; cursor: pointer;">Book Session</button>
                    </div>
                </div>
                """

            action_taken = 'Extracted Symptoms & Suggested Specialist'
            result_summary = f"Extracted: {[s['name'] for s in extracted_symptoms]}, Mapped to Department: {dept_name}"
            
            response_html = f"""
            <div class="chat-custom-card symptom-result-card">
                <div class="card-header"><i class="fas fa-stethoscope"></i> Symptom Analysis Result</div>
                <div class="card-body">
                    <p style="margin: 0 0 10px 0; font-size: 13px; color: var(--text-main);">Based on the symptoms described (<strong>{sympt}</strong>), consulting a specialist in <strong>{dept_name}</strong> is recommended.</p>
                    { f"<div style='margin-top: 10px;'><strong>Suitables Doctors:</strong></div><div style='margin-top: 6px;'>{doc_cards}</div>" if doc_cards else "<p style='font-size:11.5px; color:var(--text-muted);'>No active specialists available for booking in this department at the moment.</p>" }
                    <p style="font-size: 11px; color: var(--text-muted); font-style: italic; border-top: 1px solid var(--border-color); padding-top: 8px; margin-top: 10px;">
                        ⚠️ Disclaimer: I am not a doctor. I cannot diagnose diseases or prescribe medications. Please consult a doctor for proper medical evaluation.
                    </p>
                </div>
            </div>
            """
        else:
            # Fallback Greeting card
            response_html = f"""
            <div class="welcome-card-premium" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 18px; padding: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.02); margin-bottom: 15px;">
                <h4 style="font-size: 18px; font-weight: 700; color: #2563EB; margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-robot"></i> Hello 👋
                </h4>
                <p style="font-size: 14px; color: var(--text-main); margin: 0 0 10px 0;">I am your intelligent <strong>Medicare AI Healthcare Assistant</strong>.</p>
                <p style="font-size: 13px; color: var(--text-muted); line-height: 1.4; margin: 0;">You can query your records, view appointments, list prescriptions, or search for doctor availability. Try typing "Show my previous appointment", "Show my blood test", or describe symptoms directly.</p>
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
    
    # Secure ownership check
    if request.user.role == 'patient' and session.patient.user != request.user:
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
    if request.user.role == 'patient':
        patient = getattr(request.user, 'patientprofile', None)
        if not patient:
            return JsonResponse({'sessions': []})
        sessions = ChatSession.objects.filter(patient=patient).order_by('-started_at')
    else:
        sessions = ChatSession.objects.all().order_by('-started_at')[:10]

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
