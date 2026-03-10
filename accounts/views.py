from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .forms import DoctorRegisterForm, PharmacistRegisterForm
from django.contrib.auth.decorators import login_required
from patients.models import Patient
from pharmacy.models import Medicine, Supplier
from pharmacy.services import (
    get_low_stock_medicines,
    get_near_expiry_batches,
    get_expired_batches
)
from billing.services.report_service import ReportService
import json
from django.core.exceptions import PermissionDenied
from accounts.services.dashboard_service import DashboardService
from billing.models import InvoiceItem, Invoice
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from pharmacy.models import Batch
from django.utils import timezone
from core.utils.activity_logger import log_activity
from core.models import ActivityLog
from core.models import Notification


def doctor_register(request):

    if request.method == "POST":
        form = DoctorRegisterForm(request.POST, request.FILES)

        if form.is_valid():

            user = form.save()

            from core.models import Notification

            Notification.objects.create(
                title="New Doctor Registered",
                message=f"{user.full_name} has registered as Doctor",
                notification_type="INFO"
            )

            return redirect("login")

    else:
        form = DoctorRegisterForm()

    return render(request, "accounts/register.html", {
        "form": form,
        "role": "Doctor"
    })


def pharmacist_register(request):
    if request.method == 'POST':
        form = PharmacistRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()

        from core.models import Notification

        Notification.objects.create(
            title="New Pharmacist Registered",
            message=f"{user.full_name} has registered as Pharmacist",
            notification_type="INFO"
        )

        return redirect('login')
    else:
        form = PharmacistRegisterForm()

    return render(request, 'accounts/register.html', {'form': form, 'role': 'Pharmacist'})

@login_required
def role_redirect(request):
    user = request.user

    if not user.is_approved:
        return redirect('pending')

    if user.role == 'ADMIN':
        return redirect('admin_dashboard')

    elif user.role == 'DOCTOR':
        return redirect('doctor_dashboard')

    elif user.role == "PHARMACIST":
        return redirect("/pharmacy/dashboard/")

    return redirect('login')

@login_required
def pending_view(request):
    return render(request, 'accounts/pending.html')

@login_required
def doctor_dashboard(request):

    if request.user.role != "DOCTOR":
        raise PermissionDenied("Access restricted to doctors.")

    if not request.user.is_approved:
        return redirect("pending")

    from consultations.models import Consultation, Prescription
    from patients.models import Patient
    from django.utils import timezone

    today = timezone.now().date()

    # ---- BASIC STATS ----

    total_patients = Patient.objects.count()

    today_consultations = Consultation.objects.filter(
        doctor=request.user,
        consultation_date__date=today
    ).count()

    open_consultations = Consultation.objects.filter(
        doctor=request.user,
        status="OPEN"
    ).count()

    pending_prescriptions = Prescription.objects.filter(
        consultation__doctor=request.user,
        status="PENDING"
    ).count()

    # ---- RECENT DATA ----

    recent_patients = Patient.objects.order_by("-created_at")[:5]

    recent_consultations = Consultation.objects.filter(
        doctor=request.user
    ).select_related("patient")[:5]

    context = {
        "total_patients": total_patients,
        "today_consultations": today_consultations,
        "open_consultations": open_consultations,
        "pending_prescriptions": pending_prescriptions,
        "recent_patients": recent_patients,
        "recent_consultations": recent_consultations,
        "user": request.user
    }

    return render(
        request,
        "accounts/doctor_dashboard.html",
        context
    )

@login_required
def pharmacist_dashboard(request):

    user = request.user

    if user.role != "PHARMACIST":
        raise PermissionDenied("Access restricted to pharmacist.")

    if not user.is_approved:
        raise PermissionDenied("User not approved.")


    # ---- PERIOD FILTER ----
    period = int(request.GET.get("period", 6))


    # ---- DASHBOARD STATS ----
    context = DashboardService.pharmacist_dashboard_data()


    # ---- MONTHLY PROFIT DATA ----
    labels, revenue_values, profit_values = ReportService.monthly_profit_trend(period)
    cat_labels, cat_values = ReportService.sales_by_category()
    top_today_labels, top_today_values = ReportService.top_medicines_today()


    analytics = ReportService.dashboard_analytics()

    context.update({
        "profit_labels_json": json.dumps(labels),
        "revenue_values_json": json.dumps(revenue_values),
        "profit_values_json": json.dumps(profit_values),
        "selected_period": period,

        "category_labels_json": json.dumps(cat_labels),
        "category_values_json": json.dumps(cat_values),

        "top_today_labels_json": json.dumps(top_today_labels),
        "top_today_values_json": json.dumps(top_today_values),

        "monthly_growth": analytics["monthly_growth"],
        "most_profitable": analytics["most_profitable"],
        "stock_value": analytics["stock_value"]
    })


    context["user"] = user

    return render(
        request,
        "accounts/pharmacist_dashboard.html",
        context
    )

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

def live_sales_data(request):

    today = timezone.now().date()

    revenue = (
        InvoiceItem.objects
        .filter(invoice__created_at__date=today)
        .aggregate(total=Sum("total_with_tax"))
    )["total"] or 0

    return JsonResponse({
        "today_revenue": float(revenue)
    })

User = get_user_model()


@login_required
def admin_dashboard(request):

    today = timezone.now().date()

    # -------- INVENTORY ALERTS --------

    low_stock = get_low_stock_medicines()
    near_expiry_batches = get_near_expiry_batches()
    expired_batches = get_expired_batches()

    # LOW STOCK ALERTS
    for med in low_stock:

        Notification.objects.get_or_create(
            title=f"Low Stock Alert - {med.name}",
            defaults={
                "message": f"{med.name} stock is low ({med.stock_quantity} left)",
                "notification_type": "WARNING"
            }
        )

    # NEAR EXPIRY ALERTS
    for batch in near_expiry_batches:

        Notification.objects.get_or_create(
            title=f"Near Expiry - {batch.medicine.name}",
            defaults={
                "message": f"{batch.medicine.name} batch {batch.batch_number} expiring soon",
                "notification_type": "WARNING"
            }
        )

    # EXPIRED ALERTS
    for batch in expired_batches:

        Notification.objects.get_or_create(
            title=f"Expired Medicine - {batch.medicine.name}",
            defaults={
                "message": f"{batch.medicine.name} batch {batch.batch_number} expired",
                "notification_type": "CRITICAL"
            }
        )

    if request.user.role != "ADMIN":
        raise PermissionDenied("Admin access required")

    today = timezone.now().date()

    # -------- BASIC COUNTS --------
    total_doctors = User.objects.filter(role="DOCTOR").count()
    total_pharmacists = User.objects.filter(role="PHARMACIST").count()

    total_patients = Patient.objects.count()
    total_medicines = Medicine.objects.count()
    total_suppliers = Supplier.objects.count()

    total_revenue = Invoice.objects.aggregate(
        total=Sum("total_amount")
    )["total"] or 0


    # -------- EXPIRY DATA --------
    near_expiry = Batch.objects.filter(
        expiry_date__lte=today + timezone.timedelta(days=30),
        expiry_date__gte=today
    ).count()

    expired = Batch.objects.filter(
        expiry_date__lt=today
    ).count()


    # -------- ANALYTICS --------
    labels, revenue_values, profit_values = ReportService.monthly_profit_trend(6)

    today_revenue = ReportService.today_revenue()
    today_sales = ReportService.today_sales_count()

    analytics = ReportService.dashboard_analytics()

    recent_invoices = Invoice.objects.order_by("-created_at")[:5]

 

    recent_activity = ActivityLog.objects.select_related("user").order_by("-created_at")[:10]

    # -------- ALERT COUNTS --------

    pending_doctors = User.objects.filter(role="DOCTOR", is_approved=False).count()

    pending_pharmacists = User.objects.filter(role="PHARMACIST", is_approved=False).count()

    low_stock_count = Batch.objects.filter(quantity__lt=10).count()

    near_expiry_count = Batch.objects.filter(
        expiry_date__lte=today + timezone.timedelta(days=30),
        expiry_date__gte=today
    ).count()

    expired_count = Batch.objects.filter(
        expiry_date__lt=today
    ).count()

    low_stock_medicines = get_low_stock_medicines()
    near_expiry_batches = get_near_expiry_batches()
    expired_batches = get_expired_batches()

    dead_stock = ReportService.dead_stock()
    fast_moving = ReportService.fast_moving_medicines()

    context = {
        "total_doctors": total_doctors,
        "total_pharmacists": total_pharmacists,
        "total_patients": total_patients,
        "total_medicines": total_medicines,
        "total_suppliers": total_suppliers,
        "total_revenue": total_revenue,

        "near_expiry": near_expiry,
        "expired": expired,

        "today_revenue": today_revenue,
        "today_sales": today_sales,

        "stock_value": analytics["stock_value"],
        "most_profitable": analytics["most_profitable"],
        "monthly_growth": analytics["monthly_growth"],

        "profit_labels_json": json.dumps(labels),
        "revenue_values_json": json.dumps(revenue_values),
        "profit_values_json": json.dumps(profit_values),

        "recent_invoices": recent_invoices,
        "recent_activity": recent_activity,

        "pending_doctors": pending_doctors,
        "pending_pharmacists": pending_pharmacists,
        "low_stock_count": low_stock_count,
        "near_expiry_count": near_expiry_count,
        "expired_count": expired_count,
        "low_stock_count": low_stock_medicines.count(),
        "near_expiry_count": near_expiry_batches.count(),
        "expired_count": expired_batches.count(),

        "dead_stock": dead_stock,
        "fast_moving": fast_moving,
    }

    return render(request, "accounts/admin_dashboard.html", context)


@login_required
def approve_doctors(request):

    if request.user.role != "ADMIN":
        raise PermissionDenied()

    doctors = User.objects.filter(role="DOCTOR", is_approved=False)

    return render(request, "accounts/approve_doctors.html", {
        "doctors": doctors
    })


@login_required
def approve_pharmacists(request):

    if request.user.role != "ADMIN":
        raise PermissionDenied()

    pharmacists = User.objects.filter(role="PHARMACIST", is_approved=False)

    return render(request, "accounts/approve_pharmacists.html", {
        "pharmacists": pharmacists
    })


@login_required
def approve_user(request, user_id):

    if request.user.role != "ADMIN":
        raise PermissionDenied("Only admin can approve users.")

    if request.method != "POST":
        raise PermissionDenied("Invalid request method.")

    user = get_object_or_404(User, id=user_id)

    if user.role == "ADMIN":
        return HttpResponse("Cannot approve admin accounts.")

    if user.is_approved:
        return HttpResponse("User already approved.")

    if not user.license_number:
        return HttpResponse("License number required.")

    if not user.certificate:
        return HttpResponse("Certificate document required.")

    user.is_approved = True
    user.approved_by = request.user
    user.approved_at = timezone.now()
    user.save()
    from core.models import Notification

    Notification.objects.create(
        title="User Approved",
        message=f"{user.full_name} approved by admin",
        notification_type="INFO"
    )

    log_activity(
        request.user,
        "USER_APPROVED",
        f"{user.full_name} ({user.role}) was approved by {request.user.full_name}"
    )

    return redirect(request.META.get("HTTP_REFERER"))

@login_required
def reject_user(request, user_id):

    if request.user.role != "ADMIN":
        raise PermissionDenied()

    if request.method != "POST":
        raise PermissionDenied()

    user = get_object_or_404(User, id=user_id)

    log_activity(
        request.user,
        "USER_REJECTED",
        f"{user.full_name} ({user.role}) was rejected by {request.user.full_name}"
    )

    user.delete()

    return redirect(request.META.get("HTTP_REFERER"))

