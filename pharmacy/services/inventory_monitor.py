from django.db import models
from core.models import Notification
from pharmacy.models import Medicine, Batch
from django.utils import timezone


def check_inventory_alerts():

    # LOW STOCK
    low_stock_medicines = Medicine.objects.filter(
        stock_quantity__lte=models.F("low_stock_threshold")
    )

    for med in low_stock_medicines:

        Notification.objects.get_or_create(
            title="Low Stock Alert",
            message=f"{med.name} stock is low ({med.stock_quantity} left)",
            notification_type="WARNING"
        )

    # NEAR EXPIRY
    today = timezone.now().date()
    near_expiry = Batch.objects.filter(
        expiry_date__lte=today + timezone.timedelta(days=30),
        expiry_date__gte=today
    )

    for batch in near_expiry:

        Notification.objects.get_or_create(
            title="Medicine Near Expiry",
            message=f"{batch.medicine.name} batch {batch.batch_number} expiring soon",
            notification_type="WARNING"
        )

    # EXPIRED
    expired_batches = Batch.objects.filter(
        expiry_date__lt=today
    )

    for batch in expired_batches:

        Notification.objects.get_or_create(
            title="Expired Medicine",
            message=f"{batch.medicine.name} batch {batch.batch_number} expired",
            notification_type="CRITICAL"
        )