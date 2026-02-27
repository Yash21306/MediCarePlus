from django.utils import timezone
from datetime import date, timedelta
from django.db.models import F
from .models import Medicine, Batch


def get_low_stock_medicines():
    return Medicine.objects.filter(
        stock_quantity__lte=F('low_stock_threshold'),
        is_active=True
    )

def get_near_expiry_batches(days=30):
    today = timezone.now().date()
    future_date = today + timedelta(days=days)
    return Batch.objects.filter(
        expiry_date__range=(today, future_date),
        quantity__gt=0
    )

def get_expired_batches():
    today = timezone.now().date()
    return Batch.objects.filter(
        expiry_date__lt=today,
        quantity__gt=0
    )