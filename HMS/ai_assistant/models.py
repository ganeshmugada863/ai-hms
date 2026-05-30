import uuid
from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE, related_name='chat_sessions')
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    language = models.CharField(max_length=5, choices=[('en', 'English'), ('te', 'Telugu')], default='en')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    extracted_symptoms = models.JSONField(default=list, blank=True)
    predicted_diseases = models.JSONField(default=list, blank=True)
    risk_level = models.CharField(max_length=20, blank=True, default='')

    def __str__(self):
        return f"ChatSession {self.session_id} - Patient: {self.patient.user.username} ({self.language})"

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('bot', 'Bot')])
    content = models.TextField()
    translated_content = models.TextField(blank=True, default='')
    symptoms_extracted = models.JSONField(default=list, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.role.capitalize()} in {self.session.session_id} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

class SymptomEntry(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='symptom_entries')
    symptom_name = models.CharField(max_length=200)
    symptom_name_te = models.CharField(max_length=200, blank=True, default='')
    confidence = models.FloatField(default=0.0)
    category = models.CharField(max_length=100, blank=True, default='')
    extracted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.symptom_name} ({self.confidence:.2f}) - Msg ID: {self.message.id}"

class DiseasePrediction(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='predictions')
    disease_name = models.CharField(max_length=200)
    disease_name_te = models.CharField(max_length=200, blank=True, default='')
    confidence = models.FloatField(default=0.0)
    risk_level = models.CharField(
        max_length=20, 
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], 
        default='low'
    )
    department = models.CharField(max_length=200, blank=True, default='')
    recommended_action = models.TextField(blank=True, default='')
    predicted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.disease_name} ({self.confidence:.2f}) - Risk: {self.risk_level}"

class PatientMemory(models.Model):
    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE, related_name='ai_memories')
    key = models.CharField(max_length=200)
    value = models.JSONField(default=dict)
    category = models.CharField(
        max_length=100, 
        choices=[
            ('allergy', 'Allergy'),
            ('chronic', 'Chronic Condition'),
            ('medication', 'Current Medication'),
            ('family_history', 'Family History'),
            ('lifestyle', 'Lifestyle'),
            ('past_diagnosis', 'Past Diagnosis'),
            ('other', 'Other')
        ], 
        default='other'
    )
    source = models.CharField(max_length=50, default='chat')
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['patient', 'key']

    def __str__(self):
        return f"{self.patient.user.username} Memory: {self.category} -> {self.key}"

class RetrainQueue(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='retrain_entries', null=True, blank=True)
    status = models.CharField(
        max_length=20, 
        choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], 
        default='pending'
    )
    priority = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"QueueItem {self.id} - Status: {self.status} (Created: {self.created_at.strftime('%Y-%m-%d')})"

class WebCollectedData(models.Model):
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=500)
    content = models.TextField()
    category = models.CharField(
        max_length=100, 
        choices=[('symptom', 'Symptom'), ('disease', 'Disease'), ('medicine', 'Medicine'), ('treatment', 'Treatment')], 
        default='symptom'
    )
    is_verified = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    collected_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title[:50]} (Source: {self.url[:30]}) - Category: {self.category}"

class DatasetEntry(models.Model):
    category = models.CharField(
        max_length=50, 
        choices=[('symptom', 'Symptom'), ('disease', 'Disease'), ('medicine', 'Medicine'), ('conversation', 'Conversation')]
    )
    data = models.JSONField(default=dict)
    source = models.CharField(max_length=100, default='manual')
    language = models.CharField(max_length=5, default='en')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DatasetEntry {self.id} - Cat: {self.category} ({self.language})"

class TrainedModel(models.Model):
    model_type = models.CharField(
        max_length=50, 
        choices=[('symptom', 'Symptom Model'), ('disease', 'Disease Model'), ('risk', 'Risk Model')]
    )
    file_path = models.CharField(max_length=500)
    accuracy = models.FloatField(default=0.0)
    precision_score = models.FloatField(default=0.0)
    recall_score = models.FloatField(default=0.0)
    version = models.IntegerField(default=1)
    training_samples = models.IntegerField(default=0)
    trained_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-trained_at']

    def __str__(self):
        return f"{self.get_model_type_display()} v{self.version} - Accuracy: {self.accuracy:.2%}"
