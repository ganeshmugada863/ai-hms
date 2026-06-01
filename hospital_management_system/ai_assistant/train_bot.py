import os
import csv
import json
import re
from django.utils import timezone
from django.conf import settings
from doctors.models import DoctorProfile
from appointments.models import Appointment
from medical_records.models import MedicalRecord
from ai_assistant.models import ChatMessage, SymptomEntry, DiseasePrediction

class ChatBot:
    def __init__(self):
        # We load departments and basic data in a rules-based layout
        self.departments = [
            'General Physician', 'Cardiology', 'Dermatology', 'Ophthalmology', 
            'Gynecology', 'Orthopedics', 'Psychiatry', 'Dentistry', 'ENT', 
            'Pediatrics', 'Neurology', 'Gastroenterology', 'Nephrology', 
            'Oncology', 'Pulmonology'
        ]

    def _check_security_violation(self, message: str, patient) -> bool:
        """
        Check for security violations (preventing accessing records of other patients).
        Only triggers on 4+ digit numbers that look like real IDs, not everyday numbers like '3 days'.
        """
        msg_clean = message.lower().strip()
        # Only flag sequences of 4+ digits - these look like actual IDs, not symptom durations
        digit_sequences = re.findall(r'\b\d{4,}\b', msg_clean)
        patient_id = str(patient.id)
        patient_user_id = str(patient.user.id)
        patient_phone = str(patient.emergency_contact or '').replace('-', '').replace(' ', '')
        
        for digits in digit_sequences:
            if digits != patient_id and digits != patient_user_id and digits not in patient_phone:
                # Only block if clearly trying to access someone else's record
                keywords = ['patient id', 'patient record', 'patient history', 'patient profile',
                            'patient details', 'show patient', 'view patient', 'get patient']
                if any(kw in msg_clean for kw in keywords):
                    return True
                        
        other_patient_indicators = [
            'other patient', 'another patient', 'someone else', "doctor's patient",
            'history of patient', 'details of patient', 'profile of patient'
        ]
        if any(ind in msg_clean for ind in other_patient_indicators):
            return True
            
        return False

    def process_message(self, patient, message: str, session) -> dict:
        """
        Main entry point for chatbot query processing.
        Handles state-based conversations, multilingual replies, and custom rich cards.
        """
        from ai_assistant.language_detector import LanguageDetector
        ld = LanguageDetector()
        
        # 1. Language Detection & Configuration
        lang = ld.detect(message)
        session.language = lang
        session.save()
        
        # Translate to English for unified logic processing
        english_message = message if lang == 'en' else ld.translate_to_english(message)
        clean_msg = english_message.lower().strip()
        
        # Central Logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"MediAssist AI Interaction: Patient ID: {patient.id}, Session ID: {session.session_id}, Query: '{message}' (EN: '{english_message}')")
        
        # Create user chat message in DB
        ChatMessage.objects.create(
            session=session,
            role='user',
            content=message,
            translated_content=english_message
        )
        
        # 2. Security Check
        if self._check_security_violation(message, patient):
            resp = self.get_multilingual_response('security_error', lang)
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}
            
        # 3. Emergency Detection Check
        emergency_keywords = [
            'heart attack', 'stroke', 'chest pain', 'unconscious', 'severe bleeding',
            'breathing difficulty', 'difficulty breathing', 'seizure', 'accident', 'poisoning', 'burn injury'
        ]
        if any(kw in clean_msg for kw in emergency_keywords):
            resp = self.get_emergency_banner_html(lang)
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': {'symptoms': ['Emergency Symptoms'], 'allergy_alerts': ['CRITICAL EMERGENCY ALERT']}}

        # Load current state machine state
        state_dict = session.predicted_diseases if isinstance(session.predicted_diseases, dict) else {}
        current_state = state_dict.get('state', None)
        
        # Helper indicators for positive/negative replies
        is_yes = clean_msg in ['yes', 'yeah', 'y', 'yup', 'ok', 'okay', 'sure', 'confirm', 'correct']
        is_no = clean_msg in ['no', 'nope', 'nah', 'not', 'cancel']

        # 4. STATE MACHINE: APPOINTMENT BOOKING DETAILS CAPTURE
        if current_state == 'booking_form_entry':
            try:
                # Try parsing JSON form submission from chat window
                form_data = json.loads(message)
                # Create Appointment record
                doc_id = state_dict.get('doctor_id')
                doctor = DoctorProfile.objects.get(id=doc_id)
                
                appt = Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    appointment_date=form_data.get('date'),
                    appointment_time=form_data.get('time'),
                    reason=form_data.get('reason', 'Consultation booked via MediAssist AI'),
                    consultation_type=form_data.get('consultation_type', 'in_person'),
                    status='Pending'
                )
                
                # Clear session state
                session.predicted_diseases = {}
                session.save()
                
                success_html = self.get_appointment_success_html(appt, lang)
                ChatMessage.objects.create(session=session, role='bot', content=success_html)
                return {'response': success_html, 'analysis': None}
            except Exception as e:
                # Fallback if they replied text instead of JSON
                state_dict['state'] = None
                session.predicted_diseases = state_dict
                session.save()

        # 5. CORE TRIGGERS & COMMAND ROUTINGS
        # 5a. Greetings & Welcome Card
        if any(w in clean_msg.split() for w in ['hello', 'hi', 'hey', 'namaste', 'greetings', 'start', 'help']) or clean_msg == 'new chat':
            # Clear state
            session.predicted_diseases = {}
            session.save()
            resp_html = self.get_welcome_card_html(lang)
            ChatMessage.objects.create(session=session, role='bot', content=resp_html)
            return {'response': resp_html, 'analysis': None}
            
        # 5b. Emergency Manual Command (exact phrases only, not any message with 'emergency' in it)
        elif clean_msg in ['emergency', 'emergency help', 'ambulance request', 'ambulance']:
            resp_html = self.get_emergency_banner_html(lang)
            ChatMessage.objects.create(session=session, role='bot', content=resp_html)
            return {'response': resp_html, 'analysis': {'symptoms': ['Emergency Prompt'], 'allergy_alerts': []}}
            
        # 5c. Hospital Services Module (exact match only)
        elif clean_msg in ['hospital services', 'services', 'our services']:
            resp_html = self.get_hospital_services_html(lang)
            ChatMessage.objects.create(session=session, role='bot', content=resp_html)
            return {'response': resp_html, 'analysis': None}
            
        # 5d. Explore Departments (exact match only)
        elif clean_msg in ['explore departments', 'departments', 'show departments', 'all departments']:
            resp_html = self.get_departments_html(lang)
            ChatMessage.objects.create(session=session, role='bot', content=resp_html)
            return {'response': resp_html, 'analysis': None}
            
        # 5e. Track Appointment (exact match only)
        elif clean_msg in ['track appointment', 'my appointments', 'track my appointment', 'appointment status']:
            resp_html = self.get_track_appointments_html(patient, lang)
            ChatMessage.objects.create(session=session, role='bot', content=resp_html)
            return {'response': resp_html, 'analysis': None}
            
        # 5f. Lab Reports Checking (exact match only)
        elif clean_msg in ['lab reports', 'reports', 'lab report', 'my reports', 'my lab reports']:
            resp_html = self.get_lab_reports_html(patient, lang)
            ChatMessage.objects.create(session=session, role='bot', content=resp_html)
            return {'response': resp_html, 'analysis': None}
            
        # 5g. Find Doctor Option Start (exact match only)
        elif clean_msg in ['find doctor', 'book appointment', 'find a doctor', 'find doctor please']:
            # Ask symptom
            resp = self.get_multilingual_response('ask_symptom', lang)
            state_dict['state'] = 'awaiting_symptom'
            session.predicted_diseases = state_dict
            session.save()
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': None}

        # 5h. Direct Mapped Recommendations from Buttons (e.g. "Recommend Cardiology")
        elif clean_msg.startswith('recommend '):
            dept_name = clean_msg.replace('recommend ', '').strip().title()
            # Match closely to our departments list
            matched_dept = next((d for d in self.departments if dept_name.lower() in d.lower()), 'General Physician')
            resp = self.get_doctor_recommendations_html(matched_dept, lang, session, state_dict)
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': {'symptoms': [matched_dept + ' issue'], 'allergy_alerts': []}}
            
        # 5i. Direct Doctor Book Click (e.g. "book_doc_15")
        elif clean_msg.startswith('book_doc_'):
            doc_id = clean_msg.replace('book_doc_', '').strip()
            try:
                doctor = DoctorProfile.objects.get(id=doc_id)
                state_dict['state'] = 'booking_form_entry'
                state_dict['doctor_id'] = doc_id
                session.predicted_diseases = state_dict
                session.save()
                
                booking_form_html = self.get_booking_form_html(doctor, patient, lang)
                ChatMessage.objects.create(session=session, role='bot', content=booking_form_html)
                return {'response': booking_form_html, 'analysis': None}
            except Exception as e:
                resp = "Error accessing doctor records. Please select another doctor."
                ChatMessage.objects.create(session=session, role='bot', content=resp)
                return {'response': resp, 'analysis': None}

        # 6. SYMPTOM ANALYSIS & EVALUATION PIPELINE
        # If currently collecting details or just starting a symptom discussion
        extracted_symptoms = []
        try:
            from ai_assistant.symptom_engine import SymptomEngine
            se = SymptomEngine()
            se_res = se.extract_symptoms(english_message)
            extracted_symptoms = [item['name'] for item in se_res]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"SymptomEngine extraction failed: {e}. Using rule fallback.")
            extracted_symptoms = self.extract_symptoms_local(english_message)
        
        if extracted_symptoms:
            # Map symptom to Department
            mapped_dept = self.map_symptom_to_department(extracted_symptoms[0])
            
            # Save symptoms to session database list
            session.extracted_symptoms = list(set(session.extracted_symptoms + extracted_symptoms))
            session.risk_level = 'medium'
            session.save()
            
            # Response using AI Safety rule: "Based on the symptoms you described, consulting a [Department] is appropriate"
            resp = self.get_doctor_recommendations_html(mapped_dept, lang, session, state_dict)
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': {'symptoms': session.extracted_symptoms, 'allergy_alerts': []}}

        # 7. Broader keyword-based symptom detection as secondary fallback
        # Catches messages like 'stomach pain', 'my head hurts', 'i feel dizzy' etc.
        broad_symptom_map = [
            (['stomach', 'nausea', 'vomit', 'diarrhea', 'acidity', 'gastric', 'digestive', 'abdomen', 'belly', 'gut'], 'Gastroenterology'),
            (['chest', 'heart', 'palpitation', 'cardiac', 'pressure in chest'], 'Cardiology'),
            (['head', 'migraine', 'brain', 'dizzy', 'dizziness', 'vertigo', 'epilepsy', 'nervous', 'numbness'], 'Neurology'),
            (['skin', 'rash', 'itch', 'itching', 'acne', 'allergy', 'hives', 'eczema', 'psoriasis'], 'Dermatology'),
            (['cough', 'breath', 'lung', 'asthma', 'wheezing', 'tb', 'tuberculosis', 'sputum'], 'Pulmonology'),
            (['bone', 'joint', 'knee', 'back pain', 'spine', 'fracture', 'shoulder', 'hip', 'ankle', 'wrist', 'elbow', 'arthritis'], 'Orthopedics'),
            (['eye', 'vision', 'blur', 'blurry', 'cataract', 'glaucoma', 'retina', 'conjunctivitis'], 'Ophthalmology'),
            (['ear', 'nose', 'throat', 'tonsil', 'sinus', 'hearing', 'hoarse', 'voice', 'adenoid'], 'ENT'),
            (['child', 'baby', 'infant', 'kid', 'toddler', 'pediatric', 'children'], 'Pediatrics'),
            (['mental', 'anxiety', 'depression', 'stress', 'mood', 'phobia', 'panic', 'insomnia', 'sleep', 'bipolar', 'ocd'], 'Psychiatry'),
            (['pregnancy', 'pregnant', 'gynec', 'menstrual', 'period', 'uterus', 'ovary', 'female', 'period pain'], 'Gynecology'),
            (['kidney', 'urine', 'urinary', 'bladder', 'renal', 'dialysis', 'uti', 'frequent urination'], 'Nephrology'),
            (['tooth', 'teeth', 'dental', 'gum', 'mouth', 'jaw', 'cavity', 'toothache'], 'Dentistry'),
            (['diabetes', 'thyroid', 'hormonal', 'hormone', 'endocrine', 'sugar', 'insulin', 'adrenal'], 'Endocrinology'),
            (['fever', 'flu', 'cold', 'fatigue', 'weakness', 'tired', 'body ache', 'body pain', 'pain', 'general'], 'General Physician'),
        ]
        
        broad_matched_dept = None
        for keywords, dept in broad_symptom_map:
            if any(kw in clean_msg for kw in keywords):
                broad_matched_dept = dept
                break
        
        if broad_matched_dept:
            # Found a symptom keyword match
            extracted_symptoms = [clean_msg]  # Use the message as the symptom
            session.extracted_symptoms = list(set((session.extracted_symptoms or []) + extracted_symptoms))
            session.risk_level = 'medium'
            session.save()
            
            resp = self.get_doctor_recommendations_html(broad_matched_dept, lang, session, state_dict)
            ChatMessage.objects.create(session=session, role='bot', content=resp)
            return {'response': resp, 'analysis': {'symptoms': session.extracted_symptoms, 'allergy_alerts': []}}

        # 8. Final Fallback Default Response - always return something useful
        resp = self.get_multilingual_response('fallback', lang)
        ChatMessage.objects.create(session=session, role='bot', content=resp)
        return {'response': resp, 'analysis': None}

    # ==========================================
    # HTML UI COMPONENT GENERATORS
    # ==========================================
    
    def get_welcome_card_html(self, lang: str) -> str:
        # Title depending on lang
        t_hello = {'en': 'Hello 👋', 'te': 'హలో 👋', 'hi': 'नमस्ते 👋', 'ta': 'ஹலோ 👋', 'kn': 'ಹಲೋ 👋', 'ml': 'ഹലോ 👋'}[lang]
        t_desc = {'en': "I'm <strong>MediAssist AI</strong>.", 'te': "నేను <strong>మీడిఅసిస్ట్ AI</strong>.", 'hi': "मैं <strong>मीडियासिस्ट एआई</strong> हूँ।", 'ta': "நான் <strong>மீடியாசிஸ்ட் ஏஐ</strong>.", 'kn': "ನಾನು <strong>ಮೀಡಿಯಾಸಿಸ್ಟ್ ಎಐ</strong>.", 'ml': "ഞാൻ <strong>മീഡിയാസിസ്റ്റ് എഐ</strong>."}[lang]
        t_help = {'en': "I can help you:", 'te': "నేను మీకు సహాయం చేయగలను:", 'hi': "मैं आपकी मदद कर सकता हूँ:", 'ta': "நான் உங்களுக்கு உதவ முடியும்:", 'kn': "ನಾನು ನಿಮಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ:", 'ml': "എനിക്ക് നിങ്ങളെ സഹായിക്കാനാകും:"}[lang]
        t_actions = {'en': "Please describe your symptoms or select a quick action below to begin:", 'te': "మీ లక్షణాలను వివరించండి లేదా ప్రారంభించడానికి క్రింది శీఘ్ర చర్యను ఎంచుకోండి:", 'hi': "शुरू करने के लिए कृपया अपने लक्षणों का वर्णन करें या नीचे एक त्वरित विकल्प चुनें:", 'ta': "உங்கள் அறிகுறிகளை விவரிக்கவும் அல்லது கீழே உள்ள விரைவான செயலைத் தேர்ந்தெடுக்கவும்:", 'kn': "ಪ್ರಾರಂಭಿಸಲು ದಯವಿಟ್ಟು ನಿಮ್ಮ ರೋಗಲಕ್ಷಣಗಳನ್ನು ವಿವರಿಸಿ ಅಥವಾ ಕೆಳಗಿನ ತ್ವರಿತ ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ:", 'ml': "തുടങ്ങാൻ ദയവായി നിങ്ങളുടെ ലക്ഷണങ്ങൾ വിവരിക്കുക അല്ലെങ്കിൽ താഴെയുള്ള ഒരു ദ്രുത പ്രവർത്തനം തിരഞ്ഞെടുക്കുക:"}[lang]
        
        list_items = {
            'en': ['Find the right doctor', 'Understand symptoms', 'Book appointments', 'Explore hospital services', 'Get emergency assistance'],
            'te': ['సరైన వైద్యుడిని కనుగొనండి', 'లక్షణాలను అర్థం చేసుకోండి', 'అపాయింట్‌మెంట్‌లు బుక్ చేయండి', 'ఆసుపత్రి సేవలను అన్వేషించండి', 'అత్యవసర సహాయం పొందండి'],
            'hi': ['सही डॉक्टर खोजें', 'लक्षणों को समझें', 'अ अपॉइंटमेंट बुक करें', 'अस्पताल सेवाओं को जानें', 'आपातकालीन सहायता प्राप्त करें'],
            'ta': ['சரியான மருத்துவரை கண்டறியவும்', 'அறிகுறிகளை புரிந்து கொள்ளவும்', 'அப்பாயிண்ட்மெண்ட் முன்பதிவு செய்யவும்', 'மருத்துவமனை சேவைகளை அறியவும்', 'அவசர உதவி பெறவும்'],
            'kn': ['ಸರಿಯಾದ ವೈದ್ಯರನ್ನು ಹುಡುಕಿ', 'ರೋಗಲಕ್ಷಣಗಳನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳಿ', 'ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಬುಕ್ ಮಾಡಿ', 'ಆಸ್ಪತ್ರೆ ಸೇವೆಗಳನ್ನು ಅನ್ವೇಷಿಸಿ', 'ತುರ್ತು ಸಹಾಯ ಪಡೆಯಿರಿ'],
            'ml': ['ശരിയായ ഡോക്ടറെ കണ്ടെത്തുക', 'ലക്ഷണങ്ങൾ മനസ്സിലാക്കുക', 'അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യുക', 'ആശുപത്രി സേവനങ്ങൾ പര്യവേക്ഷണം ചെയ്യുക', 'അടിയന്തിര സഹായം നേടുക']
        }[lang]

        welcome_html = f"""
        <div class="welcome-card-premium" style="background: rgba(255,255,255,0.7); backdrop-filter: blur(10px); border: 1px solid rgba(37,99,235,0.15); border-radius: 18px; padding: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.02); margin-bottom: 15px;">
            <h4 style="font-size: 18px; font-weight: 700; color: #2563EB; margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px;">
                <i class="fas fa-robot animate-pulse"></i> {t_hello}
            </h4>
            <p style="font-size: 14.5px; color: #0F172A; margin: 0 0 10px 0;">{t_desc} {t_help}</p>
            <ul style="list-style: none; padding: 0; margin: 0 0 15px 0; font-size: 13.5px; color: #475569; display: flex; flex-direction: column; gap: 6px;">
                <li><i class="fas fa-check-circle" style="color: #10B981; margin-right: 6px;"></i> {list_items[0]}</li>
                <li><i class="fas fa-check-circle" style="color: #10B981; margin-right: 6px;"></i> {list_items[1]}</li>
                <li><i class="fas fa-check-circle" style="color: #10B981; margin-right: 6px;"></i> {list_items[2]}</li>
                <li><i class="fas fa-check-circle" style="color: #10B981; margin-right: 6px;"></i> {list_items[3]}</li>
                <li><i class="fas fa-check-circle" style="color: #10B981; margin-right: 6px;"></i> {list_items[4]}</li>
            </ul>
            <p style="font-size: 13px; color: #64748B; line-height: 1.4; margin: 0;">{t_actions}</p>
        </div>
        
        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px;">
            <button class="chat-btn" data-value="Find Doctor" style="border: 1px solid rgba(37,99,235,0.2); background: rgba(37,99,235,0.05); color: #2563EB; font-weight: 600; display: flex; align-items: center; gap: 6px; border-radius: 12px; padding: 8px 12px; font-size: 12.5px;"><i class="fas fa-user-md"></i> Find Doctor</button>
            <button class="chat-btn" data-value="Book Appointment" style="border: 1px solid rgba(37,99,235,0.2); background: rgba(37,99,235,0.05); color: #2563EB; font-weight: 600; display: flex; align-items: center; gap: 6px; border-radius: 12px; padding: 8px 12px; font-size: 12.5px;"><i class="fas fa-calendar-alt"></i> Book Appointment</button>
            <button class="chat-btn btn-no" data-value="Emergency Help" style="font-weight: 600; display: flex; align-items: center; gap: 6px; border-radius: 12px; padding: 8px 12px; font-size: 12.5px;"><i class="fas fa-ambulance"></i> Emergency Help</button>
            <button class="chat-btn" data-value="Hospital Services" style="border: 1px solid rgba(37,99,235,0.2); background: rgba(37,99,235,0.05); color: #2563EB; font-weight: 600; display: flex; align-items: center; gap: 6px; border-radius: 12px; padding: 8px 12px; font-size: 12.5px;"><i class="fas fa-hospital"></i> Services</button>
            <button class="chat-btn" data-value="Explore Departments" style="border: 1px solid rgba(37,99,235,0.2); background: rgba(37,99,235,0.05); color: #2563EB; font-weight: 600; display: flex; align-items: center; gap: 6px; border-radius: 12px; padding: 8px 12px; font-size: 12.5px;"><i class="fas fa-notes-medical"></i> Departments</button>
            <button class="chat-btn" data-value="Lab Reports" style="border: 1px solid rgba(37,99,235,0.2); background: rgba(37,99,235,0.05); color: #2563EB; font-weight: 600; display: flex; align-items: center; gap: 6px; border-radius: 12px; padding: 8px 12px; font-size: 12.5px;"><i class="fas fa-file-invoice-dollar"></i> Lab Reports</button>
            <button class="chat-btn" data-value="Track Appointment" style="border: 1px solid rgba(37,99,235,0.2); background: rgba(37,99,235,0.05); color: #2563EB; font-weight: 600; display: flex; align-items: center; gap: 6px; border-radius: 12px; padding: 8px 12px; font-size: 12.5px;"><i class="fas fa-clock"></i> Track Appointment</button>
        </div>
        """
        return welcome_html

    def get_emergency_banner_html(self, lang: str) -> str:
        t_alert = {
            'en': '⚠ This may be a medical emergency. Please contact emergency services immediately or visit the nearest emergency department.',
            'te': '⚠ ఇది వైద్య అత్యవసర పరిస్థితి కావచ్చు. దయచేసి వెంటనే అత్యవసర సేవలను సంప్రదించండి లేదా సమీప అత్యవసర విభాగానికి వెళ్ళండి.',
            'hi': '⚠ यह एक चिकित्सा आपातकाल हो सकता है। कृपया तुरंत आपातकालीन सेवाओं से संपर्क करें या निकटतम आपातकालीन विभाग में जाएँ।',
            'ta': '⚠ இது ஒரு மருத்துவ அவசர நிலையாக இருக்கலாம். தயவுசெய்து உடனடியாக அவசர சேவைகளை தொடர்பு கொள்ளவும் அல்லது அருகிலுள்ள அவசர பிரிவுக்கு செல்லவும்.',
            'kn': '⚠ ಇದು ವೈದ್ಯಕೀಯ ತುರ್ತು ಪರಿಸ್ಥಿತಿಯಾಗಿರಬಹುದು. ದಯವಿಟ್ಟು ತಕ್ಷಣ ತುರ್ತು ಸೇವೆಗಳನ್ನು ಸಂಪರ್ಕಿಸಿ ಅಥವಾ ಹತ್ತಿರದ ತುರ್ತು ವಿಭಾಗಕ್ಕೆ ಭೇಟಿ ನೀಡಿ.',
            'ml': '⚠ ഇത് ഒരു മെഡിക്കൽ അടിയന്തരാവസ്ഥയായിരിക്കാം. ദയവായി ഉടൻ തന്നെ അടിയന്തര സേവനങ്ങളുമായി ബന്ധപ്പെടുക അല്ലെങ്കിൽ അടുത്തുള്ള അത്യാഹിത വിഭാഗം സന്ദർശിക്കുക.'
        }[lang]

        banner_html = f"""
        <div style="background: rgba(239, 68, 68, 0.08); border: 2px solid #EF4444; border-radius: 16px; padding: 18px; box-shadow: 0 10px 30px rgba(239, 68, 68, 0.1); margin-bottom: 12px;">
            <h5 style="color: #EF4444; font-size: 15px; font-weight: 700; margin: 0 0 10px 0; display: flex; align-items: center; gap: 8px;">
                <i class="fas fa-exclamation-triangle animate-bounce"></i> EMERGENCY ALERT
            </h5>
            <p style="font-size: 13.5px; color: #0F172A; line-height: 1.5; font-weight: 600; margin: 0 0 15px 0;">{t_alert}</p>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <a href="tel:108" class="chat-btn" style="text-align: center; background: #EF4444; color: white !important; border: none; font-weight: bold; border-radius: 10px; padding: 10px; text-decoration: none; display: block;">
                    <i class="fas fa-phone-alt"></i> Call Ambulance (108)
                </a>
                <a href="tel:911" class="chat-btn" style="text-align: center; background: #475569; color: white !important; border: none; font-weight: 600; border-radius: 10px; padding: 10px; text-decoration: none; display: block;">
                    <i class="fas fa-phone-alt"></i> Call Emergency (911)
                </a>
                <a href="https://maps.google.com/?q=emergency+room" target="_blank" class="chat-btn" style="text-align: center; border: 1px solid rgba(239,68,68,0.3); background: white; color: #EF4444 !important; font-weight: 600; border-radius: 10px; padding: 10px; text-decoration: none; display: block;">
                    <i class="fas fa-map-marker-alt"></i> Find Nearest ER Room
                </a>
            </div>
        </div>
        """
        return banner_html

    def get_hospital_services_html(self, lang: str) -> str:
        # 12 Hospital Services
        services = [
            {'name': 'OPD', 'desc': 'Outpatient consults & general care', 'icon': 'fa-user-md'},
            {'name': 'IPD', 'desc': 'Inpatient admission & rooms details', 'icon': 'fa-bed'},
            {'name': 'ICU & NICU', 'desc': 'Intensive critical life support care', 'icon': 'fa-heartbeat'},
            {'name': 'Radiology', 'desc': 'High-definition X-Ray, CT & MRI Scans', 'icon': 'fa-x-ray'},
            {'name': 'Laboratory', 'desc': 'Secure, computerized blood analysis tests', 'icon': 'fa-vial'},
            {'name': 'Blood Bank', 'desc': '24/7 emergency blood replacement stocks', 'icon': 'fa-tint'},
            {'name': 'Pharmacy', 'desc': 'In-house certified medicine supply desk', 'icon': 'fa-pills'},
            {'name': 'Emergency Care', 'desc': '24/7 trauma response & triage units', 'icon': 'fa-ambulance'},
            {'name': 'Ambulance', 'desc': 'Fully equipped cardiac support fleet', 'icon': 'fa-truck-medical'},
            {'name': 'Insurance Desk', 'desc': 'Hassle-free TPA cashless claim processing', 'icon': 'fa-shield-halved'},
            {'name': 'Billing Office', 'desc': 'Transparent billing & discharge checkout', 'icon': 'fa-receipt'},
            {'name': 'Medical Records', 'desc': 'Digitized secure personal patient charts', 'icon': 'fa-file-medical'}
        ]
        
        cards_html = ""
        for s in services:
            cards_html += f"""
            <div style="background: white; border: 1px solid rgba(226,232,240,0.8); border-radius: 14px; padding: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.01);">
                <span style="font-size: 18px; color: #2563EB;"><i class="fas {s['icon']}"></i></span>
                <h6 style="font-size: 13.5px; font-weight: bold; margin: 6px 0 2px 0; color: #0F172A;">{s['name']}</h6>
                <p style="font-size: 11px; color: #64748B; margin: 0; line-height: 1.3;">{s['desc']}</p>
            </div>
            """

        services_html = f"""
        <div style="margin-bottom: 12px;">
            <h5 style="font-size: 15px; font-weight: 700; color: #2563EB; margin: 0 0 10px 0;"><i class="fas fa-hospital"></i> Hospital Services & Facilities</h5>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; max-height: 300px; overflow-y: auto; padding: 5px;">
                {cards_html}
            </div>
        </div>
        """
        return services_html

    def get_departments_html(self, lang: str) -> str:
        depts_details = [
            {'name': 'Cardiology', 'desc': 'Heart care & coronary diseases', 'icon': 'fa-heart'},
            {'name': 'Neurology', 'desc': 'Brain & nervous system disorders', 'icon': 'fa-brain'},
            {'name': 'Dermatology', 'desc': 'Skin health, rashes & allergy solutions', 'icon': 'fa-hand-dots'},
            {'name': 'Orthopedics', 'desc': 'Bone fractures, joints & back pain care', 'icon': 'fa-bone'},
            {'name': 'Gynecology', 'desc': 'Pregnancy & female health monitoring', 'icon': 'fa-person-pregnant'},
            {'name': 'Pediatrics', 'desc': 'Children health care & infections', 'icon': 'fa-baby'},
            {'name': 'ENT', 'desc': 'Ear, nose, throat & tonsil pain care', 'icon': 'fa-ear-listen'},
            {'name': 'Psychiatry', 'desc': 'Anxiety, depression & mental health', 'icon': 'fa-head-side-virus'},
            {'name': 'Pulmonology', 'desc': 'Asthma, lung issues & breathing care', 'icon': 'fa-lungs'},
            {'name': 'Gastroenterology', 'desc': 'Stomach pain, acidity & digestive care', 'icon': 'fa-stomach'},
            {'name': 'Nephrology', 'desc': 'Kidney problems & urinary issues', 'icon': 'fa-kidneys'},
            {'name': 'Dentistry', 'desc': 'Toothaches, gum health & oral checkups', 'icon': 'fa-tooth'}
        ]
        
        cards_html = ""
        for d in depts_details:
            cards_html += f"""
            <div style="background: white; border: 1px solid rgba(226,232,240,0.8); border-radius: 14px; padding: 12px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 6px rgba(0,0,0,0.01);">
                <div>
                    <span style="font-size: 18px; color: #2563EB;"><i class="fas {d['icon']}"></i></span>
                    <h6 style="font-size: 13px; font-weight: bold; margin: 6px 0 2px 0; color: #0F172A;">{d['name']}</h6>
                    <p style="font-size: 11px; color: #64748B; margin: 0 0 10px 0; line-height: 1.3;">{d['desc']}</p>
                </div>
                <button class="chat-btn" data-value="Recommend {d['name']}" style="padding: 4px 8px; font-size: 11px; border-radius: 8px; width: 100%; border: 1px solid rgba(37,99,235,0.2); background: rgba(37,99,235,0.05); color: #2563EB;">Consult</button>
            </div>
            """

        dept_html = f"""
        <div style="margin-bottom: 12px;">
            <h5 style="font-size: 15px; font-weight: 700; color: #2563EB; margin: 0 0 10px 0;"><i class="fas fa-notes-medical"></i> Specialized Medical Departments</h5>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; max-height: 300px; overflow-y: auto; padding: 5px;">
                {cards_html}
            </div>
        </div>
        """
        return dept_html

    def get_track_appointments_html(self, patient, lang: str) -> str:
        appts = Appointment.objects.filter(patient=patient).order_by('-appointment_date', '-appointment_time')[:5]
        
        t_title = {
            'en': 'Your Active Appointments',
            'te': 'మీ క్రియాశీల అపాయింట్‌మెంట్‌లు',
            'hi': 'आपके सक्रिय अपॉइंटमेंट',
            'ta': 'உங்கள் செயலில் உள்ள அப்பாயிண்ட்மெண்ட்கள்',
            'kn': 'ನಿಮ್ಮ ಸಕ್ರಿಯ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್‌ಗಳು',
            'ml': 'നിങ്ങളുടെ സജീവമായ അപ്പോയിന്റ്മെന്റുകൾ'
        }.get(lang, 'Your Active Appointments')
        t_no_appt = {
            'en': 'No appointments found.',
            'te': 'అపాయింట్‌మెంట్‌లు ఏవీ కనుగొనబడలేదు.',
            'hi': 'कोई अपॉइंटमेंट नहीं मिला।',
            'ta': 'அப்பாயிண்ட்மெண்ட்கள் எதுவும் இல்லை.',
            'kn': 'ಯಾವುದೇ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್‌ಗಳು ಕಂಡುಬಂದಿಲ್ಲ.',
            'ml': 'അപ്പോയിന്റ്മെന്റുകൾ ഒന്നും കണ്ടെത്തിയില്ല.'
        }.get(lang, 'No appointments found.')
        
        if not appts.exists():
            return f"<p style='font-size:13.5px; color:#475569;'><i class='fas fa-clock'></i> <strong>{t_title}</strong>:<br>{t_no_appt}</p>"

        list_html = ""
        for a in appts:
            color = "#EAB308" if a.status == 'Pending' else "#10B981" if a.status == 'Approved' else "#EF4444"
            list_html += f"""
            <div style="background: white; border: 1px solid rgba(226,232,240,0.8); border-radius: 12px; padding: 12px; margin-bottom: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="font-size:11px; font-weight:bold; color:#64748B;">ID: #{a.id}</span>
                    <span style="font-size:10px; font-weight:bold; padding:2px 6px; border-radius:10px; background: {color}22; color: {color};">{a.status.upper()}</span>
                </div>
                <h6 style="font-size:13px; font-weight:bold; margin:0 0 4px 0; color:#0F172A;">Dr. {a.doctor.user.first_name} {a.doctor.user.last_name}</h6>
                <p style="font-size:11px; color:#475569; margin:0;">
                    <i class="fas fa-calendar-alt"></i> {a.appointment_date} &nbsp; 
                    <i class="fas fa-clock"></i> {a.appointment_time} &nbsp; 
                    <i class="fas fa-video"></i> {a.get_consultation_type_display()}
                </p>
            </div>
            """

        final_html = f"""
        <div style="margin-bottom: 12px;">
            <h5 style="font-size: 15px; font-weight: 700; color: #2563EB; margin: 0 0 10px 0;"><i class="fas fa-clock"></i> {t_title}</h5>
            <div style="max-height: 250px; overflow-y: auto; padding: 2px;">
                {list_html}
            </div>
        </div>
        """
        return final_html

    def get_lab_reports_html(self, patient, lang: str) -> str:
        # Query patient uploads (we treat all report uploads as lab reports)
        reports = MedicalRecord.objects.filter(patient=patient).order_by('-uploaded_at')[:5]
        
        t_title = {
            'en': 'Your Digital Lab Reports',
            'te': 'మీ డిజిటల్ ల్యాబ్ నివేదికలు',
            'hi': 'आपकी डिजिटल लैब रिपोर्ट',
            'ta': 'உங்கள் டிஜிட்டல் ஆய்வக அறிக்கைகள்',
            'kn': 'ನಿಮ್ಮ ಡಿಜಿಟಲ್ ಲ್ಯಾಬ್ ವರದಿಗಳು',
            'ml': 'നിങ്ങളുടെ ഡിജിറ്റൽ ലാബ് റിപ്പോർട്ടുകൾ'
        }.get(lang, 'Your Digital Lab Reports')
        t_no_report = {
            'en': 'No lab reports uploaded yet.',
            'te': 'ఇంకా ల్యాబ్ నివేదికలు ఏవీ అప్‌లోడ్ చేయబడలేదు.',
            'hi': 'अभी तक कोई लैब रिपोर्ट अपलोड नहीं की गई है।',
            'ta': 'ஆய்வக அறிக்கைகள் எதுவும் இன்னும் பதிவேற்றப்படவில்லை.',
            'kn': 'ಇನ್ನೂ ಯಾವುದೇ ಲ್ಯಾಬ್ ವರದಿಗಳನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಲಾಗಿಲ್ಲ.',
            'ml': 'ലാബ് റിപ്പോർട്ടുകൾ ഒന്നും ഇതുവരെ അപ്‌ലോഡ് ചെയ്തിട്ടില്ല.'
        }.get(lang, 'No lab reports uploaded yet.')

        if not reports.exists():
            return f"<p style='font-size:13.5px; color:#475569;'><i class='fas fa-file-invoice-dollar'></i> <strong>{t_title}</strong>:<br>{t_no_report}</p>"

        list_html = ""
        for r in reports:
            file_url = r.file.url if r.file else "#"
            list_html += f"""
            <div style="background: white; border: 1px solid rgba(226,232,240,0.8); border-radius: 12px; padding: 12px; margin-bottom: 8px; display:flex; justify-content:space-between; align-items:center; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                <div style="flex:1; margin-right: 10px; overflow:hidden;">
                    <h6 style="font-size:12.5px; font-weight:bold; margin:0; color:#0F172A; white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">{r.description or 'Laboratory Record'}</h6>
                    <p style="font-size:10px; color:#64748B; margin:2px 0 0 0;">Uploaded: {r.uploaded_at.strftime('%Y-%m-%d')}</p>
                </div>
                <a href="{file_url}" download class="chat-btn" style="padding:4px 10px; font-size:11px; border-radius:8px; border: 1px solid rgba(16,185,129,0.3); background: rgba(16,185,129,0.05); color:#10B981; text-decoration:none; display:inline-flex; align-items:center; gap:4px;">
                    <i class="fas fa-download"></i> Get
                </a>
            </div>
            """

        final_html = f"""
        <div style="margin-bottom: 12px;">
            <h5 style="font-size: 15px; font-weight: 700; color: #2563EB; margin: 0 0 10px 0;"><i class="fas fa-file-invoice-dollar"></i> {t_title}</h5>
            <div style="max-height: 250px; overflow-y: auto; padding: 2px;">
                {list_html}
            </div>
        </div>
        """
        return final_html

    def get_doctor_recommendations_html(self, department: str, lang: str, session, state_dict) -> str:
        # AI safety message
        t_safety = {
            'en': f"Based on the symptoms you described, consulting a specialist in **{department}** may be appropriate.",
            'te': f"మీరు వివరించిన లక్షణాల ఆధారంగా, **{department}** నిపుణుడిని సంప్రదించడం సముచితం కావచ్చు.",
            'hi': f"आपके द्वारा बताए गए लक्षणों के आधार पर, **{department}** के विशेषज्ञ से परामर्श करना उचित हो सकता है।",
            'ta': f"நீங்கள் விவரித்த அறிகுறிகளின் அடிப்படையில், **{department}** நிபுணரை அணுகுவது பொருத்தமானதாக இருக்கலாம்.",
            'kn': f"ನೀವು ವಿವರಿಸಿದ ರೋಗಲಕ್ಷಣಗಳ ಆಧಾರದ ಮೇಲೆ, **{department}** ತಜ್ಞರನ್ನು ಸಂಪರ್ಕಿಸುವುದು ಸೂಕ್ತವಾಗಬಹುದು.",
            'ml': f"നിങ്ങൾ വിവരിച്ച ലക്ഷണങ്ങളുടെ അടിസ്ഥാനത്തിൽ, **{department}** ലെ ഒരു വിദഗ്ദ്ധനെ കാണുന്നത് ഉചിതമായിരിക്കും."
        }[lang]
        
        # Check doctors in that department
        docs = DoctorProfile.objects.filter(specialization__icontains=department.split()[0], is_approved=True).order_by('-rating', '-experience')
        if not docs.exists():
            # Fallback check
            docs = DoctorProfile.objects.filter(is_approved=True).order_by('-rating', '-experience')[:3]
            
        t_doctors_header = {
            'en': 'Here are suitable doctors for you:',
            'te': 'మీ కోసం తగిన వైద్యులు ఇక్కడ ఉన్నారు:',
            'hi': 'यहाँ आपके लिए उपयुक्त डॉक्टर हैं:',
            'ta': 'உங்களுக்கு ஏற்ற மருத்துவர்கள் இங்கே உள்ளனர்:',
            'kn': 'ನಿಮಗಾಗಿ ಸೂಕ್ತವಾದ ವೈದ್ಯರು ಇಲ್ಲಿದ್ದಾರೆ:',
            'ml': 'നിങ്ങൾക്ക് അനുയോജ്യരായ ഡോക്ടർമാർ ഇതാ:'
        }[lang]

        cards_html = ""
        for d in docs[:4]:
            rating_val = d.rating if d.rating is not None else 5.0
            rating_stars = "★" * int(round(rating_val)) + "☆" * (5 - int(round(rating_val)))
            exp_val = d.experience if d.experience is not None else 0
            fee_val = d.consultation_fee if d.consultation_fee is not None else 0
            reviews_val = d.reviews if d.reviews is not None else 0
            
            # Select doc state value triggers state transition
            cards_html += f"""
            <div style="background: white; border: 1px solid rgba(226,232,240,0.8); border-radius: 14px; padding: 14px; box-shadow: 0 4px 6px rgba(0,0,0,0.01);">
                <div style="display:flex; gap:12px; align-items:center; margin-bottom:8px;">
                    <div style="width:40px; height:40px; border-radius:50%; background:#2563EB; color:white; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:16px;">
                        {d.user.first_name[0] if d.user.first_name else 'D'}
                    </div>
                    <div>
                        <h6 style="font-size:13.5px; font-weight:bold; margin:0; color:#0F172A;">Dr. {d.user.first_name} {d.user.last_name}</h6>
                        <p style="font-size:11px; color:#64748B; margin:2px 0 0 0;">{d.specialization} | {d.qualification}</p>
                    </div>
                </div>
                <p style="font-size:11.5px; color:#475569; margin:0 0 8px 0; line-height:1.4;">
                    <i class="fas fa-briefcase" style="color:#2563EB;"></i> {exp_val} Years Experience &nbsp; 
                    <i class="fas fa-star" style="color:#F59E0B;"></i> <span style="color:#F59E0B; font-weight:bold;">{rating_val}</span> ({reviews_val} reviews)
                </p>
                <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #F1F5F9; padding-top:8px; margin-top:8px;">
                    <span style="font-size:12px; font-weight:bold; color:#10B981;">Fee: ${fee_val}</span>
                    <button class="chat-btn" data-value="book_doc_{d.id}" style="padding:4px 12px; font-size:11.5px; border-radius:8px; background:#2563EB; color:white; border:none; font-weight:bold;">Book Session</button>
                </div>
            </div>
            """

        if not cards_html:
            cards_html = """
            <div style="background: rgba(248, 250, 252, 0.7); border: 1px dashed rgba(37,99,235,0.2); border-radius: 14px; padding: 16px; text-align: center; color: #475569;">
                <i class="fas fa-user-md" style="font-size: 24px; color: #2563EB; margin-bottom: 8px;"></i>
                <p style="margin: 0; font-size: 13px; font-weight: 600; color: #1E293B;">No specialist doctors are currently active for online booking in this department.</p>
                <p style="margin: 4px 0 0 0; font-size: 11.5px; color: #64748B;">Please consult our 24/7 general triage or check back later.</p>
            </div>
            """

        final_html = f"""
        <div style="margin-bottom:12px;">
            <p style="font-size:13.5px; color:#0F172A; line-height:1.5; font-weight:500; margin-bottom:10px;">{t_safety}</p>
            <p style="font-size:12.5px; color:#475569; margin-bottom:8px; font-weight:600;"><i class="fas fa-star-of-life" style="color:#2563EB;"></i> {t_doctors_header}</p>
            <div style="display:flex; flex-direction:column; gap:10px;">
                {cards_html}
            </div>
            <p style="font-size:11px; color:#64748B; font-style:italic; line-height:1.4; border-top: 1px solid #E2E8F0; padding-top: 10px; margin-top: 12px;">
                ⚠ Disclaimer: I am not a doctor. I cannot diagnose diseases, recommend dosages, or prescribe medications. Please consult the recommended specialist for proper medical checkup.
            </p>
        </div>
        """
        return final_html

    def get_booking_form_html(self, doctor, patient, lang: str) -> str:
        # Interactive HTML form in chat
        t_header = {
            'en': f'Book Appointment with Dr. {doctor.user.first_name} {doctor.user.last_name}',
            'te': f'Dr. {doctor.user.first_name} {doctor.user.last_name} తో అపాయింట్‌మెంట్ బుక్ చేయండి',
            'hi': f'डॉ. {doctor.user.first_name} {doctor.user.last_name} के साथ अपॉइंटमेंट बुक करें',
            'ta': f'டாக்டர் {doctor.user.first_name} {doctor.user.last_name} உடன் அப்பாயிண்ட்மெண்ட் முன்பதிவு செய்யவும்',
            'kn': f'ಡಾ. {doctor.user.first_name} {doctor.user.last_name} ಅವರೊಂದಿಗೆ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಬುಕ್ ಮಾಡಿ',
            'ml': f'ഡോ. {doctor.user.first_name} {doctor.user.last_name}-തുമായി അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യുക'
        }.get(lang, f'Book Appointment with Dr. {doctor.user.first_name} {doctor.user.last_name}')
        
        today = timezone.localdate().strftime('%Y-%m-%d')
        
        form_html = f"""
        <div class="appointment-form-card" style="background: white; border: 1px solid rgba(37,99,235,0.15); border-radius: 16px; padding: 18px; box-shadow: 0 8px 24px rgba(0,0,0,0.03); max-width:100%;">
            <h5 style="font-size:14.5px; font-weight:700; color:#2563EB; margin:0 0 15px 0; border-bottom:1px solid #F1F5F9; padding-bottom:8px;">
                <i class="fas fa-calendar-plus"></i> {t_header}
            </h5>
            <form class="interactive-booking-form" onsubmit="event.preventDefault(); submitBookingForm(this);" style="display:flex; flex-direction:column; gap:10px;">
                <div class="form-group" style="display:flex; flex-direction:column; gap:4px;">
                    <label style="font-size:11px; font-weight:bold; color:#475569;">Patient Name</label>
                    <input type="text" name="name" value="{patient.user.first_name} {patient.user.last_name}" required style="padding:6px 10px; font-size:12.5px; border-radius:6px; border:1px solid #CBD5E1; background:#F8FAFC;">
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                    <div class="form-group" style="display:flex; flex-direction:column; gap:4px;">
                        <label style="font-size:11px; font-weight:bold; color:#475569;">Age</label>
                        <input type="number" name="age" value="{patient.age}" required style="padding:6px 10px; font-size:12.5px; border-radius:6px; border:1px solid #CBD5E1;">
                    </div>
                    <div class="form-group" style="display:flex; flex-direction:column; gap:4px;">
                        <label style="font-size:11px; font-weight:bold; color:#475569;">Gender</label>
                        <select name="gender" required style="padding:6px 10px; font-size:12.5px; border-radius:6px; border:1px solid #CBD5E1; background:white;">
                            <option value="Male" {"selected" if patient.gender == 'Male' else ""}>Male</option>
                            <option value="Female" {"selected" if patient.gender == 'Female' else ""}>Female</option>
                            <option value="Other" {"selected" if patient.gender == 'Other' else ""}>Other</option>
                        </select>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                    <div class="form-group" style="display:flex; flex-direction:column; gap:4px;">
                        <label style="font-size:11px; font-weight:bold; color:#475569;">Preferred Date</label>
                        <input type="date" name="date" value="{today}" min="{today}" required style="padding:6px 10px; font-size:12.5px; border-radius:6px; border:1px solid #CBD5E1;">
                    </div>
                    <div class="form-group" style="display:flex; flex-direction:column; gap:4px;">
                        <label style="font-size:11px; font-weight:bold; color:#475569;">Preferred Time</label>
                        <input type="time" name="time" value="10:00" required style="padding:6px 10px; font-size:12.5px; border-radius:6px; border:1px solid #CBD5E1;">
                    </div>
                </div>
                <div class="form-group" style="display:flex; flex-direction:column; gap:4px;">
                    <label style="font-size:11px; font-weight:bold; color:#475569;">Consultation Mode</label>
                    <select name="consultation_type" required style="padding:6px 10px; font-size:12.5px; border-radius:6px; border:1px solid #CBD5E1; background:white;">
                        <option value="in_person">In-Person Consultation</option>
                        <option value="video">Premium Video Call</option>
                        <option value="audio">Voice Call Only</option>
                    </select>
                </div>
                <div class="form-group" style="display:flex; flex-direction:column; gap:4px;">
                    <label style="font-size:11px; font-weight:bold; color:#475569;">Brief Reason</label>
                    <input type="text" name="reason" placeholder="e.g. Cough and cold consultation" required style="padding:6px 10px; font-size:12.5px; border-radius:6px; border:1px solid #CBD5E1;">
                </div>
                <button type="submit" class="submit-booking-btn" style="margin-top:8px; padding:10px; border-radius:8px; border:none; background:#2563EB; color:white; font-weight:bold; font-size:13px; cursor:pointer;">Confirm Booking Details</button>
            </form>
        </div>
        """
        return form_html

    def get_appointment_success_html(self, appt, lang: str) -> str:
        t_header = {
            'en': 'Appointment Successfully Confirmed! 🎉',
            'te': 'అపాయింట్‌మెంట్ విజయవంతంగా ధృవీకరించబడింది! 🎉',
            'hi': 'अपॉइंटमेंट सफलतापूर्वक पक्का हो गया! 🎉',
            'ta': 'அப்பாயிண்ட்மெண்ட் வெற்றிகரமாக உறுதிசெய்யப்பட்டது! 🎉',
            'kn': 'ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಯಶಸ್ವಿಯಾಗಿ ದೃಢೀಕರಿಸಲ್ಪಟ್ಟಿದೆ! 🎉',
            'ml': 'അപ്പോയിന്റ്മെന്റ് വിജയകരമായി സ്ഥിരീകരിച്ചു! 🎉'
        }.get(lang, 'Appointment Successfully Confirmed! 🎉')
        
        t_id = {
            'en': 'Appointment ID',
            'te': 'అపాయింట్‌మెంట్ ఐడి',
            'hi': 'अपॉइंटमेंट आईडी',
            'ta': 'அப்பாயிண்ட்மெண்ட் ஐடி',
            'kn': 'ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಐಡಿ',
            'ml': 'അപ്പോയിന്റ്മെന്റ് ഐഡി'
        }.get(lang, 'Appointment ID')
        t_doctor = {
            'en': 'Consulting Doctor',
            'te': 'సంప్రదింపు వైద్యుడు',
            'hi': 'परामर्शदाता डॉक्टर',
            'ta': 'ஆலோசனை மருத்துவர்',
            'kn': 'ಸಮಾಲೋಚನಾ ವೈದ್ಯರು',
            'ml': 'കൺസൾട്ടിംഗ് ഡോക്ടർ'
        }.get(lang, 'Consulting Doctor')
        
        success_html = f"""
        <div style="background: rgba(16, 185, 129, 0.08); border: 2px solid #10B981; border-radius: 16px; padding: 18px; box-shadow: 0 10px 30px rgba(16, 185, 129, 0.05); margin-bottom: 10px;">
            <h5 style="color: #10B981; font-size: 15px; font-weight: 700; margin: 0 0 10px 0; display: flex; align-items: center; gap: 8px;">
                <i class="fas fa-check-circle animate-pulse"></i> {t_header}
            </h5>
            <div style="background:white; border:1px solid rgba(16,185,129,0.15); border-radius:12px; padding:14px; margin-bottom:12px; font-size:13px; color:#334155;">
                <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-weight:bold;">
                    <span>{t_id}:</span>
                    <span style="color:#10B981;">#{appt.id}</span>
                </div>
                <div style="margin-bottom:6px;">
                    <strong>{t_doctor}:</strong> Dr. {appt.doctor.user.first_name} {appt.doctor.user.last_name}
                </div>
                <div style="margin-bottom:6px;">
                    <strong>Date & Time:</strong> {appt.appointment_date} at {appt.appointment_time}
                </div>
                <div style="margin-bottom:6px;">
                    <strong>Specialization:</strong> {appt.doctor.specialization}
                </div>
                <div>
                    <strong>Hospital Location:</strong> MediCare Main Block, 2nd Floor, Room 204
                </div>
            </div>
            
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                <a href="/appointments/slip/{appt.id}/" target="_blank" class="chat-btn" style="text-align:center; padding:8px 10px; font-size:11.5px; font-weight:bold; background:#10B981; color:white !important; border:none; border-radius:8px; text-decoration:none; display:block;">
                    <i class="fas fa-file-download"></i> Get Slip
                </a>
                <a href="https://calendar.google.com/calendar/render?action=TEMPLATE&text=Appointment+with+Dr.+{appt.doctor.user.last_name}&dates={appt.appointment_date.strftime('%Y%m%d')}/{appt.appointment_date.strftime('%Y%m%d')}" target="_blank" class="chat-btn" style="text-align:center; padding:8px 10px; font-size:11.5px; font-weight:600; border:1px solid rgba(16,185,129,0.3); background:white; color:#10B981 !important; border-radius:8px; text-decoration:none; display:block;">
                    <i class="fas fa-calendar-plus"></i> Add Calendar
                </a>
            </div>
        </div>
        """
        return success_html

    # ==========================================
    # TRANSLATION & DICTIONARY UTILITIES
    # ==========================================

    def get_multilingual_response(self, key: str, lang: str) -> str:
        # Multi-language text templates
        vocab = {
            'ask_symptom': {
                'en': 'Please describe your symptoms or health concern (e.g. "I have fever and cough for two days").',
                'te': 'దయచేసి మీ లక్షణాలను లేదా ఆరోగ్య సమస్యను వివరించండి (ఉదా: "నాకు రెండు రోజులుగా జ్వరం మరియు దగ్గు ఉంది").',
                'hi': 'कृपया अपने लक्षणों या स्वास्थ्य संबंधी चिंता का वर्णन करें (जैसे "मुझे दो दिनों से बुखार और खांसी है")।',
                'ta': 'உங்கள் அறிகுறிகளை அல்லது சுகாதார கவலையை விவரிக்கவும் (எ.கா. "எனக்கு இரண்டு நாட்களாக காய்ச்சல் மற்றும் இருமல் உள்ளது").',
                'kn': 'ದಯವಿಟ್ಟು ನಿಮ್ಮ ರೋಗಲಕ್ಷಣಗಳನ್ನು ಅಥವಾ ಆರೋಗ್ಯ ಕಾಳಜಿಯನ್ನು ವಿವರಿಸಿ (ಉದಾ. "ನನಗೆ ಎರಡು ದಿನಗಳಿಂದ ಜ್ವರ ಮತ್ತು ಕೆಮ್ಮು ಇದೆ").',
                'ml': 'ദയവായി നിങ്ങളുടെ ലക്ഷണങ്ങളോ ആരോഗ്യ പ്രശ്നമോ വിവരിക്കുക (ഉദാ. "എനിക്ക് രണ്ട് ദിവസമായി പനിയും ചുമയും ഉണ്ട്").'
            },
            'security_error': {
                'en': 'Security Access Denied: You are not authorized to view this patient\'s records for privacy reasons.',
                'te': 'భద్రతా నిరాకరణ: గోప్యతా కారణాల వల్ల ఈ రోగి యొక్క వివరాలను వీక్షించడానికి మీకు అనుమతి లేదు.',
                'hi': 'सुरक्षा अस्वीकृति: गोपनीयता कारणों से आपको इस मरीज के रिकॉर्ड देखने की अनुमति नहीं है।',
                'ta': 'பாதுகாப்பு மறுக்கப்பட்டது: தனியுரிமை காரணங்களுக்காக இந்த நோயாளியின் பதிவுகளைப் பார்க்க உங்களுக்கு அனுமதி இல்லை.',
                'kn': 'ಭದ್ರತಾ ನಿರಾಕರಣೆ: ಗೌಪ್ಯತೆ ಕಾರಣಗಳಿಂದಾಗಿ ಈ ರೋಗಿಯ ದಾಖಲೆಗಳನ್ನು ವೀಕ್ಷಿಸಲು ನಿಮಗೆ ಅನುಮತಿ ಇಲ್ಲ.',
                'ml': 'സുരക്ഷാ നിഷേധം: സ്വകാര്യതാ കാരണങ്ങളാൽ ഈ രോഗിയുടെ വിവരങ്ങൾ കാണാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.'
            },
            'fallback': {
                'en': "I'm not sure how to help with that query. Please describe your symptoms (e.g., 'I have joint pain') or select one of the Quick Actions (like Hospital Services, Book Appointment) to get started.",
                'te': "ఆ ప్రశ్నకు ఎలా సహాయం చేయాలో నాకు ఖచ్చితంగా తెలియదు. దయచేసి మీ లక్షణాలను వివరించండి (ఉదా: 'నాకు కీళ్ల నొప్పులు ఉన్నాయి') లేదా ప్రారంభించడానికి శీఘ్ర చర్యలలో ఒకదాన్ని ఎంచుకోండి.",
                'hi': "मुझे नहीं पता कि इस प्रश्न में कैसे मदद करूँ। कृपया अपने लक्षणों का वर्णन करें (जैसे, 'मुझे जोड़ों का दर्द है') या शुरू करने के लिए त्वरित विकल्पों में से किसी एक को चुनें।",
                'ta': "அந்த கேள்விக்கு எவ்வாறு உதவுவது என்று எனக்குத் தெரியவில்லை. உங்கள் அறிகுறிகளை விவரிக்கவும் (எ.கா., 'எனக்கு மூட்டு வலி உள்ளது') அல்லது தொடங்க விரைவான செயல்களில் ஒன்றைத் தேர்ந்தெடுக்கவும்.",
                'kn': "ಆ ಪ್ರಶ್ನೆಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬೇಕೆಂದು ನನಗೆ ಖಚಿತವಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ರೋಗಲಕ್ಷಣಗಳನ್ನು ವಿವರಿಸಿ (ಉದಾ, 'ನನಗೆ ಕೀಲು ನೋವು ಇದೆ') ಅಥವಾ ಪ್ರಾರಂಭಿಸಲು ತ್ವರಿತ ಆಯ್ಕೆಗಳಲ್ಲಿ ಒಂದನ್ನು ಆರಿಸಿ.",
                'ml': "ആ ചോദ്യത്തിന് എങ്ങനെ സഹായിക്കണമെന്ന് എനിക്ക് ഉറപ്പില്ല. ദയവായി നിങ്ങളുടെ ലക്ഷണങ്ങൾ വിവരിക്കുക (ഉദാ, 'എനിക്ക് മൂട്ട് വേദനയുണ്ട്') അല്ലെങ്കിൽ ആരംഭിക്കാൻ ദ്രുത പ്രവർത്തനങ്ങളിൽ ഒന്ന് തിരഞ്ഞെടുക്കുക."
            }
        }
        return vocab.get(key, {}).get(lang, vocab[key]['en'])

    def extract_symptoms_local(self, text: str) -> list:
        # Simple local symptom extractor based on clean English keywords
        symptoms_keys = [
            'fever', 'cough', 'cold', 'headache', 'chest pain', 'breathing difficulty', 
            'skin rash', 'eye pain', 'pregnancy', 'joint pain', 'mental stress', 
            'dental pain', 'ear problems'
        ]
        
        extracted = []
        text_lower = text.lower()
        for s in symptoms_keys:
            if s in text_lower:
                extracted.append(s)
                
        return extracted

    def map_symptom_to_department(self, symptom: str) -> str:
        # Try finding the symptom in SymptomEngine to get its category and map it
        try:
            from ai_assistant.symptom_engine import SymptomEngine
            se = SymptomEngine()
            category = None
            for s in se.symptoms:
                if s['name'].lower() == symptom.lower():
                    category = s['category'].lower()
                    break
            
            if category:
                category_mapping = {
                    'cardiovascular': 'Cardiology',
                    'dermatological': 'Dermatology',
                    'skin': 'Dermatology',
                    'respiratory': 'Pulmonology',
                    'gastrointestinal': 'Gastroenterology',
                    'neurological': 'Neurology',
                    'musculoskeletal': 'Orthopedics',
                    'orthopedic': 'Orthopedics',
                    'ophthalmological': 'Ophthalmology',
                    'eye': 'Ophthalmology',
                    'psychiatric': 'Psychiatry',
                    'mental': 'Psychiatry',
                    'pediatric': 'Pediatrics',
                    'gynecological': 'Gynecology',
                    'pregnancy': 'Gynecology',
                    'urological': 'Nephrology',
                    'renal': 'Nephrology',
                    'kidney': 'Nephrology',
                    'endocrine': 'Endocrinology',
                    'hormonal': 'Endocrinology',
                    'rheumatological': 'Rheumatology',
                    'joint': 'Rheumatology',
                    'dental': 'Dentistry',
                    'mouth': 'Dentistry',
                    'ent': 'ENT',
                    'ears': 'ENT',
                    'throat': 'ENT'
                }
                if category in category_mapping:
                    return category_mapping[category]
        except Exception:
            pass

        # Fallback to local hardcoded mapping
        mapping = {
            'fever': 'General Physician',
            'cough': 'General Physician',
            'cold': 'General Physician',
            'headache': 'Neurology',
            'chest pain': 'Cardiology',
            'breathing difficulty': 'Pulmonology',
            'skin rash': 'Dermatology',
            'eye pain': 'Ophthalmology',
            'pregnancy': 'Gynecology',
            'joint pain': 'Orthopedics',
            'mental stress': 'Psychiatry',
            'dental pain': 'Dentistry',
            'ear problems': 'ENT'
        }
        return mapping.get(symptom, 'General Physician')
