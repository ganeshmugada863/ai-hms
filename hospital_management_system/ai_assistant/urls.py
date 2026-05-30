from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    # Patient-facing chat views
    path('', views.chat_view, name='chat'),
    path('api/send/', views.api_send_message, name='api_send'),
    path('api/history/', views.api_chat_history, name='api_history'),
    path('api/sessions/', views.api_sessions, name='api_sessions'),
    path('api/upload/', views.api_upload_media, name='api_upload'),
    path('api/log-call/', views.api_log_call, name='api_log_call'),

    # Admin-facing dashboards and management views
    path('dashboard/', views.admin_ai_dashboard, name='ai_dashboard'),
    path('collected-data/', views.admin_collected_data, name='collected_data'),
    path('retrain/', views.admin_trigger_retrain, name='trigger_retrain'),
    path('datasets/', views.admin_manage_datasets, name='manage_datasets'),
    path('datasets/download/<str:name>/', views.download_dataset, name='download_dataset'),
]
