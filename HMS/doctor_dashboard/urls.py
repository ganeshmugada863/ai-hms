from django.urls import path
from . import views

from django.urls import path
from .views import doctor_dashboard

urlpatterns = [
    path('', doctor_dashboard, name='doctor_dashboard'),
]