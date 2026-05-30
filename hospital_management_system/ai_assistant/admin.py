from django.contrib import admin
from django.utils import timezone
from .models import (
    ChatSession, ChatMessage, SymptomEntry, DiseasePrediction,
    PatientMemory, RetrainQueue, WebCollectedData, DatasetEntry, TrainedModel
)

@admin.action(description="Verify selected web-collected records")
def bulk_verify(modeladmin, request, queryset):
    updated = queryset.update(
        is_verified=True, 
        is_rejected=False,
        verified_by=request.user,
        verified_at=timezone.now()
    )
    modeladmin.message_user(request, f"Successfully verified {updated} records.")

@admin.action(description="Reject selected web-collected records")
def bulk_reject(modeladmin, request, queryset):
    updated = queryset.update(
        is_verified=False, 
        is_rejected=True,
        verified_by=request.user,
        verified_at=timezone.now()
    )
    modeladmin.message_user(request, f"Successfully rejected {updated} records.")

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'patient', 'language', 'started_at', 'is_active', 'risk_level')
    list_filter = ('language', 'is_active', 'risk_level', 'started_at')
    search_fields = ('session_id', 'patient__user__username', 'risk_level')
    readonly_fields = ('session_id', 'started_at')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'role', 'timestamp', 'content_preview')
    list_filter = ('role', 'timestamp')
    search_fields = ('content', 'translated_content', 'session__session_id')
    readonly_fields = ('timestamp',)

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'

@admin.register(SymptomEntry)
class SymptomEntryAdmin(admin.ModelAdmin):
    list_display = ('symptom_name', 'symptom_name_te', 'confidence', 'category', 'extracted_at')
    list_filter = ('category', 'extracted_at')
    search_fields = ('symptom_name', 'symptom_name_te', 'message__session__patient__user__username')

@admin.register(DiseasePrediction)
class DiseasePredictionAdmin(admin.ModelAdmin):
    list_display = ('disease_name', 'confidence', 'risk_level', 'department', 'predicted_at')
    list_filter = ('risk_level', 'department', 'predicted_at')
    search_fields = ('disease_name', 'disease_name_te', 'session__session_id')

@admin.register(PatientMemory)
class PatientMemoryAdmin(admin.ModelAdmin):
    list_display = ('patient', 'category', 'key', 'last_updated', 'source')
    list_filter = ('category', 'source', 'last_updated')
    search_fields = ('patient__user__username', 'key')

@admin.register(RetrainQueue)
class RetrainQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'status', 'priority', 'created_at', 'processed_at')
    list_filter = ('status', 'priority', 'created_at', 'processed_at')
    search_fields = ('session__session_id', 'error_message')

@admin.register(WebCollectedData)
class WebCollectedDataAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'category', 'is_verified', 'is_rejected', 'collected_at')
    list_filter = ('category', 'is_verified', 'is_rejected', 'collected_at')
    search_fields = ('title', 'content', 'url')
    actions = [bulk_verify, bulk_reject]
    readonly_fields = ('collected_at',)

@admin.register(DatasetEntry)
class DatasetEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'source', 'language', 'is_active', 'created_at')
    list_filter = ('category', 'source', 'language', 'is_active', 'created_at')
    search_fields = ('data', 'source')

@admin.register(TrainedModel)
class TrainedModelAdmin(admin.ModelAdmin):
    list_display = ('model_type', 'version', 'accuracy', 'precision_score', 'recall_score', 'training_samples', 'is_active', 'trained_at')
    list_filter = ('model_type', 'is_active', 'trained_at')
    search_fields = ('file_path', 'version')
