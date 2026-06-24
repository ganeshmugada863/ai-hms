from django.urls import path
from .views import (
    create_reminder,
    mark_all_notifications_read,
    notifications_list,
    mark_notification_read,
    delete_notification,
    clear_all_notifications
)

urlpatterns = [
    path('', create_reminder, name='create_reminder'),
    path('mark-all-read/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/', notifications_list, name='notifications_list'),
    path('mark-read/<int:notification_id>/', mark_notification_read, name='mark_notification_read'),
    path('delete/<int:notification_id>/', delete_notification, name='delete_notification'),
    path('clear-all/', clear_all_notifications, name='clear_all_notifications'),
]