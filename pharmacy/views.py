from django.shortcuts import render
from .models import Medicine, Batch, StockMovement, Supplier, MedicineCategory
from .services import (
    get_low_stock_medicines,
    get_near_expiry_batches,
    get_expired_batches
)
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def pharmacist_dashboard(request):
    context = {
        "total_medicines": Medicine.objects.count(),
        "low_stock_count": get_low_stock_medicines().count(),
        "near_expiry_count": get_near_expiry_batches().count(),
        "expired_count": get_expired_batches().count(),
    }
    return render(request, "pharmacy/dashboard.html", context)

def low_stock_medicines(request):
    medicines = get_low_stock_medicines()
    return render(request, "pharmacy/low_stock.html", {
        "medicines": medicines
    })

def near_expiry_batches(request):
    batches = get_near_expiry_batches()
    return render(request, "pharmacy/near_expiry.html", {
        "batches": batches
    })

def expired_batches(request):
    batches = get_expired_batches()
    return render(request, "pharmacy/expired_batches.html", {
        "batches": batches
    })

def medicine_list(request):
    medicines = Medicine.objects.all()
    return render(request, "pharmacy/medicine_list.html", {
        "medicines": medicines
    })

def supplier_purchase_report(request):
    suppliers = Supplier.objects.all()

    report_data = []

    for supplier in suppliers:
        batches = Batch.objects.filter(supplier=supplier)

        total_quantity = batches.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        total_value = batches.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("purchase_price"),
                    output_field=DecimalField()
                )
            )
        )["total"] or 0

        report_data.append({
            "supplier": supplier,
            "total_batches": batches.count(),
            "total_quantity": total_quantity,
            "total_value": total_value,
        })

    return render(request, "pharmacy/supplier_report.html", {
        "report_data": report_data
    })  

def category_sales_report(request):

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    sales_filter = {'movement_type': 'SALE'}

    if start_date:
        sales_filter['created_at__date__gte'] = start_date
    if end_date:
        sales_filter['created_at__date__lte'] = end_date

    categories = MedicineCategory.objects.all()
    report_data = []

    for category in categories:
        sales = StockMovement.objects.filter(
            medicine__category=category,
            **sales_filter
        )

        total_quantity = sales.aggregate(
            total_qty=Sum('quantity')
        )['total_qty'] or 0

        total_value = sales.aggregate(
            total_val=Sum(
                ExpressionWrapper(
                    F('quantity') * F('medicine__default_selling_price'),
                    output_field=DecimalField()
                )
            )
        )['total_val'] or 0

        report_data.append({
            'category': category.name,
            'total_quantity': total_quantity,
            'total_sales_value': total_value,
        })

    return render(request, 'pharmacy/category_report.html', {
        'report_data': report_data,
        'start_date': start_date,
        'end_date': end_date,
    })

@login_required
def doctor_medicine_stock(request):

    if request.user.role != "DOCTOR":
        raise PermissionDenied("Doctors only.")

    medicines = Medicine.objects.all()

    today = timezone.now().date()

    stock_data = []

    for med in medicines:

        total_stock = med.batches.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        near_expiry = med.batches.filter(
            expiry_date__lte=today + timezone.timedelta(days=30),
            expiry_date__gte=today,
            quantity__gt=0
        ).exists()

        stock_data.append({
            "medicine": med,
            "stock": total_stock,
            "low_stock": med.is_low_stock(),
            "near_expiry": near_expiry
        })

    return render(
        request,
        "pharmacy/doctor_medicine_stock.html",
        {
            "stock_data": stock_data
        }
    )

@login_required
def expiry_report(request):

    if request.user.role not in ["ADMIN", "PHARMACIST"]:
        raise PermissionDenied("Access restricted.")

    today = timezone.now().date()
    limit = today + timezone.timedelta(days=30)

    batches = Batch.objects.filter(
        expiry_date__gte=today,
        expiry_date__lte=limit,
        quantity__gt=0
    ).select_related("medicine").order_by("expiry_date")

    return render(
        request,
        "pharmacy/expiry_report.html",
        {
            "batches": batches
        }
    )

@login_required
def stock_report(request):

    if request.user.role not in ["ADMIN", "PHARMACIST"]:
        raise PermissionDenied("Access restricted.")

    medicines = Medicine.objects.all()

    stock_data = []

    for med in medicines:

        batches = med.batches.all()

        total_stock = batches.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        batch_count = batches.count()

        stock_value = sum(
            batch.quantity * batch.purchase_price
            for batch in batches
        )

        stock_data.append({
            "medicine": med,
            "stock": total_stock,
            "batches": batch_count,
            "value": stock_value
        })

    return render(
        request,
        "pharmacy/stock_report.html",
        {
            "stock_data": stock_data
        }
    )