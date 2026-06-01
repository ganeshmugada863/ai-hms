from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('api/send/', views.api_send_message, name='api_send'),
    path('api/history/', views.api_chat_history, name='api_history'),
    path('api/sessions/', views.api_sessions, name='api_sessions'),
]
