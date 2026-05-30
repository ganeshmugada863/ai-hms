from django.urls import path
from .views import upload_medical_record, patient_upload_medical_record, view_medical_records, download_medical_record

urlpatterns = [
    path('upload/', upload_medical_record, name='upload_medical_record'),
    path('patient-upload/', patient_upload_medical_record, name='patient_upload_medical_record'),
    path('view/', view_medical_records, name='view_medical_records'),
    path('download/<int:record_id>/', download_medical_record, name='download_medical_record'),
]
