from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('api/send/', views.api_send_message, name='api_send'),
    path('api/history/', views.api_chat_history, name='api_history'),
    path('api/sessions/', views.api_sessions, name='api_sessions'),
    
    # Fallbacks for admin views to prevent NoReverseMatch template errors
    path('dashboard/', views.chat_view, name='ai_dashboard'),
    path('collected-data/', views.chat_view, name='collected_data'),
    path('retrain/', views.chat_view, name='trigger_retrain'),
    path('datasets/', views.chat_view, name='manage_datasets'),
    path('datasets/download/<str:name>/', views.chat_view, name='download_dataset'),
]
