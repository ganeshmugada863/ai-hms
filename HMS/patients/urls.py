from django.urls import path
from .views import create_patient_profile, doctor_patient_list

urlpatterns = [
    path('create-profile/', create_patient_profile, name='create_patient_profile'),
    path('my-patients/', doctor_patient_list, name='doctor_patient_list'),
]