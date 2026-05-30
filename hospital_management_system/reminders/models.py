from django.db import models

# Create your models here.
from django.db import models
from authentication.models import CustomUser

class Reminder(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    reminder_title = models.CharField(max_length=255)
    reminder_date = models.DateField()
    reminder_time = models.TimeField()

    REMINDER_TYPES = [
        ('medicine', 'Medicine'),
        ('appointment', 'Appointment'),
        ('follow_up', 'Follow-up'),
    ]
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES, default='medicine')
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.reminder_title

class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default='appointment')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.title}"