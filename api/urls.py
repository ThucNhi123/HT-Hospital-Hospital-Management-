from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path('sign-in/', views.sign_in_view, name='sign_in'),
    path('sign-up/', views.sign_up_view, name='sign_up'),
    path('sign-out/', views.sign_out_view, name='sign_out'),
    path('patient-dashboard/', views.patient_dashboard_view, name='patient_dashboard'),
    path('delete-appointment/<str:appointment_id>/', views.delete_appointment, name='delete_appointment'),
    path('check-availability/', views.check_availability, name='check_availability'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('doctor-dashboard/', views.doctor_dashboard_view, name='doctor_dashboard'),
    path('create-treatment/', views.create_treatment_view, name='create_treatment'),
    path('get-history/<str:appointment_id>/', views.get_treatment_history, name='get_history'),
    path('my-patients/', views.my_patients_view, name='my_patients'),
    path('my-patients/<str:patient_id>/', views.patient_detail_view, name='patient_detail'),    
    path('reception-dashboard/', views.reception_billing_dashboard_view, name='reception_dashboard'),
    path('confirm-payment/<str:bill_id>/', views.confirm_payment_view, name='confirm_payment'),
    path('get-all-patients/', views.get_all_patient_records, name='get_all_patients'),
    path('get-patient-history/<str:patient_id>/', views.get_patient_history_detail, name='patient_history'),
    path('get-financial-report/', views.get_financial_report, name='financial_report'),
]
