from django.core.mail import send_mail
from django.conf import settings

def send_appointment_reminder(appointment):
    """
    Sends an email reminder for an appointment.
    """
    subject = f"Appointment Reminder: Dr. {appointment.doctor.user.username}"
    message = f"""
    Hello {appointment.patient.user.username},

    This is a reminder for your upcoming appointment:
    Date: {appointment.appointment_date}
    Time: {appointment.appointment_time}
    Doctor: Dr. {appointment.doctor.user.username}

    Please be on time.

    Regards,
    MediCare Hospital Team
    """
    recipient_list = [appointment.patient.user.email]
    
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_medication_reminder(reminder):
    """
    Sends an email for medication reminder.
    """
    subject = f"Medication Reminder: {reminder.medication_name}"
    message = f"""
    Hello,

    Time to take your medication: {reminder.medication_name}
    Dosage: {reminder.dosage}
    Time: {reminder.reminder_time}

    Stay healthy!

    Regards,
    MediCare Hospital Team
    """
    recipient_list = [reminder.patient.user.email]
    
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
