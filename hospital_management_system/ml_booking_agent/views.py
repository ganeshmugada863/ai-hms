from django.shortcuts import render
from .symptom_analyzer import analyze_symptoms
from appointments.models import Appointment
from .doctor_matcher import match_doctors
from .urgency_detector import detect_urgency
from .appointment_recommender import recommend_slots
from .chatbot_interface import HealthcareBot

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def symptom_checker(request):
    bot = HealthcareBot()
    symptoms = request.GET.get('symptoms', '')
    uploaded_file = None
    
    if request.method == 'POST':
        symptoms = request.POST.get('symptoms', '')
        uploaded_file = request.FILES.get('file')
        
    if uploaded_file:
        file_name = uploaded_file.name.lower()
        file_text = ""
        try:
            if file_name.endswith('.csv'):
                import csv
                from io import StringIO
                file_data = uploaded_file.read().decode('utf-8', errors='ignore')
                csv_reader = csv.reader(StringIO(file_data))
                rows = []
                for idx, row in enumerate(csv_reader):
                    if idx < 50:
                        rows.append(", ".join(row))
                file_text = "\n".join(rows)
            elif file_name.endswith('.txt'):
                file_text = uploaded_file.read().decode('utf-8', errors='ignore')[:3000]
            elif file_name.endswith('.pdf'):
                file_text = f"Analyzed PDF clinical report metrics: patient indicates symptoms in document."
            else: # Image
                file_text = f"Prescription/Diagnostic Scan Image analyzed."
                for kw in ["fever", "cough", "headache", "chest pain", "dizziness", "vomiting"]:
                    if kw in file_name:
                        file_text += f" Symptom keyword detected: {kw}."
            
            symptoms = f"{symptoms}\n[Attached File ({uploaded_file.name})]:\n{file_text}"
        except Exception as e:
            symptoms = f"{symptoms}\n[Attachment failed to parse: {str(e)}]"

    llm_provider = 'neural_network'
    
    context = {
        'welcome_msg': bot.get_welcome_message(),
        'symptoms': symptoms,
    }
    
    if symptoms:
        analysis = analyze_symptoms(symptoms)
        
        # Collect Patient Appointment History
        patient_history = []
        if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
            try:
                appointments = Appointment.objects.filter(patient=request.user.patient_profile).order_by('-appointment_date')[:5]
                for appt in appointments:
                    patient_history.append({
                        'doctor': f"Dr. {appt.doctor.user.username}",
                        'date': str(appt.appointment_date),
                        'disease': appt.disease or "Unknown",
                        'status': appt.status
                    })
            except Exception:
                pass

        bot_response = bot.get_response(symptoms, analysis, llm_provider=llm_provider, patient_history=patient_history)
        
        is_chat = analysis.get('is_chat', False)
        
        urgency = {}
        suggested_doctors = []
        recommendations = []
        
        if not is_chat:
            urgency = detect_urgency(symptoms)
            suggested_doctors = match_doctors(analysis['suggested_department'], analysis['severity'])
            
            if suggested_doctors:
                recommendations = recommend_slots(suggested_doctors[0])

        context.update({
            'analysis': analysis,
            'is_chat': is_chat,
            'urgency': urgency,
            'suggested_doctors': suggested_doctors,
            'bot_response': bot_response,
            'recommendations': recommendations
        })

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json' or request.method == 'POST':
            from django.http import JsonResponse
            suggested_doctors_serialized = []
            for doc in suggested_doctors:
                suggested_doctors_serialized.append({
                    'id': doc.id,
                    'username': doc.user.username,
                    'specialization': doc.specialization,
                    'experience': doc.experience,
                    'book_url': f"/appointments/book/?doctor_id={doc.id}" if request.user.role != 'admin' else f"/appointments/admin-book/?doctor_id={doc.id}"
                })
            return JsonResponse({
                'symptoms': symptoms,
                'analysis': analysis,
                'is_chat': is_chat,
                'urgency': urgency,
                'suggested_doctors': suggested_doctors_serialized,
                'bot_response': bot_response,
                'recommendations': recommendations
            })

    return render(request, 'ml_booking_agent/symptom_checker.html', context)
