from django.utils import timezone
from datetime import timedelta
from pharmacy.models import Batch


class InventoryService:

    @staticmethod
    def near_expiry_batches(days=30):
        """
        Return batches expiring within given days
        """
        today = timezone.now().date()
        threshold = today + timedelta(days=days)

        return Batch.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=threshold,
            quantity__gt=0
        ).order_by("expiry_date")

    @staticmethod
    def expired_batches():
        """
        Return expired batches still having stock
        """
        today = timezone.now().date()

        return Batch.objects.filter(
            expiry_date__lt=today,
            quantity__gt=0
        )

    @staticmethod
    def dead_stock(days_without_sale=60):
        """
        Medicines not sold in last X days
        """
        from pharmacy.models import StockMovement

        threshold = timezone.now() - timedelta(days=days_without_sale)

        sold_recently = StockMovement.objects.filter(
            movement_type="SALE",
            created_at__gte=threshold
        ).values_list("batch__medicine_id", flat=True)

        from pharmacy.models import Medicine

        return Medicine.objects.exclude(id__in=sold_recently)