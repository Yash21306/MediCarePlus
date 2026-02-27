from . import views
from django.urls import path
from .views import pharmacist_dashboard

urlpatterns = [
    path("dashboard/", pharmacist_dashboard, name="pharmacist_dashboard"),
    path('low-stock/', views.low_stock_medicines, name='low_stock_medicines'),
    path('near-expiry/', views.near_expiry_batches, name='near_expiry_batches'),
    path('expired-batches/', views.expired_batches, name='expired_batches'),
    path('medicines/', views.medicine_list, name='medicine_list'),
]