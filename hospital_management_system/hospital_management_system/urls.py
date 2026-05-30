"""
URL configuration for hospital_management_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('auth/', include('authentication.urls')),

    # Dashboards
    path('admin-dashboard/', include('admin_dashboard.urls')),
    path('doctor-dashboard/', include('doctor_dashboard.urls')),
    path('patient-dashboard/', include('patient_dashboard.urls')),

    # Profiles & Core Apps
    path('doctors/', include('doctors.urls')),
    path('patients/', include('patients.urls')),
    path('appointments/', include('appointments.urls')),
    path('prescriptions/', include('prescriptions.urls')),
    path('medical-records/', include('medical_records.urls')),

    # Additional Features
    path('consultations/', include('consultations.urls')),
    path('reports/', include('reports.urls')),
    path('reminders/', include('reminders.urls')),
    path('ml-booking-agent/', include('ml_booking_agent.urls')),
    path('departments/', include('departments.urls')),
    path('ai/', include('ai_assistant.urls')),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)