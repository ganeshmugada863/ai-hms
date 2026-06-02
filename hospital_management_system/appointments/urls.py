from django.urls import path
from .views import (
    book_appointment,
    appointment_list,
    doctor_add_appointment,
    edit_appointment,
    complete_appointment,
    acknowledge_appointment,
    update_appointment_status,
    manage_appointments,
    appointment_detail,
    api_search_appointments,
)

urlpatterns = [
    path('book/', book_appointment, name='book_appointment'),
    path('list/', appointment_list, name='appointment_list'),
    path('manage/', manage_appointments, name='manage_appointments'),
    path('doctor-add/', doctor_add_appointment, name='doctor_add_appointment'),
    path('edit/<int:appointment_id>/', edit_appointment, name='edit_appointment'),
    path('<int:appointment_id>/', appointment_detail, name='appointment_detail'),
    path('<int:appointment_id>/complete/', complete_appointment, name='complete_appointment'),
    path('<int:appointment_id>/acknowledge/', acknowledge_appointment, name='acknowledge_appointment'),
    path('update/<int:appointment_id>/<str:status>/', update_appointment_status, name='update_appointment_status'),
    path('api/search/', api_search_appointments, name='api_search_appointments'),
]