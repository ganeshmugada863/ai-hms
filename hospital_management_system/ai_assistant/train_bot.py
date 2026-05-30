import os
import csv
import json
import re
import numpy as np
from django.utils import timezone
from django.conf import settings

from ai_assistant.language_detector import LanguageDetector
from ai_assistant.symptom_engine import SymptomEngine
from ai_assistant.risk_engine import RiskEngine
from ai_assistant.memory_engine import MemoryEngine

class ChatBot:
    def __init__(self):
        self.ld = LanguageDetector()
        self.se = SymptomEngine()
        self.re = RiskEngine()
        self.me = MemoryEngine()
        
        self.diseases = []
        self.medicines = []
        self.disease_model = None
        self.disease_model_loaded = False
        
        self._load_datasets()
        self._load_disease_model()

    def _load_datasets(self):
        # Load diseases detail
        current_dir = os.path.dirname(os.path.abspath(__file__))
        diseases_path = os.path.join(current_dir, 'datasets', 'diseases.csv')
        if os.path.exists(diseases_path):
            with open(diseases_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.diseases.append({
                        'name': row.get('disease_name', '').strip().lower(),
                        'name_te': row.get('disease_name_te', '').strip(),
                        'symptoms': [s.strip().lower() for s in row.get('common_symptoms', '').split(',') if s.strip()],
                        'department': row.get('department', '').strip(),
                        'severity': row.get('severity', 'medium').strip().lower(),
                        'description': row.get('description', '').strip(),
                        'tests': row.get('recommended_tests', '').strip(),
                        'treatment': row.get('treatment_overview', '').strip()
                    })
                    
        # Load medicines detail
        medicines_path = os.path.join(current_dir, 'datasets', 'medicines.csv')
        if os.path.exists(medicines_path):
            with open(medicines_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Target diseases list
                    t_diseases = [d.strip().lower() for d in row.get('disease', '').split(',') if d.strip()]
                    self.medicines.append({
                        'name': row.get('medicine_name', '').strip(),
                        'diseases': t_diseases,
                        'dosage': row.get('dosage', '').strip(),
                        'side_effects': row.get('side_effects', '').strip(),
                        'contraindications': row.get('contraindications', '').strip()
                    })

    def _load_disease_model(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, 'models', 'disease_model.h5')
        if os.path.exists(model_path):
            try:
                import tensorflow as tf
                self.disease_model = tf.keras.models.load_model(model_path)
                self.disease_model_loaded = True
            except Exception as e:
                print(f"Warning: Failed to load disease_model.h5: {e}. Using Jaccard similarity fallback.")
                self.disease_model = None

    def _check_security_violation(self, message: str, patient) -> bool:
        msg_clean = message.lower().strip()
        
        # Look for digit sequences representing IDs or phone numbers
        digit_sequences = re.findall(r'\b\d+\b', msg_clean)
        patient_id = str(patient.id)
        patient_user_id = str(patient.user.id)
        patient_phone = str(patient.emergency_contact or '').replace('-', '').replace(' ', '')
        
        for digits in digit_sequences:
            if len(digits) >= 1:
                if digits != patient_id and digits != patient_user_id and digits not in patient_phone:
                    # Access attempt keyword checks
                    keywords = ['patient', 'history', 'profile', 'record', 'details', 'visit', 'show', 'view', 'check', 'get']
                    if any(kw in msg_clean for kw in keywords) or 'id' in msg_clean or 'phone' in msg_clean:
                        return True
                        
        # Explicit requests referencing other patients/people
        other_patient_indicators = [
            'other patient', 'another patient', 'someone else', "doctor's patient",
            'history of patient', 'details of patient', 'profile of patient'
        ]
        if any(ind in msg_clean for ind in other_patient_indicators):
            return True
            
        return False

    def process_message(self, patient, message: str, session) -> dict:
        """
        Main pipeline orchestrator implementing the MediBot state-based consultation workflow.
        """
        from ai_assistant.models import ChatMessage, SymptomEntry, DiseasePrediction
        from doctors.models import DoctorProfile
        from appointments.models import Appointment
        from consultations.models import Consultation
        import logging
        
        # Central logging of all patient interactions
        logger = logging.getLogger(__name__)
        logger.info(f"Interaction Log: Patient ID: {patient.id}, Session ID: {session.session_id}, Message: '{message}'")
        
        # 1. Language Detection
        lang = self.ld.detect(message)
        session.language = lang
        session.save()
        
        # Translate message to English for NLP processing if Telugu
        english_message = message if lang == 'en' else self.ld.translate_to_english(message)
        
        # Save user message to database
        user_msg = ChatMessage.objects.create(
            session=session,
            role='user',
            content=message,
            translated_content=english_message
        )
        
        # Load or initialize session state
        state_dict = session.predicted_diseases if isinstance(session.predicted_diseases, dict) else {}
        current_state = state_dict.get('state', None)
        
        # Helper lists for positive/negative replies
        positive_replies = ['yes', 'yeah', 'y', 'yup', 'avunu', 'avnu', 'ha', 'sare', 'ok', 'okay', 'అవును', 'సరే', 'హా']
        negative_replies = ['no', 'n', 'nope', 'nah', 'ledu', 'kaadu', 'kadu', 'లేదు', 'కాదు', 'వద్దు']
        
        clean_msg = english_message.lower().strip()
        is_yes = clean_msg in positive_replies or any(w in positive_replies for w in clean_msg.split())
        is_no = clean_msg in negative_replies or any(w in negative_replies for w in clean_msg.split())
        
        disclaimer = "I am not a doctor. I cannot diagnose diseases or prescribe medicines. This is general guidance only. Please consult a qualified doctor for proper medical evaluation."
        
        # ==========================================
        # STATE MACHINE TRANSITIONS
        # ==========================================
        
        # STATE: awaiting_verification
        if current_state == 'awaiting_verification':
            patient_id = str(patient.id)
            phone = str(patient.emergency_contact or '').replace('-', '').replace(' ', '')
            clean_input = clean_msg.replace('-', '').replace(' ', '')
            
            if clean_input == patient_id or clean_input in phone or clean_input == str(patient.user.id):
                state_dict['verified'] = True
                state_dict['state'] = None
                session.predicted_diseases = state_dict
                session.save()
                
                resp = (
                    f"Verification success! Mee profile details 📋:\n"
                    f"- **Name:** {patient.user.first_name} {patient.user.last_name}\n"
                    f"- **Age:** {patient.age} years\n"
                    f"- **Gender:** {patient.gender}\n"
                    f"- **Blood Group:** {patient.blood_group}\n"
                    f"- **Medical History:** {patient.medical_history or 'None registered'}\n"
                    f"- **Emergency Contact:** {patient.emergency_contact}\n\n"
                    f"Mee details safety and security control lo vunnayi. Only registered doctors and you can access them."
                )
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
            else:
                logger.warning(f"Security Alert / Verification Failure: User {patient.user.username} (ID {patient.id}) entered non-matching verification code: '{message}'")
                resp = "Security reasons valla nenu ee information ivvalenu. Hospital staff tho contact cheyandi."
                
                state_dict['state'] = None
                session.predicted_diseases = state_dict
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}

        # STATE: awaiting_permission
        elif current_state == 'awaiting_permission':
            if is_yes:
                dept_name = state_dict.get('department', 'General Medicine')
                # Suggest highly rated doctors
                docs = DoctorProfile.objects.filter(specialization__icontains=dept_name.split()[0], is_approved=True).order_by('-rating', '-reviews', '-experience')
                if not docs.exists():
                    docs = DoctorProfile.objects.filter(is_approved=True).order_by('-rating', '-reviews', '-experience')
                
                # Render Doctor Cards in HTML
                doc_html = '<div class="doctor-cards-container">'
                for d in docs[:5]:
                    doc_html += f"""
                    <div class="doctor-card">
                        <div class="doc-card-body">
                            <h5>Dr. {d.user.first_name} {d.user.last_name}</h5>
                            <p class="specialization"><strong>Specialization:</strong> {d.specialization}</p>
                            <p class="rating">⭐ {d.rating:.1f}/5 ({d.reviews} reviews)</p>
                            <p class="experience"><strong>Experience:</strong> {d.experience} years</p>
                            <button class="chat-btn select-doctor-btn" data-value="select_doctor_{d.id}" data-display="Select Dr. {d.user.last_name}">[Select]</button>
                        </div>
                    </div>
                    """
                doc_html += '</div>'
                
                resp = (
                    "Here are the highly-rated doctors in our hospital matching your symptoms:" if lang == 'en'
                    else "మీ లక్షణాలకు సరిపోయే మా ఆసుపత్రిలోని అత్యుత్తమ వైద్యులు ఇక్కడ ఉన్నారు:"
                )
                resp += f"\n\n{doc_html}"
                
                state_dict['state'] = 'awaiting_doctor_selection'
                session.predicted_diseases = state_dict
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
                
            elif is_no:
                resp = (
                    f"Understood. If you feel worse or experience severe symptoms, please seek direct medical attention. Let me know if you need anything else!\n\n*{disclaimer}*"
                )
                session.predicted_diseases = {}
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
        
        # STATE: awaiting_doctor_selection
        elif current_state == 'awaiting_doctor_selection':
            doctor = None
            if clean_msg.startswith('select_doctor_'):
                try:
                    doc_id = int(clean_msg.replace('select_doctor_', '').strip())
                    doctor = DoctorProfile.objects.filter(id=doc_id).first()
                except Exception:
                    pass
            else:
                # Search by typed doctor name or username
                docs = DoctorProfile.objects.filter(is_approved=True)
                words = clean_msg.split()
                for d in docs:
                    un = d.user.username.lower()
                    fn = d.user.first_name.lower()
                    ln = d.user.last_name.lower()
                    full_name = f"{fn} {ln}"
                    
                    if full_name in clean_msg or fn in clean_msg or ln in clean_msg or un in clean_msg:
                        doctor = d
                        break
                    
                    if any(w in fn or w in ln or fn in w or ln in w or w in un or un in w for w in words if len(w) >= 3):
                        doctor = d
                        break
            
            if doctor:
                resp = (
                    f"You selected **Dr. {doctor.user.first_name} {doctor.user.last_name}**.\n\n"
                    "MediBot support formats options to connect with the doctor. How would you like to continue?\n\n"
                    '<div class="preference-actions">'
                    '<button class="chat-btn pref-btn btn-danger" data-value="pref_emergency" data-display="[Emergency]">🚨 Emergency</button>'
                    '<button class="chat-btn pref-btn btn-primary" data-value="pref_meet_doctor" data-display="[Meet Doctor]">📅 Meet Doctor</button>'
                    '<button class="chat-btn pref-btn btn-success" data-value="pref_video_call" data-display="[Video Call]">🎥 Video Call</button>'
                    '<button class="chat-btn pref-btn btn-info" data-value="pref_voice_call" data-display="[Voice Call]">📞 Voice Call</button>'
                    '<button class="chat-btn pref-btn btn-secondary" data-value="pref_chat" data-display="[Chat]">💬 Chat</button>'
                    '</div>'
                )
                
                state_dict['state'] = 'awaiting_preference_selection'
                state_dict['doctor_id'] = doctor.id
                session.predicted_diseases = state_dict
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
            else:
                resp = (
                    "Please select one of the doctors from the cards above by clicking [Select], or type the doctor's name correctly (e.g., 'Srinivas Rao')."
                    if lang == 'en' else
                    "దయచేసి పైన ఉన్న కార్డ్‌ల నుండి ఒక వైద్యుడిని ఎంచుకోండి లేదా వైద్యుడి పేరును సరిగ్గా టైప్ చేయండి (ఉదాహరణకు, 'Srinivas Rao')."
                )
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
        
        # STATE: awaiting_preference_selection
        elif current_state == 'awaiting_preference_selection':
            doc_id = state_dict.get('doctor_id')
            doctor = DoctorProfile.objects.get(id=doc_id)
            
            if clean_msg == 'pref_emergency':
                # Prioritize nearest available doctors
                resp = (
                    f"🚨 **Emergency mode activated.**\n\n"
                    f"We have notified **Dr. {doctor.user.first_name} {doctor.user.last_name}** and the nearest medical on-duty staff. "
                    f"A doctor is coming online immediately. Please stay calm and keep your browser window open.\n\n"
                    f"*{disclaimer}*"
                )
                
                # Save consultation
                Consultation.objects.create(
                    patient=patient,
                    doctor=doctor,
                    consultation_type='video',
                    status='ongoing',
                    scheduled_date=timezone.now(),
                    notes="Emergency consultation initialized via AI chatbot."
                )
                
                session.predicted_diseases = {}
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
                
            elif clean_msg == 'pref_meet_doctor':
                # Render appointment booking form
                extracted_symptoms_list = ", ".join(session.extracted_symptoms) if session.extracted_symptoms else "Symptom checkup"
                form_html = f"""
                <div class="appointment-form-card">
                    <h5>Book Physical Appointment</h5>
                    <form class="interactive-booking-form" onsubmit="event.preventDefault(); submitBookingForm(this);">
                        <div class="form-group">
                            <label>Patient Name:</label>
                            <input type="text" name="name" value="{patient.user.first_name} {patient.user.last_name}" required>
                        </div>
                        <div class="form-group">
                            <label>Age:</label>
                            <input type="number" name="age" value="{patient.age}" required>
                        </div>
                        <div class="form-group">
                            <label>Appointment Date:</label>
                            <input type="date" name="date" required>
                        </div>
                        <div class="form-group">
                            <label>Preferred Time:</label>
                            <input type="time" name="time" required>
                        </div>
                        <div class="form-group">
                            <label>Problem Summary:</label>
                            <textarea name="summary" required>{extracted_symptoms_list}</textarea>
                        </div>
                        <input type="hidden" name="doctor_id" value="{doc_id}">
                        <button type="submit" class="submit-booking-btn">Submit Booking</button>
                    </form>
                </div>
                """
                resp = (
                    "Please fill out this appointment form to meet the doctor in person:"
                    if lang == 'en' else
                    "వైద్యుడిని వ్యక్తిగతంగా కలవడానికి దయచేసి ఈ అపాయింట్‌మెంట్ ఫారమ్‌ను పూరించండి:"
                )
                resp += f"\n\n{form_html}"
                
                state_dict['state'] = 'awaiting_booking_form'
                session.predicted_diseases = state_dict
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
                
            elif clean_msg == 'pref_video_call':
                # Open Video Call room console
                video_html = f"""
                <div class="video-room-console">
                    <div class="video-screen">
                        <div class="remote-video">
                            <i class="fas fa-user-md placeholder-avatar"></i>
                            <span>Dr. {doctor.user.last_name} Video Feed (Awaiting connection...)</span>
                        </div>
                        <div class="local-video">
                            <video id="localVideoFeed" autoplay muted style="width:100%; height:100%; object-fit:cover; display:none;"></video>
                            <div class="local-video-placeholder"><span>Patient (You)</span></div>
                        </div>
                    </div>
                    <div class="video-controls-row">
                        <button class="control-btn active" onclick="toggleCameraControl(this)"><i class="fas fa-video"></i> Camera On</button>
                        <button class="control-btn active" onclick="toggleMicControl(this)"><i class="fas fa-microphone"></i> Mic On</button>
                        <button class="control-btn" onclick="toggleScreenShareControl(this)"><i class="fas fa-desktop"></i> Share Screen</button>
                        <button class="control-btn btn-danger" onclick="endConsultationCall(this, 'video')"><i class="fas fa-phone-slash"></i> End</button>
                    </div>
                    <div class="media-upload-section">
                        <h6>Secure Media Upload Panel (Only Dr. {doctor.user.last_name} can view)</h6>
                        <div class="upload-buttons">
                            <button onclick="triggerDirectUpload()"><i class="fas fa-file-upload"></i> Upload Image / Report PDF</button>
                        </div>
                    </div>
                    <div class="console-chat-section">
                        <h6>Console Message Log</h6>
                        <div class="console-chat-box">
                            <p class="system-msg">Video session initialized. Central Django channels open.</p>
                        </div>
                    </div>
                </div>
                """
                resp = (
                    f"Starting **Video Consultation** with **Dr. {doctor.user.first_name} {doctor.user.last_name}**:\n\n"
                    f"**Camera and Screen Sharing Guide:**\n"
                    f"- Camera allow cheyyataniki controls visual toggle check cheyyandi.\n"
                    f"- Screen sharing enable cheyyali ante desktop display icon button ni press cheyyandi.\n"
                    f"- Mee video connection is established via a secure end-to-end encrypted tunnel.\n"
                    f"- Mee media files uploads attachments system dwara auto secure path lo store cheyabadutundi.\n\n"
                    f"*{disclaimer}*"
                )
                resp += f"\n\n{video_html}"
                
                Consultation.objects.create(
                    patient=patient,
                    doctor=doctor,
                    consultation_type='video',
                    status='ongoing',
                    scheduled_date=timezone.now(),
                    notes="Video consultation session started."
                )
                
                # Clear active flow state but keep doctor linked
                session.predicted_diseases = {'doctor_id': doc_id}
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
                
            elif clean_msg == 'pref_voice_call':
                voice_html = f"""
                <div class="video-room-console voice-only">
                    <div class="voice-screen">
                        <i class="fas fa-phone-volume pulsing-icon"></i>
                        <span>Active Voice Session with Dr. {doctor.user.last_name}</span>
                    </div>
                    <div class="video-controls-row">
                        <button class="control-btn active" onclick="toggleMicControl(this)"><i class="fas fa-microphone"></i> Mic On</button>
                        <button class="control-btn btn-danger" onclick="endConsultationCall(this, 'audio')"><i class="fas fa-phone-slash"></i> Hang Up</button>
                    </div>
                </div>
                """
                resp = (
                    f"Connecting **Voice Call** with **Dr. {doctor.user.first_name} {doctor.user.last_name}**...\n\n"
                    f"Mee voice connection is established via a secure end-to-end encrypted tunnel.\n"
                    f"Mee session logs database log storage dashboard check block automatic saving processes start chesayi.\n\n"
                    f"*{disclaimer}*"
                )
                resp += f"\n\n{voice_html}"
                
                Consultation.objects.create(
                    patient=patient,
                    doctor=doctor,
                    consultation_type='audio',
                    status='ongoing',
                    scheduled_date=timezone.now(),
                    notes="Voice consultation session started."
                )
                
                session.predicted_diseases = {'doctor_id': doc_id}
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
                
            elif clean_msg == 'pref_chat':
                chat_html = f"""
                <div class="doctor-chat-console">
                    <div class="chat-header">💬 Chat Room: Dr. {doctor.user.first_name} {doctor.user.last_name}</div>
                    <div class="chat-messages-log">
                        <p class="system-msg">Secure chat session opened. Message logs save centrally in Django Consultation history.</p>
                    </div>
                </div>
                """
                resp = (
                    f"Chat session opened with **Dr. {doctor.user.first_name} {doctor.user.last_name}**:\n\n"
                    f"Mee chat connection is established via a secure end-to-end encrypted tunnel.\n"
                    f"Mee messages metadata only assigned doctor and administrative audit panel visual status block matches.\n\n"
                    f"*{disclaimer}*"
                )
                resp += f"\n\n{chat_html}"
                
                Consultation.objects.create(
                    patient=patient,
                    doctor=doctor,
                    consultation_type='chat',
                    status='ongoing',
                    scheduled_date=timezone.now(),
                    notes="Chat consultation session started."
                )
                
                session.predicted_diseases = {'doctor_id': doc_id}
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
        
        # STATE: awaiting_booking_form (JSON form submission)
        elif current_state == 'awaiting_booking_form' and clean_msg.startswith('{') and 'date' in clean_msg:
            try:
                form_data = json.loads(message)
                doc_id = state_dict.get('doctor_id')
                doctor = DoctorProfile.objects.get(id=doc_id)
                
                # Create Appointment
                appt = Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    appointment_date=form_data.get('date'),
                    appointment_time=form_data.get('time'),
                    reason=form_data.get('summary', 'Symptom consult booked via MediBot'),
                    status='Approved'
                )
                
                resp = (
                    f"✓ **Appointment successfully booked with Dr. {doctor.user.first_name} {doctor.user.last_name}!**\n\n"
                    f"**Date:** {appt.appointment_date}\n"
                    f"**Time:** {appt.appointment_time}\n"
                    f"Please arrive 15 minutes before your scheduled slot. Thank you!\n\n"
                    f"*{disclaimer}*"
                )
                
                session.predicted_diseases = {}
                session.save()
                
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}
            except Exception as e:
                print(f"Error booking appointment: {e}")

        # ==========================================
        # GENERAL MEDIBOT TRIGGERS (Natural Queries)
        # ==========================================
        
        # Check security violation first
        if self._check_security_violation(message, patient):
            logger.warning(f"Security Alert: User {patient.user.username} (ID {patient.id}) attempted unauthorized access with query: '{message}'")
            resp = "Security reasons valla nenu ee information ivvalenu. Hospital staff tho contact cheyandi."
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}
        
        # GREETINGS
        if any(w in clean_msg.split() for w in ['hello', 'hi', 'hey', 'namaste']) or any(w in clean_msg for w in ['నమస్కారం', 'నమస్తే']):
            resp = (
                "Hello! 👋 I am your **HMS AI Medical Appointment Assistant** 🏥.\n\n"
                "I can help you:\n"
                "• Describe your symptoms\n"
                "• Find the right specialist doctor\n"
                "• Book appointments\n\n"
                "Please describe your symptoms or health concern, and I will recommend the appropriate specialist for you."
            )
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}

        # PATIENT PERSONAL PROFILE AND HISTORY REQUESTS
        if any(w in clean_msg for w in ['my history', 'my record', 'my details', 'visit history', 'show profile', 'my profile']):
            if state_dict.get('verified') == True:
                resp = (
                    f"Here is your patient details profile:\n"
                    f"- **Name:** {patient.user.first_name} {patient.user.last_name}\n"
                    f"- **Age:** {patient.age} years\n"
                    f"- **Gender:** {patient.gender}\n"
                    f"- **Blood Group:** {patient.blood_group}\n"
                    f"- **Medical History:** {patient.medical_history or 'None registered'}\n"
                    f"- **Emergency Contact:** {patient.emergency_contact}"
                )
            else:
                # Require verification
                state_dict['state'] = 'awaiting_verification'
                session.predicted_diseases = state_dict
                session.save()
                resp = "Mee confidential patient records check details view privacy reasons valla please confirm your patient ID code or emergency phone number code to verify."
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}

        # Check RAG before general fallbacks
        from ai_assistant.rag_engine import RAGEngine
        rag = RAGEngine()
        rag_match = rag.search_kb(english_message)
        if rag_match:
            ChatMessage.objects.create(session=session, role='bot', content=rag_match)
            return {'response': rag_match, 'analysis': None}

        # SYSTEM CHARTS SUMMARY
        if any(w in clean_msg for w in ['chart', 'charts', 'report statistics', 'revenue statistics', 'analytics']):
            resp = (
                "MediBot matches 3 charts currently setup in your Django home admin panel 📊:\n"
                "1. **Monthly Revenue Trend Chart**: Tracks hospital billings and incoming consult fees.\n"
                "2. **Department Patient Distribution**: Displays incoming patient volume mapped to each medical unit.\n"
                "3. **Doctor Ratings Summary**: Visualizes doctor reviews and performance scores.\n\n"
                "Mee dashboard check dashboard panels link direct details direct check cheyyandi!"
            )
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}

        # DJANGO FORMS ROUTING
        if any(w in clean_msg for w in ['form', 'forms', 'registration', 'register profile', 'profile form']):
            resp = (
                "Maa hospital registration options matching list 📋:\n"
                "- **Patient Profile Creation**: [/patients/create-profile/](/patients/create-profile/)\n"
                "- **Interactive Booking Portal**: [/appointments/book/](/appointments/book/)\n"
                "Links click chesi direct forms details fill cheyandi."
            )
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}

        # APPOINTMENTS HANDLING
        if any(w in clean_msg for w in ['book appointment', 'appointment dates', 'doctor consult', 'appointment book']):
            resp = (
                "Appointment book details process modal. You can book using the [Appointment Booking Form](/appointments/book/) "
                "or let me search doctors here. Department or specialization name cheppandi!"
            )
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}

        # DOCTOR AVAILABILITY
        if any(w in clean_msg for w in ['doctor', 'doctors', 'specialist', 'specialists', 'available doctors', 'availability']):
            docs = DoctorProfile.objects.filter(is_approved=True).order_by('-rating')
            if docs.exists():
                doc_html = '<div class="doctor-cards-container">'
                for d in docs[:5]:
                    doc_html += f"""
                    <div class="doctor-card">
                        <div class="doc-card-body">
                            <h5>Dr. {d.user.first_name} {d.user.last_name}</h5>
                            <p class="specialization"><strong>Specialization:</strong> {d.specialization}</p>
                            <p class="rating">⭐ {d.rating:.1f}/5 ({d.reviews} reviews)</p>
                            <p class="experience"><strong>Experience:</strong> {d.experience} years</p>
                            <button class="chat-btn select-doctor-btn" data-value="select_doctor_{d.id}" data-display="Select Dr. {d.user.last_name}">[Select]</button>
                        </div>
                    </div>
                    """
                doc_html += '</div>'
                
                resp = (
                    "Approved available doctors list matching database 🩺:\n\n"
                    f"{doc_html}\n\n"
                    f"Evaritho connect cheyali? Cheppandi. \n\n*{disclaimer}*"
                )
                state_dict['state'] = 'awaiting_doctor_selection'
                session.predicted_diseases = state_dict
                session.save()
            else:
                resp = f"No doctors currently active in the database. General hospital visits suggest desk. \n\n*{disclaimer}*"
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}

        # OUT OF HMS SCOPE
        if any(w in clean_msg for w in ['weather', 'news', 'sports', 'movies', 'politics', 'joke', 'song']):
            resp = "Idi Hospital Management System (HMS) related query kadu. Please visit front desk or main desk for other inquiries."
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}

        # ==========================================
        # DEFAULT CLINICAL SYMPTOM FLOW
        # ==========================================
        
        # Check conversational queries fallback
        is_greeting_or_farewell = self._check_conversational_dataset(clean_msg, lang)
        if is_greeting_or_farewell:
            ChatMessage.objects.create(session=session, role='bot', content=is_greeting_or_farewell)
            return {'response': is_greeting_or_farewell, 'analysis': None}
            
        # Extract symptoms
        extracted = self.se.extract_symptoms(english_message)
        
        if not extracted:
            resp = (
                "Hello! I can help you find the right doctor and book an appointment. 🏥\n\n"
                "Please describe your symptoms or health concern. For example:\n"
                "• 'I have chest pain and difficulty breathing'\n"
                "• 'I have a skin rash for 3 days'\n"
                "• 'My child has fever and cough'\n\n"
                f"*{disclaimer}*"
            )
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}
            
        # Save symptoms to DB & Cache
        current_symptoms = [s['name'] for s in extracted]
        session.extracted_symptoms = current_symptoms
        session.save()
        
        for item in extracted:
            SymptomEntry.objects.create(
                message=user_msg,
                symptom_name=item['name'],
                symptom_name_te=self.ld.translate_to_telugu(item['name']),
                confidence=item['confidence'],
                category=item['category']
            )
            
        # Check HMS History
        history_banner = ""
        if patient:
            history_elements = []
            if patient.medical_history:
                history_elements.append(f"history of {patient.medical_history}")
            
            # Check past completed appointments
            past_visits = Appointment.objects.filter(patient=patient, status='Completed').order_by('-appointment_date')[:2]
            if past_visits.exists():
                visits_str = ", ".join([f"Dr. {v.doctor.user.last_name} ({v.appointment_date})" for v in past_visits])
                history_elements.append(f"visits with {visits_str}")
                
            if history_elements:
                history_banner = f"*(Patient background: {', '.join(history_elements)})*\n\n"
                
        # Format Symptom Definitions & Health Area
        symptom_list_str = "Symptom check evaluation results:\n"
        for s in current_symptoms:
            symptom_list_str += f"✓ {s.capitalize()}\n"
            
        symptom_definitions = "\nAbout symptoms:\n"
        for item in extracted:
            desc = item.get('description', '')
            if not desc:
                for sym_ref in self.se.symptoms:
                    if sym_ref['name'] == item['name']:
                        desc = sym_ref['description']
                        break
            if not desc:
                desc = f"Refers to feelings of {item['name']}."
            symptom_definitions += f"- **{item['name'].capitalize()}**: {desc}\n"
            
        categories_extracted = list(set([item['category'] for item in extracted]))
        health_area = "General Physician"
        if 'neurological' in categories_extracted:
            health_area = "Neurology"
        elif 'cardiovascular' in categories_extracted:
            health_area = "Cardiology"
        elif 'respiratory' in categories_extracted:
            health_area = "Pulmonology"
        elif 'gastrointestinal' in categories_extracted:
            health_area = "Gastroenterology"
        elif 'dermatological' in categories_extracted or 'skin' in categories_extracted:
            health_area = "Dermatology"
        elif 'musculoskeletal' in categories_extracted or 'orthopedic' in categories_extracted:
            health_area = "Orthopedics"
        elif 'ophthalmological' in categories_extracted or 'eye' in categories_extracted:
            health_area = "Ophthalmology"
        elif 'ent' in categories_extracted or 'ear' in categories_extracted:
            health_area = "ENT"
        elif 'psychiatric' in categories_extracted or 'mental' in categories_extracted:
            health_area = "Psychiatry"
        elif 'pediatric' in categories_extracted:
            health_area = "Pediatrics"
        elif 'gynecological' in categories_extracted:
            health_area = "Gynecology"
        elif 'renal' in categories_extracted or 'kidney' in categories_extracted:
            health_area = "Nephrology"
        elif 'endocrine' in categories_extracted or 'hormonal' in categories_extracted:
            health_area = "Endocrinology"
        elif 'rheumatological' in categories_extracted or 'joint' in categories_extracted:
            health_area = "Rheumatology"
        elif 'dental' in categories_extracted or 'tooth' in categories_extracted:
            health_area = "Dental"
            
        area_explanation = (
            f"\nThese symptoms map to **{health_area}** department conditions.\n"
            f"Would you like me to suggest doctors related to your symptoms?\n\n"
            '<div class="chat-actions">'
            '<button class="chat-btn btn-yes" data-value="Yes" data-display="Yes">Yes</button>'
            '<button class="chat-btn btn-no" data-value="No" data-display="No">No</button>'
            '</div>'
        )
        
        full_response = f"{history_banner}{symptom_list_str}{symptom_definitions}\n*{disclaimer}*{area_explanation}"
        
        # Save state: awaiting_permission
        session.predicted_diseases = {
            'state': 'awaiting_permission',
            'symptoms': current_symptoms,
            'department': health_area
        }
        session.save()
        
        ChatMessage.objects.create(session=session, role='bot', content=full_response)
        
        analysis_data = {
            'symptoms': current_symptoms,
            'risk_level': 'none',
            'allergy_alerts': []
        }
        
        return {'response': full_response, 'analysis': analysis_data}
        


    def _predict_disease(self, active_symptoms: list) -> dict:
        """
        Predict disease using TensorFlow model if loaded, fallback to Jaccard heuristic.
        """
        if not active_symptoms:
            return None
            
        symptom_to_idx = {s['name']: idx for idx, s in enumerate(self.se.symptoms)}
        
        if self.disease_model_loaded and self.disease_model is not None:
            try:
                # Prepare binary symptom vector
                vec = np.zeros(len(self.se.symptoms))
                for s in active_symptoms:
                    if s in symptom_to_idx:
                        vec[symptom_to_idx[s]] = 1.0
                        
                predictions = self.disease_model.predict(np.array([vec]), verbose=0)[0]
                pred_idx = int(np.argmax(predictions))
                confidence = float(predictions[pred_idx])
                
                predicted_name = self.diseases[pred_idx]['name']
                
                # Fetch details
                for d in self.diseases:
                    if d['name'] == predicted_name:
                        res = d.copy()
                        res['confidence'] = confidence
                        return res
            except Exception as e:
                print(f"Error during disease model prediction: {e}. Falling back to Jaccard.")
                
        # Fallback to Jaccard similarity
        return self._predict_disease_heuristic(active_symptoms)

    def _predict_disease_heuristic(self, active_symptoms: list) -> dict:
        if not active_symptoms:
            return None
            
        active_set = set(active_symptoms)
        best_match = None
        highest_score = 0.0
        
        for d in self.diseases:
            disease_symptoms = set(d['symptoms'])
            intersection = active_set.intersection(disease_symptoms)
            if not intersection:
                continue
                
            # Jaccard similarity: intersection over union
            union = active_set.union(disease_symptoms)
            score = len(intersection) / len(union)
            
            # Boost score slightly if most of the disease's symptoms are covered
            coverage = len(intersection) / len(disease_symptoms)
            final_score = (score * 0.6) + (coverage * 0.4)
            
            if final_score > highest_score:
                highest_score = final_score
                best_match = d
                
        if best_match:
            res = best_match.copy()
            res['confidence'] = round(highest_score, 2)
            return res
            
        return None

    def _check_conversational_dataset(self, text: str, lang: str) -> str:
        # Load conversations.csv patterns
        current_dir = os.path.dirname(os.path.abspath(__file__))
        conv_path = os.path.join(current_dir, 'datasets', 'conversations.csv')
        if not os.path.exists(conv_path):
            return None
            
        with open(conv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pattern = row.get('pattern', '').strip().lower()
                resp = row.get('response', '').strip()
                resp_te = row.get('response_te', '').strip()
                r_lang = row.get('language', 'en')
                
                # Check regex match
                if pattern and re.search(rf'\b{re.escape(pattern)}\b', text):
                    # Return language appropriate response
                    if lang == 'te' and resp_te:
                        return resp_te
                    return resp
        return None

    def generate_response(self, analysis: dict, language: str) -> str:
        """
        Build a beautifully formatted markdown clinical analysis report for the user.
        """
        disclaimer = self._get_disclaimer(language)
        
        if language == 'te':
            # Telugu Report
            meds_str = ""
            if analysis['suggested_medicines']:
                meds_str = "\n\n**సూచించదగిన గృహవైద్యం/మందులు:**"
                for m in analysis['suggested_medicines']:
                    meds_str += f"\n- **{m['name']}**: డోసేజ్: {m['dosage']} | సైడ్ ఎఫెక్ట్స్: {m['side_effects']}"
            
            allergy_str = ""
            if analysis['allergy_warnings']:
                allergy_str = "\n\n⚠️ **అలెర్జీ హెచ్చరికలు:**"
                for w in analysis['allergy_warnings']:
                    allergy_str += f"\n- రోగికి **{w}** పట్ల అలెర్జీ ఉన్నట్లు రికార్డు అయింది! దయచేసి దీనికి దూరంగా ఉండండి."

            report = (
                f"### ప్రాథమిక ఆరోగ్య నివేదిక\n"
                f"- **గుర్తించిన లక్షణాలు:** {', '.join(analysis['symptoms'])}\n"
                f"- **అంచనా వేయబడిన వ్యాధి:** {analysis['disease']} (సహాయక విశ్వసనీయత: {analysis['confidence']:.0%})\n"
                f"- **వైద్య విభాగం:** {analysis['department']}\n"
                f"- **వివరణ:** {analysis['description']}\n\n"
                f"**సిఫార్సు చేయబడిన పరీక్షలు:**\n{analysis['tests']}\n\n"
                f"**చికిత్స సూచనలు:**\n{analysis['treatment']}\n"
                f"{meds_str}"
                f"{allergy_str}\n\n"
                f"🚨 **రిస్క్ అసెస్‌మెంట్ (ప్రమాద అంచనా):** **{analysis['risk_level'].upper()}**\n"
                f"- **రిస్క్ కారకాలు:** {', '.join(analysis['risk_factors'])}\n"
                f"- **వైద్యుడి సిఫార్సు:** {analysis['risk_recommendations']}\n\n"
                f"---  \n"
                f"{disclaimer}"
            )
        else:
            # English Report
            meds_str = ""
            if analysis['suggested_medicines']:
                meds_str = "\n\n**Suggested Medications:**"
                for m in analysis['suggested_medicines']:
                    meds_str += f"\n- **{m['name']}**: Dosage: {m['dosage']} | Side Effects: {m['side_effects']}"
            
            allergy_str = ""
            if analysis['allergy_warnings']:
                allergy_str = "\n\n⚠️ **Allergy Warnings:**"
                for w in analysis['allergy_warnings']:
                    allergy_str += f"\n- Patient has a registered allergy related to **{w}**! Avoid administration."

            report = (
                f"### Preliminary Medical Report\n"
                f"- **Extracted Symptoms:** {', '.join(analysis['symptoms'])}\n"
                f"- **Predicted Condition:** {analysis['disease']} (Confidence: {analysis['confidence']:.0%})\n"
                f"- **Medical Department:** {analysis['department']}\n"
                f"- **Description:** {analysis['description']}\n\n"
                f"**Recommended Tests:**\n{analysis['tests']}\n\n"
                f"**Treatment Advice:**\n{analysis['treatment']}\n"
                f"{meds_str}"
                f"{allergy_str}\n\n"
                f"🚨 **Risk Level:** **{analysis['risk_level'].upper()}**\n"
                f"- **Risk Factors:** {', '.join(analysis['risk_factors'])}\n"
                f"- **Doctor's Recommendation:** {analysis['risk_recommendations']}\n\n"
                f"---  \n"
                f"{disclaimer}"
            )
            
        return report

    def _get_disclaimer(self, language: str) -> str:
        if language == 'te':
            return (
                f"*గమనిక: ఇది ఏఐ (కృత్రిమ మేధస్సు) ఆధారిత విశ్లేషణ మాత్రమే. ఇది అధికారిక వైద్య నిర్ధారణ లేదా చికిత్సకు ప్రత్యామ్నాయం కాదు. "
                f"దయచేసి ఖచ్చితమైన చికిత్స మరియు సలహా కోసం మా ఆసుపత్రిలోని అర్హత కలిగిన వైద్యుడిని సంప్రదించండి. అత్యవసర పరిస్థితిలో వెంటనే ఆసుపత్రికి వెళ్ళండి.*"
            )
        return (
            f"*Disclaimer: This is an AI-assisted evaluation and does not constitute official medical advice, diagnosis, or treatment. "
            f"Please consult a qualified doctor at our hospital for official medical guidance. In case of an emergency, go to the nearest ER immediately.*"
        )
