from django.urls import path
from .views import (
    signup, login_view, PatientListCreateView,
    MedicalRecordAddView, PatientMedicalRecordListView,
    PatientDetailView
)

urlpatterns = [
    # Authentication
    path('signup/', signup, name='signup'),
    path('login/', login_view, name='login'),

    # Patient Endpoints (Doctor/Admin)
    path('patients/', PatientListCreateView.as_view(), name='patient-list-create'),
    path('patients/<int:pk>/', PatientDetailView.as_view(), name='patient-detail'), # Added for admin to retrieve specific patient

    # Medical Record Endpoints (Doctor/Admin)
    path('patients/records/add/', MedicalRecordAddView.as_view(), name='medical-record-add'),
    path('patients/<int:pk>/records/', PatientMedicalRecordListView.as_view(), name='patient-medical-records'),
]