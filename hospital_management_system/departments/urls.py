from django.urls import path
from .views import departments_list, department_doctors

urlpatterns = [
    path('list/', departments_list, name='departments_list'),
    path('<int:dept_id>/doctors/', department_doctors, name='department_doctors'),
]
