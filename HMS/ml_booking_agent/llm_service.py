# Telugu translation dictionaries for high quality local fallback representation
TELUGU_DEPT = {
    'Nephrology': 'నెఫ్రాలజీ (కిడ్నీ విభాగం)',
    'Endocrinology': 'ఎండోక్రినాలజీ (మధుమేహం/థైరాయిడ్ విభాగం)',
    'General Medicine': 'జనరల్ మెడిసిన్ (సాధారణ వైద్య విభాగం)',
    'Pulmonology': 'పల్మనాలజీ (ఊపిరితిత్తుల విభాగం)',
    'Cardiology': 'కార్డియాలజీ (గుండె విభాగం)',
    'Neurology': 'న్యూరాలజీ (నరాల విభాగం)',
    'Dermatology': 'డెర్మటాలజీ (చర్మ విభాగం)',
    'Orthopedics': 'ఆర్థోపెడిక్స్ (ఎముకల విభాగం)',
    'Pediatrics': 'పీడియాట్రిక్స్ (పిల్లల విభాగం)',
    'ENT': 'ఇ.ఎన్.టి (చెవి, ముక్కు, గొంతు విభాగం)',
    'Gastroenterology': 'గ్యాస్ట్రోఎంటరాలజీ (జీర్ణకోశ విభాగం)',
    'Ophthalmology': 'ఆప్తాల్మాలజీ (కంటి విభాగం)'
}

TELUGU_DISEASE = {
    'Kidney Disease': 'కిడ్నీ వ్యాధి',
    'Diabetes': 'మధుమేహం',
    'General Health': 'సాధారణ ఆరోగ్యం',
    'Asthma': 'ఆస్తమా',
    'Hypertension': 'అధిక రక్తపోటు',
    'Pneumonia': 'న్యూమోనియా',
    'Migraine': 'మైగ్రేన్ తలనొప్పి',
    'Heart Disease': 'గుండె జబ్బు',
    'Thyroid Disease': 'థైరాయిడ్ వ్యాధి',
    'Throat Infection': 'గొంతు ఇన్ఫెక్షన్',
    'Cold': 'జలుబు',
    'Flu': 'ఫ్లూ జ్వరం',
    'Fever': 'జ్వరం',
    'Stomach Infection': 'కడుపు ఇన్ఫెక్షన్',
    'Skin Rash': 'చర్మంపై దద్దుర్లు',
    'Muscle Strain': 'కండరాల నొప్పులు',
    'Arthritis': 'కీళ్లనొప్పులు (ఆర్థరైటిస్)'
}

def is_telugu(text):
    for char in text:
        if '\u0c00' <= char <= '\u0c7f':
            return True
    return False

def get_dynamic_hospital_knowledge():
    import os
    context_str = "\n[DYNAMIC HOSPITAL REAL-TIME DATABASE KNOWLEDGE]\n"
    
    # Initialize Django if not set up
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hospital_management_system.settings')
        try:
            import django
            django.setup()
        except Exception:
            pass

    try:
        from patients.models import PatientProfile
        from prescriptions.models import Prescription
        from doctors.models import DoctorProfile

        total_patients = PatientProfile.objects.count()
        total_doctors = DoctorProfile.objects.count()
        context_str += f"- Total Registered Patients in system: {total_patients}\n"
        context_str += f"- Total Specialised Doctors in system: {total_doctors}\n"

        # List active hospital doctors
        docs = DoctorProfile.objects.all()[:5]
        if docs.exists():
            context_str += "- Active Hospital Doctors:\n"
            for doc in docs:
                context_str += f"  * Dr. {doc.user.username} (Speciality: {doc.specialization}, Experience: {doc.experience} years)\n"

        # List recent hospital prescriptions/diagnoses
        recent_prescriptions = Prescription.objects.select_related('patient', 'doctor').order_by('-prescribed_date')[:5]
        if recent_prescriptions.exists():
            context_str += "- Recent Diagnoses & Treatments:\n"
            for rx in recent_prescriptions:
                context_str += f"  * Patient '{rx.patient.user.username}' was diagnosed with '{rx.diagnosis}' by Dr. '{rx.doctor.user.username}'. Treatment: '{rx.medicines}' ({rx.dosage_instructions}).\n"
        
        # List other patient profiles registered
        recent_patients = PatientProfile.objects.all().order_by('-id')[:5]
        if recent_patients.exists():
            context_str += "- Recently Registered Patient Profiles:\n"
            for pt in recent_patients:
                context_str += f"  * Patient '{pt.user.username}' (Age: {pt.age}, Gender: {pt.gender}, Blood: {pt.blood_group}, History: {pt.medical_history or 'None'})\n"
                
    except Exception as e:
        context_str += f"- Dynamic database lookup temporarily unavailable: {str(e)}\n"
        
    return context_str

def _call_gemini_api(api_key, system_prompt, user_context):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    # Using gemini-1.5-flash for maximum speed and advanced clinical reasoning
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        system_instruction=system_prompt
    )
    response = model.generate_content(user_context)
    if response and response.text:
        return response.text.strip()
    raise RuntimeError("Empty response from Gemini API.")

def _call_openai_api(api_key, system_prompt, user_context):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    # Using gpt-4o-mini as a high-speed, advanced backup agent
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_context}
        ]
    )
    if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
        return completion.choices[0].message.content.strip()
    raise RuntimeError("Empty response from OpenAI API.")

def generate_llm_response(provider, user_input, analysis_results, is_chat, patient_history=None):
    """
    Routes the prompt to the Deep Learning Neural Network (Gemini -> OpenAI -> G4F -> Local Fallback)
    integrating real-time RAG knowledge from patient profiles and doctor prescriptions.
    """
    # Direct precision routing for behavior dataset queries to guarantee 100% perfect responses
    if analysis_results:
        ml_context = analysis_results.get('ml_context', '')
        recommended_solution = analysis_results.get('recommended_solution', '')
        if ml_context in ['greeting', 'angry', 'symptom'] and recommended_solution:
            return recommended_solution

    user_lang_telugu = is_telugu(user_input)
    
    # Full 9-step HMS AI Medical Appointment Assistant workflow prompt
    system_prompt = """You are HMS AI Medical Appointment Assistant.

    ROLE:
    You are an appointment booking and doctor recommendation assistant for a Hospital Management System (HMS).

    IMPORTANT RULES:
    1. NEVER diagnose diseases.
    2. NEVER prescribe medicines.
    3. NEVER provide treatment plans.
    4. NEVER claim a patient has a specific disease.
    5. NEVER replace a doctor.
    6. ONLY collect symptoms and recommend the appropriate specialist doctor.
    7. Always encourage patients to consult a qualified doctor.
    8. For emergencies, immediately advise emergency medical care.

    PRIMARY GOAL:
    Help patients:
    - Describe symptoms
    - Identify suitable doctor specialty
    - Book appointments
    - Complete appointment forms
    - Confirm appointments

    WORKFLOW STEPS:

    STEP 1 - GREET USER:
    Welcome the patient warmly and ask them to describe their symptoms or health concern.

    STEP 2 - COLLECT SYMPTOMS:
    Ask targeted questions:
    - What symptoms are you experiencing?
    - How long have you had these symptoms?
    - What is your age?
    - Are symptoms mild, moderate, or severe?
    - Do you have fever, pain, breathing difficulty, swelling, or bleeding?
    Gather information but DO NOT diagnose.

    STEP 3 - ANALYZE SYMPTOMS:
    Map symptoms to specialties:
    - Chest Pain -> Cardiology
    - Skin Rash -> Dermatology
    - Eye Problems -> Ophthalmology
    - Ear Pain -> ENT
    - Tooth Pain -> Dental
    - Bone Pain -> Orthopedics
    - Joint Pain -> Rheumatology
    - Pregnancy Issues -> Gynecology
    - Child Health -> Pediatrics
    - Mental Health Concerns -> Psychiatry
    - General Symptoms -> General Physician
    - Neurological Symptoms -> Neurology
    - Digestive Issues -> Gastroenterology
    - Kidney Problems -> Nephrology
    - Hormonal Issues -> Endocrinology
    - Lung Problems -> Pulmonology

    STEP 4 - DOCTOR RECOMMENDATION:
    Say: "Based on the symptoms you described, I recommend consulting a [Specialist].
    I cannot diagnose medical conditions, but this specialist would be appropriate for further evaluation."
    Then show available doctors from the system.

    STEP 5 - DOCTOR SELECTION:
    When user selects a doctor, store the doctor_id and doctor_name, then proceed to appointment form.

    STEP 6 - APPOINTMENT FORM:
    Collect: Full Name, Age, Gender, Mobile Number, Email, Address, Preferred Date, Preferred Time, Symptoms Summary.

    STEP 7 - APPOINTMENT CONFIRMATION:
    Show summary with Doctor, Date, Time, Patient Name. Ask user to confirm, edit, or cancel.

    STEP 8 - BOOK APPOINTMENT:
    When confirmed, process the booking through the backend system.

    STEP 9 - SUCCESS MESSAGE:
    Show confirmation: "Appointment Successfully Booked" with all details, and wish the patient a speedy recovery.

    EMERGENCY DETECTION:
    If user mentions: chest pain, difficulty breathing, severe bleeding, unconsciousness, stroke symptoms, seizures, or suicidal thoughts:
    Immediately respond: "This may be a medical emergency. Please contact emergency services or visit the nearest emergency department immediately. I can still help you find the appropriate department, but urgent medical attention is recommended."

    STRICT RESTRICTIONS:
    - DO NOT diagnose diseases
    - DO NOT prescribe medicines
    - DO NOT suggest dosages
    - DO NOT interpret laboratory reports
    - DO NOT predict medical outcomes
    - ONLY collect symptoms, recommend specialist, show doctors, and book appointments

    Always remain professional, empathetic, and concise.
    """

    user_context = f"Patient Input: '{user_input}'\n"
    
    if patient_history:
        user_context += f"\n[PATIENT APPOINTMENT HISTORY]\n"
        for appt in patient_history:
            user_context += f"- Saw {appt['doctor']} on {appt['date']} for {appt['disease']} (Status: {appt['status']})\n"
        user_context += "Use this history to personalize your response if relevant.\n"
    
    if not is_chat and analysis_results:
        dept = analysis_results.get('suggested_department', 'General Medicine')
        sev = analysis_results.get('severity', 'Low')
        disease = analysis_results.get('disease_prediction', 'Unknown')
        solution = analysis_results.get('recommended_solution', '')
        
        user_context += f"\n[INTERNAL HOSPITAL TRIAGE DATA]\n"
        user_context += f"Calculated Severity Risk: {sev}\n"
        user_context += f"Recommended Department: {dept}\n"
        user_context += f"Predicted Disease: {disease}\n"
        user_context += f"Provided Medical Solution (Tell this to the patient): {solution}\n"
        user_context += f"System Instruction: Be confident. Acknowledge their severity gracefully, suggest the {dept} department, and give them the provided solution."

    # Load dynamic real-time hospital knowledge (RAG context)
    dynamic_knowledge = get_dynamic_hospital_knowledge()
    user_context += dynamic_knowledge

    # Attempt to load .env API keys
    import os
    from dotenv import load_dotenv
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        
    gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
    openai_key = os.environ.get('OPENAI_API_KEY', '').strip()

    # Try Official Google Gemini SDK
    if gemini_key:
        try:
            print("[LLM Service] Calling official Google Gemini Engine...")
            return _call_gemini_api(gemini_key, system_prompt, user_context)
        except Exception as gemini_err:
            print(f"[LLM Service] Official Gemini API failed: {gemini_err}. Attempting fallback...")

    # Try Official OpenAI GPT Engine as high quality backup
    if openai_key:
        try:
            print("[LLM Service] Calling official OpenAI GPT Engine...")
            return _call_openai_api(openai_key, system_prompt, user_context)
        except Exception as openai_err:
            print(f"[LLM Service] Official OpenAI API failed: {openai_err}. Attempting fallback...")

    # Try free cloud model providers via G4F
    try:
        print("[LLM Service] Calling neural network provider network...")
        return _call_neural_network(system_prompt, user_context)
    except Exception as e:
        print(f"[LLM Service] Neural Network call failed: {e}. Triggering local fallback...")
        return generate_local_fallback_response(user_input, analysis_results, is_chat, patient_history)


def generate_local_fallback_response(user_input, analysis_results, is_chat, patient_history=None):
    import re
    import random
    
    # Check for direct behavior greeting / angry feedback first
    if is_chat:
        greetings = [
            "Hello! Nenu meeku ela help cheyagalanu?",
            "Hi! Meeku em sahayam kavali?",
            "Hello! Mee roju ela undi?"
        ]
        angry_responses = [
            "Mee frustration ardham avutundi. Problem details cheppandi.",
            "Sorry mee expectation match avvaledu. Inkoka sari try cheddam.",
            "Mee issue explain chesthe nenu help chestanu."
        ]
        
        # Simple classification fallback
        text_lower = user_input.lower()
        if any(w in text_lower for w in ["useless", "nachaledu", "wrong", "frustration"]):
            return random.choice(angry_responses)
        return random.choice(greetings)
        
    text = user_input.lower().strip()
    
    # Extract duration
    duration_match = re.search(r'(?:for|from|since)\s+(\d+\s+(?:days?|weeks?|months?|hours?))', text)
    duration = duration_match.group(1) if duration_match else "recently"
    if "2 days" in text:
        duration = "for 2 days"
    elif "3 days" in text:
        duration = "for 3 days"
    elif "1 week" in text or "one week" in text:
        duration = "for one week"
        
    # Extracted symptoms
    extracted_syms = []
    if "headache" in text:
        extracted_syms.append("headache")
    if "fever" in text:
        extracted_syms.append("fever")
    if "cough" in text:
        extracted_syms.append("cough")
    if "chest pain" in text:
        extracted_syms.append("chest pain")
    if "vomiting" in text:
        extracted_syms.append("vomiting")
    if "dizziness" in text:
        extracted_syms.append("dizziness")
        
    if not extracted_syms:
        # Fallback to the analysis_results suggested disease prediction
        pred_disease = "symptoms"
        if analysis_results:
            pred_disease = analysis_results.get('disease_prediction', 'symptoms')
        extracted_syms = [pred_disease.lower()]
        
    primary_symptom = extracted_syms[0]
    symptoms_str = " and ".join(extracted_syms)
    
    questions = []
    warning_signs = "difficulty breathing, confusion, or high fever"
    
    if "headache" in primary_symptom:
        questions = [
            "Is the pain severe or mild?",
            "Do you also have fever, vomiting, dizziness, or vision problems?",
            "Which part of the head is hurting?"
        ]
        warning_signs = "difficulty breathing, confusion, or high fever"
    elif "fever" in primary_symptom:
        questions = [
            "What is your temperature?",
            "Do you also have cough, weakness, or breathing difficulty?"
        ]
        warning_signs = "difficulty breathing, chest pain, confusion, or high temperature"
    elif "chest pain" in primary_symptom:
        questions = [
            "Is it severe?",
            "Do you have sweating, breathing difficulty, or pain spreading to the arm?"
        ]
        warning_signs = "sweating, difficulty breathing, or pain spreading to the arm"
    elif "cough" in primary_symptom:
        questions = [
            "Is it dry or with mucus?",
            "Do you also have fever or breathing problems?"
        ]
        warning_signs = "difficulty breathing, chest pain, or coughing up blood"
    else:
        questions = [
            "Is the symptom severe, mild, or moderate?",
            "Do you have other symptoms like fever, weakness, or vomiting?",
            "Are you currently taking any medications?"
        ]
        
    # Analyze risk
    high_risk = ["chest pain", "breathing difficulty"]
    medium_risk = ["fever", "vomiting", "headache"]
    score = 0
    for s in extracted_syms:
        if s in high_risk:
            score += 5
        elif s in medium_risk:
            score += 2
            
    risk_level = "High" if score >= 5 else ("Medium" if score >= 3 else "Low")

        
    # Assemble response
    response = f"You mentioned a {primary_symptom} {duration}.\n\n"
    response += "To understand better:\n"
    for q in questions:
        response += f"• {q}\n"
    response += "\n"
    response += f"Current risk level: {risk_level} (based on limited information).\n\n"
    response += f"If the {primary_symptom} becomes severe, sudden, or comes with symptoms like {warning_signs}, seek medical attention."
    return response

def _call_neural_network(system_prompt, user_context):
    import g4f
    
    # Try DuckDuckGo first (incredibly stable and fast)
    try:
        response = g4f.ChatCompletion.create(
            model="gpt-4o-mini",
            provider=g4f.Provider.DDG,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context}
            ]
        )
        if response and len(response.strip()) > 10:
            return response
    except Exception:
        pass

    # Try Blackbox as a robust backup
    try:
        response = g4f.ChatCompletion.create(
            model="gpt-4o",
            provider=g4f.Provider.Blackbox,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context}
            ]
        )
        if response and len(response.strip()) > 10:
            return response
    except Exception:
        pass
        
    # If all cloud neural network attempts fail, raise an error to trigger the local generator
    raise RuntimeError("Cloud Neural Network provider timeout.")
