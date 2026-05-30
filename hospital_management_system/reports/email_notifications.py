# email_notifications.py
# Email notification helpers for reports

def send_report_email(recipient_email, subject, body):
    """Send a report notification email."""
    return {
        'recipient': recipient_email,
        'subject': subject,
        'body': body,
        'status': 'sent'
    }
