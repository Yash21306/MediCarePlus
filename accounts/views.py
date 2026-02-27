from django.http import HttpResponse
from django.shortcuts import render, redirect
from .forms import DoctorRegisterForm, PharmacistRegisterForm
from django.contrib.auth.decorators import login_required
from patients.models import Patient
from pharmacy.models import Medicine
from pharmacy.services import (
    get_low_stock_medicines,
    get_near_expiry_batches,
    get_expired_batches
)
from billing.services.report_service import ReportService
import json

def doctor_register(request):
    if request.method == 'POST':
        form = DoctorRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('login')
        else:
            print(form.errors)  # 👈 ADD THIS
    else:
        form = DoctorRegisterForm()

    return render(request, 'accounts/register.html', {'form': form, 'role': 'Doctor'})


def pharmacist_register(request):
    if request.method == 'POST':
        form = PharmacistRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = PharmacistRegisterForm()

    return render(request, 'accounts/register.html', {'form': form, 'role': 'Pharmacist'})

@login_required
def role_redirect(request):
    user = request.user

    # Admin first
    if user.is_superuser:
        return redirect('/admin/')

    # If not approved → pending page
    if not user.is_approved:
        return redirect('pending')

    # Role-based redirect
    if user.role == 'DOCTOR':
        return redirect('doctor_dashboard')

    elif user.role == 'PHARMACIST':
        return redirect('pharmacist_dashboard')

    return redirect('login')


@login_required
def pending_view(request):
    return render(request, 'accounts/pending.html')

@login_required
def doctor_dashboard(request):
    if request.user.role != 'DOCTOR':
        return redirect('login')

    if not request.user.is_approved:
        return redirect('pending')
    
    patient_count = Patient.objects.filter(created_by=request.user).count()

    context = {
        "user": request.user,
        "patient_count": patient_count,
    }
    return render(request, "accounts/doctor_dashboard.html", context)


@login_required
def pharmacist_dashboard(request):
    if request.user.role != 'PHARMACIST':
        return redirect('login')

    if not request.user.is_approved:
        return redirect('pending')
    
    patient_count = Patient.objects.filter(created_by=request.user).count()

    top_data = ReportService.top_selling_medicines()

    labels = [item["medicine__name"] for item in top_data]
    values = [item["total_sold"] for item in top_data]

    trend_labels, trend_values = ReportService.last_7_days_revenue()

    context = {
        "user": request.user,
        "patient_count": patient_count,

        "total_medicines": Medicine.objects.count(),
        "low_stock_count": get_low_stock_medicines().count(),
        "near_expiry_count": get_near_expiry_batches().count(),
        "expired_count": get_expired_batches().count(),    

        "total_revenue": ReportService.total_revenue(),
        "today_revenue": ReportService.today_revenue(),
        "today_sales_count": ReportService.today_sales_count(),
        "monthly_revenue": ReportService.monthly_revenue(),

        "top_medicines": ReportService.top_selling_medicines(), 

        "top_labels_json": json.dumps(labels),
        "top_values_json": json.dumps(values),  

        "trend_labels_json": json.dumps(trend_labels),
        "trend_values_json": json.dumps(trend_values),                 
    }

    context.update({
        "trend_labels_json": json.dumps(trend_labels),
        "trend_values_json": json.dumps(trend_values),
        "trend_labels_json": json.dumps(trend_labels),
        "trend_values_json": json.dumps(trend_values),
    })

    return render(request, "accounts/pharmacist_dashboard.html", context)

def home(request):
    user = request.user

    if user.is_authenticated:

        # Admin first
        # if user.is_superuser:
        #     return redirect('/admin/')

        # If not approved
        if not user.is_approved:
            return redirect('pending')

        # Role-based redirect
        if user.role == 'DOCTOR':
            return redirect('doctor_dashboard')

        elif user.role == 'PHARMACIST':
            return redirect('pharmacist_dashboard')

    return render(request, 'accounts/home.html')
