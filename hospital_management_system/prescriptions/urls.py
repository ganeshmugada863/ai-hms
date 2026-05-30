from django.urls import path
from .views import (
    create_prescription, 
    view_prescriptions,
    list_prescriptions,
    edit_prescription,
    export_prescription_pdf
)

urlpatterns = [
    path('create/', create_prescription, name='create_prescription'),
    path('view/', view_prescriptions, name='view_prescriptions'),
    path('list/', list_prescriptions, name='list_prescriptions'),
    path('edit/<int:prescription_id>/', edit_prescription, name='edit_prescription'),
    path('export/<int:prescription_id>/', export_prescription_pdf, name='export_prescription_pdf'),
]
