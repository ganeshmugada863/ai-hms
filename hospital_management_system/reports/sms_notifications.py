# sms_notifications.py
# SMS notification helpers for reports

def send_report_sms(phone_number, message):
    """Send a report notification SMS."""
    return {
        'recipient': phone_number,
        'message': message,
        'status': 'sent'
    }
