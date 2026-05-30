from django.urls import path
from .views import create_reminder, mark_all_notifications_read

urlpatterns = [
    path('', create_reminder, name='create_reminder'),
    path('mark-all-read/', mark_all_notifications_read, name='mark_all_notifications_read'),
]