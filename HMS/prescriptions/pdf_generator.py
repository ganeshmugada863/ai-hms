from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
import io

def generate_prescription_pdf(prescription):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    p.setFont("Helvetica-Bold", 24)
    p.setFillColor(colors.HexColor("#4facfe"))
    p.drawString(1 * inch, height - 1 * inch, "MediCare")
    
    p.setFont("Helvetica", 10)
    p.setFillColor(colors.black)
    p.drawString(1 * inch, height - 1.2 * inch, "Premium Healthcare Services")
    p.line(1 * inch, height - 1.3 * inch, width - 1 * inch, height - 1.3 * inch)

    # Doctor Info
    p.setFont("Helvetica-Bold", 12)
    p.drawString(1 * inch, height - 1.8 * inch, f"Dr. {prescription.doctor.user.username}")
    p.setFont("Helvetica", 10)
    p.drawString(1 * inch, height - 2.0 * inch, f"Specialization: {prescription.doctor.specialization}")
    
    # Patient Info
    p.setFont("Helvetica-Bold", 12)
    p.drawString(width - 3 * inch, height - 1.8 * inch, "Patient Details")
    p.setFont("Helvetica", 10)
    p.drawString(width - 3 * inch, height - 2.0 * inch, f"Name: {prescription.patient.user.username}")
    p.drawString(width - 3 * inch, height - 2.2 * inch, f"Date: {prescription.prescribed_date.strftime('%Y-%m-%d')}")

    # Diagnosis
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1 * inch, height - 3.0 * inch, "Diagnosis")
    p.setFont("Helvetica", 12)
    p.drawString(1 * inch, height - 3.3 * inch, prescription.diagnosis)

    # Prescription
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1 * inch, height - 4.0 * inch, "Prescription (Rx)")
    
    # Medicines list
    text_object = p.beginText(1 * inch, height - 4.3 * inch)
    text_object.setFont("Helvetica", 12)
    text_object.setLeading(20)
    
    for med in prescription.medicines.split('\n'):
        text_object.textLine(f"• {med}")
    
    p.drawText(text_object)

    # Dosage Instructions
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1 * inch, height - 6.5 * inch, "Instructions")
    p.setFont("Helvetica", 12)
    p.drawString(1 * inch, height - 6.8 * inch, prescription.dosage_instructions)

    # Footer
    p.setFont("Helvetica-Oblique", 10)
    p.drawCentredString(width / 2, 0.5 * inch, "This is a computer-generated prescription. MediCare Healthcare v6.0")

    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer
