import os
import csv
import json
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.conf import settings
from django.contrib import messages

from patients.models import PatientProfile
from doctors.models import DoctorProfile
from consultations.models import Consultation, ConsultationMedia, ConsultationCallLog
from ai_assistant.apps import AIAssistantConfig
from ai_assistant.models import ChatSession, ChatMessage, SymptomEntry, DiseasePrediction, PatientMemory, RetrainQueue, WebCollectedData, DatasetEntry, TrainedModel
from ai_assistant.forms import DatasetUploadForm
from ai_assistant.dataset_manager import DatasetManager
from ai_assistant.auto_retrain import AutoRetrainer
from ai_assistant.web_collector import WebCollector

# Helper to restrict to staff/superuser
def is_admin(user):
    return user.is_active and (user.is_staff or user.is_superuser)

# Helper to check if patient
def get_patient_profile(user):
    return PatientProfile.objects.filter(user=user).first()


# ==========================================
# Patient Views
# ==========================================

@login_required
def chat_view(request):
    """
    Renders the AI Assistant chat page for logged-in patients.
    """
    patient = get_patient_profile(request.user)
    if not patient:
        messages.error(request, "Access Denied: AI Assistant is only available for patients.")
        return redirect('homepage')  # Fallback to main home or login page
        
    return render(request, 'ai_assistant/chat.html', {
        'patient': patient,
        'title': 'Smart AI Health Assistant'
    })


@login_required
@require_POST
def api_send_message(request):
    """
    AJAX endpoint for sending messages to the chatbot.
    Receives JSON: { "message": "...", "session_id": "..." }
    """
    patient = get_patient_profile(request.user)
    if not patient:
        return JsonResponse({'error': 'Unauthorized: Patient role required.'}, status=403)
        
    try:
        data = json.loads(request.body)
        message_text = data.get('message', '').strip()
        session_id_str = data.get('session_id', '').strip()
    except Exception:
        return JsonResponse({'error': 'Invalid JSON request payload.'}, status=400)
        
    if not message_text:
        return JsonResponse({'error': 'Message text is required.'}, status=400)
        
    # Resolve or create ChatSession
    session = None
    if session_id_str:
        try:
            session = ChatSession.objects.filter(patient=patient, session_id=session_id_str, is_active=True).first()
        except Exception:
            pass
            
    if not session:
        session = ChatSession.objects.create(patient=patient, is_active=True)
        
    try:
        chatbot = AIAssistantConfig.get_chatbot()
        result = chatbot.process_message(patient, message_text, session)
        
        return JsonResponse({
            'response': result['response'],
            'session_id': str(session.session_id),
            'analysis': result['analysis']
        })
    except Exception as e:
        print(f"Error processing chatbot message: {e}")
        return JsonResponse({
            'response': "I am experiencing an internal error processing your request. Please rest and consult a doctor if you feel unwell.",
            'session_id': str(session.session_id),
            'error': str(e)
        }, status=500)


@login_required
def api_chat_history(request):
    """
    AJAX endpoint to retrieve all messages for a specific session.
    """
    patient = get_patient_profile(request.user)
    if not patient:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    session_id_str = request.GET.get('session_id', '')
    if not session_id_str:
        return JsonResponse({'error': 'session_id is required.'}, status=400)
        
    session = get_object_or_404(ChatSession, patient=patient, session_id=session_id_str)
    
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
        'language': session.language,
        'risk_level': session.risk_level,
        'extracted_symptoms': session.extracted_symptoms,
        'messages': history
    })


@login_required
def api_sessions(request):
    """
    AJAX endpoint to retrieve list of past chat sessions.
    """
    patient = get_patient_profile(request.user)
    if not patient:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    sessions = ChatSession.objects.filter(patient=patient).order_by('-started_at')
    data = []
    for s in sessions:
        # Get snippet of first user message
        first_msg = s.messages.filter(role='user').first()
        snippet = first_msg.content[:40] + "..." if first_msg else "New Conversation"
        
        data.append({
            'session_id': str(s.session_id),
            'started_at': s.started_at.strftime('%Y-%m-%d %I:%M %p'),
            'risk_level': s.risk_level,
            'language': s.get_language_display(),
            'snippet': snippet
        })
        
    return JsonResponse({'sessions': data})


# ==========================================
# Admin Views
# ==========================================

@login_required
@user_passes_test(is_admin)
def admin_ai_dashboard(request):
    """
    AI Dashboard displaying statistics, model registry, and retraining controls.
    """
    stats = {
        'total_sessions': ChatSession.objects.count(),
        'total_messages': ChatMessage.objects.count(),
        'total_predictions': DiseasePrediction.objects.count(),
        'pending_retrain': RetrainQueue.objects.filter(status='pending').count(),
        'risk_critical': ChatSession.objects.filter(risk_level='critical').count(),
        'risk_high': ChatSession.objects.filter(risk_level='high').count(),
        'risk_medium': ChatSession.objects.filter(risk_level='medium').count(),
        'risk_low': ChatSession.objects.filter(risk_level='low').count()
    }
    
    # Active models
    active_models = TrainedModel.objects.filter(is_active=True)
    
    # Recent predictions
    recent_predictions = DiseasePrediction.objects.all().order_by('-predicted_at')[:8]
    
    # Recent queue items
    recent_queue = RetrainQueue.objects.all().order_by('-created_at')[:5]
    
    return render(request, 'ai_assistant/ai_dashboard.html', {
        'stats': stats,
        'active_models': active_models,
        'recent_predictions': recent_predictions,
        'recent_queue': recent_queue,
        'title': 'AI Assistant Management Dashboard'
    })


@login_required
@user_passes_test(is_admin)
def admin_collected_data(request):
    """
    Verification dashboard for web collected data.
    """
    if request.method == 'POST':
        data_id = request.POST.get('data_id')
        action = request.POST.get('action')  # 'verify' or 'reject'
        
        item = get_object_or_404(WebCollectedData, id=data_id)
        
        if action == 'verify':
            item.is_verified = True
            item.is_rejected = False
            item.verified_by = request.user
            item.verified_at = timezone.now()
            item.save()
            
            # Save verified content into unified DatasetEntry
            DatasetEntry.objects.create(
                category=item.category,
                data={
                    'title': item.title,
                    'content': item.content,
                    'source': item.url
                },
                source='web_collector',
                language='en',
                is_active=True
            )
            messages.success(request, f"Article '{item.title}' verified and saved to training dataset.")
            
        elif action == 'reject':
            item.is_verified = False
            item.is_rejected = True
            item.verified_by = request.user
            item.verified_at = timezone.now()
            item.save()
            messages.info(request, f"Article '{item.title}' marked as rejected.")
            
        return redirect('admin_collected_data')
        
    collected_list = WebCollectedData.objects.all().order_by('-collected_at')
    return render(request, 'ai_assistant/collected_data.html', {
        'collected_list': collected_list,
        'title': 'Verify Scraped Web Content'
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def admin_trigger_retrain(request):
    """
    Manually force a full check and retraining process.
    """
    try:
        ar = AutoRetrainer()
        # Force=True bypasses the threshold check and retrains immediately if there is any pending data
        triggered = ar.check_and_retrain(force=True)
        if triggered:
            messages.success(request, "Model retraining completed successfully. All engines hot-reloaded.")
        else:
            messages.warning(request, "No pending queue items available to retrain.")
    except Exception as e:
        messages.error(request, f"Retraining failed: {e}")
        
    return redirect('admin_ai_dashboard')


@login_required
@user_passes_test(is_admin)
def admin_manage_datasets(request):
    """
    CRUD and overview interface for CSV datasets inside datasets/ directory.
    """
    dm = DatasetManager()
    dataset_names = ['symptoms', 'diseases', 'medicines', 'conversations', 'telugu', 'english']
    dataset_stats = []
    
    for name in dataset_names:
        stats = dm.get_statistics(name)
        file_path = os.path.join(dm.dataset_dir, f"{name}.csv")
        modified = ""
        if os.path.exists(file_path):
            mtime = os.path.getmtime(file_path)
            modified = timezone.make_aware(timezone.datetime.fromtimestamp(mtime)).strftime('%Y-%m-%d %H:%M:%S')
            
        dataset_stats.append({
            'name': name,
            'row_count': stats.get('row_count', 'N/A'),
            'columns': ", ".join(stats.get('columns', [])),
            'modified': modified,
            'has_nulls': any(v > 0 for v in stats.get('null_counts', {}).values()) if 'null_counts' in stats else False
        })
        
    # Handle CSV upload
    if request.method == 'POST':
        form = DatasetUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dataset_name = form.cleaned_data['dataset_name']
            csv_file = request.FILES['csv_file']
            
            try:
                # Read CSV and validate columns
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.reader(decoded_file)
                headers = next(reader)
                
                # Check file schema
                temp_df = pd.read_csv(csv_file)
                
                # Backup and overwrite
                dm.backup_dataset(dataset_name)
                dm.save_dataset(dataset_name, temp_df)
                
                messages.success(request, f"Dataset '{dataset_name}.csv' updated successfully.")
                return redirect('admin_manage_datasets')
            except Exception as e:
                messages.error(request, f"Failed to upload dataset: {e}")
    else:
        form = DatasetUploadForm()
        
    # Read unsupervised clusters findings if file exists
    discovered_patterns = {}
    patterns_path = os.path.join(dm.dataset_dir, 'discovered_patterns.json')
    if os.path.exists(patterns_path):
        try:
            with open(patterns_path, 'r', encoding='utf-8') as f:
                discovered_patterns = json.load(f)
        except Exception:
            pass
            
    return render(request, 'ai_assistant/manage_datasets.html', {
        'dataset_stats': dataset_stats,
        'discovered_patterns': discovered_patterns,
        'form': form,
        'title': 'Manage Medical CSV Datasets'
    })


@login_required
@user_passes_test(is_admin)
def download_dataset(request, name):
    """
    Stream a dataset CSV file for download.
    """
    dm = DatasetManager()
    file_path = os.path.join(dm.dataset_dir, f"{name}.csv")
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="text/csv")
            response['Content-Disposition'] = f'attachment; filename={name}.csv'
            return response
    messages.error(request, "File not found.")
    return redirect('admin_manage_datasets')


@login_required
def api_upload_media(request):
    """
    Handles secure patient-doctor file uploads from the MediBot interface.
    Saves to /media/uploads/patient_{id}/doctor_{id}/filename
    """
    patient = get_patient_profile(request.user)
    if not patient:
        return JsonResponse({'error': 'Unauthorized: Patient profile required.'}, status=403)

    if request.method != 'POST' or not request.FILES.get('file'):
        return JsonResponse({'error': 'No file uploaded or invalid method.'}, status=400)

    uploaded_file = request.FILES['file']
    session_id_str = request.POST.get('session_id', '').strip()
    
    # Try to find an active doctor from the active session state
    doctor = None
    if session_id_str:
        session = ChatSession.objects.filter(patient=patient, session_id=session_id_str, is_active=True).first()
        if session and isinstance(session.predicted_diseases, dict):
            doc_id = session.predicted_diseases.get('doctor_id')
            if doc_id:
                doctor = DoctorProfile.objects.filter(id=doc_id).first()

    # Fallback to first doctor if no doctor selected yet
    if not doctor:
        doctor = DoctorProfile.objects.first()
        if not doctor:
            return JsonResponse({'error': 'No doctors available in system to assign media.'}, status=400)

    # Find or create a consultation for tracking
    consultation = Consultation.objects.filter(patient=patient, doctor=doctor, status='ongoing').first()
    if not consultation:
        consultation = Consultation.objects.create(
            patient=patient,
            doctor=doctor,
            consultation_type='chat',
            status='ongoing',
            scheduled_date=timezone.now(),
            notes="Consultation started via MediBot chat file upload."
        )

    # Save to ConsultationMedia
    try:
        media = ConsultationMedia.objects.create(
            consultation=consultation,
            patient=patient,
            doctor=doctor,
            file=uploaded_file,
            description="Secure file uploaded through MediBot"
        )
        
        # Let chatbot know of upload by creating a user notification message in background
        if session_id_str:
            session = ChatSession.objects.filter(patient=patient, session_id=session_id_str, is_active=True).first()
            if session:
                msg_content = f"[Uploaded File: {uploaded_file.name}]"
                ChatMessage.objects.create(
                    session=session,
                    role='user',
                    content=msg_content,
                    translated_content=msg_content
                )
                # Let bot respond to confirm upload
                resp = (
                    f"Nenu mee file ni confirm chesanu: **{uploaded_file.name}**.\n"
                    f"Idi secure path `/media/uploads/patient_{patient.id}/doctor_{doctor.id}/{uploaded_file.name}` lo store cheyabadindi. "
                    f"Dr. {doctor.user.last_name} matrame deenni chudagalaru.\n\n"
                    f"Nenu doctor kadu. Idi general information matrame. Final ga doctor tho consult cheyandi."
                )
                ChatMessage.objects.create(session=session, role='bot', content=resp)
        
        return JsonResponse({
            'status': 'success',
            'filename': uploaded_file.name,
            'media_id': media.id,
            'secure_path': media.file.name,
            'message': f"Securely uploaded to /media/uploads/patient_{patient.id}/doctor_{doctor.id}/{uploaded_file.name}"
        })
    except Exception as e:
        return JsonResponse({'error': f"Failed to save media: {str(e)}"}, status=500)


@login_required
@require_POST
def api_log_call(request):
    """
    Logs voice/video call sessions centrally in Django consultations.
    """
    patient = get_patient_profile(request.user)
    if not patient:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    try:
        data = json.loads(request.body)
        session_id_str = data.get('session_id')
        duration = int(data.get('duration_seconds', 0))
        call_type = data.get('call_type', 'video')
        camera = bool(data.get('camera_used', False))
        mic = bool(data.get('mic_used', False))
        screen = bool(data.get('screen_share_used', False))
        
        doctor = None
        if session_id_str:
            session = ChatSession.objects.filter(patient=patient, session_id=session_id_str).first()
            if session and isinstance(session.predicted_diseases, dict):
                doc_id = session.predicted_diseases.get('doctor_id')
                if doc_id:
                    doctor = DoctorProfile.objects.filter(id=doc_id).first()
                    
        if not doctor:
            doctor = DoctorProfile.objects.first()
            
        consultation = Consultation.objects.filter(patient=patient, doctor=doctor, consultation_type=call_type, status='ongoing').first()
        if not consultation:
            consultation = Consultation.objects.create(
                patient=patient,
                doctor=doctor,
                consultation_type=call_type,
                status='completed',
                scheduled_date=timezone.now(),
                notes=f"{call_type.capitalize()} call session logged via MediBot."
            )
        else:
            consultation.status = 'completed'
            consultation.save()
            
        # Create Call Log entry
        log = ConsultationCallLog.objects.create(
            consultation=consultation,
            duration_seconds=duration,
            started_at=timezone.now() - timezone.timedelta(seconds=duration),
            ended_at=timezone.now(),
            camera_used=camera,
            mic_used=mic,
            screen_share_used=screen
        )
        
        return JsonResponse({
            'status': 'success',
            'log_id': log.id,
            'message': 'Call session logged centrally in Django database.'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
