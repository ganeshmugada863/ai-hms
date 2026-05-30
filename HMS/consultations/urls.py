from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='consultations_index'),
    path('video/', views.video_call_view, name='video_call'),
    path('audio/', views.audio_call_view, name='audio_call'),
    path('chat/', views.chat_view, name='chat'),
    path('api/check-incoming-call/', views.check_incoming_call, name='check_incoming_call'),
    path('api/update-call-status/', views.update_call_status, name='update_call_status'),
    path('api/get-call-status/', views.get_call_status, name='get_call_status'),
]
