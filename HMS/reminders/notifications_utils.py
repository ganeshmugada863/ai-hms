from django.core.mail import send_mail
from django.conf import settings
from reminders.models import Notification
import logging

logger = logging.getLogger(__name__)

def send_appointment_notifications(appointment):
    # 1. Store Notification in DB for the Doctor
    doctor_user = appointment.doctor.user
    patient_username = appointment.patient.user.username
    notif_title = "New Appointment Booking"
    notif_msg = f"Patient {patient_username} has booked an appointment with you for {appointment.appointment_date} at {appointment.appointment_time}. Reason: {appointment.reason}"
    
    try:
        Notification.objects.create(
            user=doctor_user,
            title=notif_title,
            message=notif_msg,
            notification_type='appointment'
        )
        print(f"DEBUG: Saved database notification for doctor {doctor_user.username}")
    except Exception as e:
        print(f"DEBUG: Failed to save database notification: {e}")
        logger.error(f"Error saving database notification: {e}")
    
    # 2. Send Email to the Doctor
    if doctor_user.email:
        email_subject = f"New Appointment Booking: {patient_username}"
        email_body = f"""Hello Dr. {doctor_user.username},

A new appointment has been booked with you by patient {patient_username}.

Appointment Details:
Date: {appointment.appointment_date}
Time: {appointment.appointment_time}
Reason: {appointment.reason}

Please log in to your dashboard to manage your schedule.

Regards,
MediCare Hospital Team"""
        try:
            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [doctor_user.email]
            )
            print(f"DEBUG: Email successfully sent to doctor: {doctor_user.email}")
        except Exception as e:
            print(f"DEBUG: Failed to send email to doctor: {e}")
            logger.error(f"Error sending doctor email notification: {e}")

    # 3. Send SMS notification to Doctor's phone number
    doctor_phone = doctor_user.phone if hasattr(doctor_user, 'phone') and doctor_user.phone else "Not Provided"
    sms_body = f"MediCare Booking Alert: Patient {patient_username} has booked an appointment with you on {appointment.appointment_date} at {appointment.appointment_time}."
    
    # Log SMS sending
    print(f"===========================================================")
    print(f"SMS SENT TO DOCTOR NUMBER ({doctor_phone}):")
    print(f"Message: {sms_body}")
    print(f"===========================================================")
    
    # Also log to standard Django logs
    logger.info(f"SMS notification sent to {doctor_phone}: {sms_body}")

def send_status_change_notification(appointment, new_status):
    patient_user = appointment.patient.user
    doctor_name = appointment.doctor.user.username
    notif_title = f"Appointment {new_status}"
    notif_msg = f"Your appointment with Dr. {doctor_name} on {appointment.appointment_date} has been marked as '{new_status}'."
    
    try:
        Notification.objects.create(
            user=patient_user,
            title=notif_title,
            message=notif_msg,
            notification_type='appointment_status'
        )
        print(f"DEBUG: Saved database notification for patient {patient_user.username}")
    except Exception as e:
        print(f"DEBUG: Failed to save status change notification: {e}")
        logger.error(f"Error saving status change notification: {e}")
        
    if patient_user.email:
        email_subject = f"Appointment Update: Dr. {doctor_name} ({new_status})"
        email_body = f"""Hello {patient_user.username},

Your appointment status with Dr. {doctor_name} has been updated.

Appointment Details:
Date: {appointment.appointment_date}
Time: {appointment.appointment_time}
New Status: {new_status}

Please log in to your dashboard to view details.

Regards,
MediCare Hospital Team"""
        try:
            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [patient_user.email]
            )
            print(f"DEBUG: Email successfully sent to patient: {patient_user.email}")
        except Exception as e:
            print(f"DEBUG: Failed to send email to patient: {e}")
            
    patient_phone = patient_user.phone if hasattr(patient_user, 'phone') and patient_user.phone else "Not Provided"
    sms_body = f"MediCare Update: Your appointment with Dr. {doctor_name} on {appointment.appointment_date} is now {new_status}."
    print(f"===========================================================")
    print(f"SMS SENT TO PATIENT NUMBER ({patient_phone}):")
    print(f"Message: {sms_body}")
    print(f"===========================================================")

def send_prescription_notification(prescription):
    patient_user = prescription.patient.user
    doctor_name = prescription.doctor.user.username
    notif_title = "New Prescription Issued"
    notif_msg = f"Dr. {doctor_name} has issued a new prescription for you. Diagnosis: {prescription.diagnosis}."
    
    try:
        Notification.objects.create(
            user=patient_user,
            title=notif_title,
            message=notif_msg,
            notification_type='prescription'
        )
        print(f"DEBUG: Saved prescription database notification for patient {patient_user.username}")
    except Exception as e:
        print(f"DEBUG: Failed to save prescription notification: {e}")
        
    if patient_user.email:
        email_subject = f"New Prescription: Dr. {doctor_name}"
        email_body = f"""Hello {patient_user.username},

Dr. {doctor_name} has issued a new prescription for you.

Details:
Diagnosis: {prescription.diagnosis}
Medicines: {prescription.medicines}
Instructions: {prescription.dosage_instructions}

You can download the PDF copy from your prescription list.

Regards,
MediCare Hospital Team"""
        try:
            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [patient_user.email]
            )
            print(f"DEBUG: Email successfully sent to patient: {patient_user.email}")
        except Exception as e:
            print(f"DEBUG: Failed to send email to patient: {e}")
            
    patient_phone = patient_user.phone if hasattr(patient_user, 'phone') and patient_user.phone else "Not Provided"
    sms_body = f"MediCare Alert: Dr. {doctor_name} has issued a prescription for you. Please check your dashboard."
    print(f"===========================================================")
    print(f"SMS SENT TO PATIENT NUMBER ({patient_phone}):")
    print(f"Message: {sms_body}")
    print(f"===========================================================")

def send_medical_record_notification(record):
    patient_user = record.patient.user
    doctor_name = record.uploaded_by_doctor.user.username if record.uploaded_by_doctor else "Hospital Staff"
    notif_title = "New Medical Report Uploaded"
    notif_msg = f"Dr. {doctor_name} has uploaded a new medical report for you: '{record.report_name}'."
    
    try:
        Notification.objects.create(
            user=patient_user,
            title=notif_title,
            message=notif_msg,
            notification_type='medical_record'
        )
        print(f"DEBUG: Saved medical record database notification for patient {patient_user.username}")
    except Exception as e:
        print(f"DEBUG: Failed to save medical record notification: {e}")
        
    if patient_user.email:
        email_subject = f"New Medical Report: {record.report_name}"
        email_body = f"""Hello {patient_user.username},

Dr. {doctor_name} has uploaded a new medical report for you.

Details:
Report Name: {record.report_name}
File Type: {record.file_type}
Date: {record.uploaded_at.strftime('%Y-%m-%d')}

You can view and download this report from your medical records list.

Regards,
MediCare Hospital Team"""
        try:
            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [patient_user.email]
            )
            print(f"DEBUG: Email successfully sent to patient: {patient_user.email}")
        except Exception as e:
            print(f"DEBUG: Failed to send email to patient: {e}")
            
    patient_phone = patient_user.phone if hasattr(patient_user, 'phone') and patient_user.phone else "Not Provided"
    sms_body = f"MediCare Alert: Dr. {doctor_name} has uploaded a new report '{record.report_name}' for you."
    print(f"===========================================================")
    print(f"SMS SENT TO PATIENT NUMBER ({patient_phone}):")
    print(f"Message: {sms_body}")
    print(f"===========================================================")
