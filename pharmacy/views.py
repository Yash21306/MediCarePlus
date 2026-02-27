from django.shortcuts import render
from .models import Medicine, Batch
from .services import (
    get_low_stock_medicines,
    get_near_expiry_batches,
    get_expired_batches
)

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