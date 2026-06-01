import uuid
import json
from django.db import models
from authentication.models import CustomUser
from patients.models import PatientProfile

class ChatSession(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='ai_chat_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    language = models.CharField(max_length=10, default='en')
    risk_level = models.CharField(max_length=20, default='low')
    context_data = models.TextField(default='{}')  # Stores session memory JSON (e.g., preferred doctor, previous queries)

    def get_memory(self):
        try:
            return json.loads(self.context_data)
        except Exception:
            return {}

    def set_memory(self, data):
        self.context_data = json.dumps(data)
        self.save()

    def __str__(self):
        return f"Session {str(self.session_id)[:8]} - {self.patient.user.username}"


class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10)  # 'user' or 'bot'
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role.capitalize()} message in {str(self.session.session_id)[:8]}"


class AIAuditLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    query = models.TextField()
    action = models.CharField(max_length=100)  # e.g., 'Retrieved Appointment History', 'Blocked unauthorized access'
    result = models.TextField()                # e.g., 'Returned 1 active appointment', 'Permission Denied'
    ip_address = models.CharField(max_length=50, blank=True, null=True)
    device = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"Audit: {username} - {self.action} at {self.timestamp}"
