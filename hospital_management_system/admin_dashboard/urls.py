from django.urls import path
from .views import (
    admin_dashboard, 
    admin_doctor_list, 
    admin_patient_list, 
    admin_appointment_list, 
    admin_book_appointment,
    admin_edit_appointment,
    admin_prescription_list,
    approve_doctor
)

urlpatterns = [
    path('', admin_dashboard, name='admin_dashboard'),
    path('doctors/', admin_doctor_list, name='admin_doctor_list'),
    path('doctors/approve/<int:doctor_id>/', approve_doctor, name='approve_doctor'),
    path('patients/', admin_patient_list, name='admin_patient_list'),
    path('appointments/', admin_appointment_list, name='admin_appointment_list'),
    path('appointments/book/', admin_book_appointment, name='admin_book_appointment'),
    path('appointments/edit/<int:appointment_id>/', admin_edit_appointment, name='admin_edit_appointment'),
    path('prescriptions/', admin_prescription_list, name='admin_prescription_list'),
]