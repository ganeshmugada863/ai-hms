from django.urls import path
from .views import create_doctor_profile

urlpatterns = [
    path('create-profile/', create_doctor_profile, name='create_doctor_profile'),
]