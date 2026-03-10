from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta

from pharmacy.models import Batch, Medicine, StockMovement
from billing.services.inventory_service import InventoryService


class InventoryDashboardService:

    @staticmethod
    def get_summary(days_near_expiry=30, dead_stock_days=60, low_stock_threshold=10):
        """
        Returns inventory dashboard summary counts.
        """

        today = timezone.now().date()

        # -----------------------------------------
        # Near Expiry Count
        # -----------------------------------------
        near_expiry_count = InventoryService.near_expiry_batches(
            days=days_near_expiry
        ).count()

        # -----------------------------------------
        # Expired Count
        # -----------------------------------------
        expired_count = InventoryService.expired_batches().count()

        # -----------------------------------------
        # Dead Stock Count
        # -----------------------------------------
        dead_stock_count = InventoryService.dead_stock(
            days_without_sale=dead_stock_days
        ).count()

        # -----------------------------------------
        # Low Stock Count (total quantity across batches)
        # -----------------------------------------
        medicine_stock = (
            Batch.objects
            .values("medicine")
            .annotate(total_qty=Sum("quantity"))
        )

        low_stock_count = sum(
            1 for m in medicine_stock
            if (m["total_qty"] or 0) <= low_stock_threshold
        )

        return {
            "near_expiry_count": near_expiry_count,
            "expired_count": expired_count,
            "dead_stock_count": dead_stock_count,
            "low_stock_count": low_stock_count,
        }