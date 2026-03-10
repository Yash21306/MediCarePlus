from django.urls import path
from . import views

app_name = "patients"

urlpatterns = [

    path("", views.patient_list, name="patient_list"),

    path("add/", views.add_patient, name="add_patient"),

    path("<int:pk>/", views.PatientDetailView.as_view(), name="patient_detail"),

    path("edit/<int:pk>/", views.edit_patient, name="edit_patient"),

    path("delete/<int:pk>/", views.delete_patient, name="delete_patient"),

    path(
        "purchase-history/<int:pk>/",
        views.patient_purchase_history,
        name="patient_purchase_history"
    ),
]