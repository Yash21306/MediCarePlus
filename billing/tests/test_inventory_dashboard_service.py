from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from accounts.models import CustomUser, City
from pharmacy.models import Medicine, Batch
from billing.services.inventory_dashboard_service import InventoryDashboardService


class InventoryDashboardServiceTest(TestCase):

    def setUp(self):
        self.city = City.objects.create(
            name="Mumbai",
            state="Maharashtra",
            country="India"
        )

        self.user = CustomUser.objects.create_user(
            email="admin@test.com",
            password="pass123",
            role="ADMIN",
            full_name="Admin",
            phone="8888888888",
            city=self.city,
            is_approved=True
        )

        self.medicine1 = Medicine.objects.create(
            name="MedA",
            price=Decimal("10.00"),
            gst_percentage=Decimal("5.00")
        )

        self.medicine2 = Medicine.objects.create(
            name="MedB",
            price=Decimal("20.00"),
            gst_percentage=Decimal("5.00")
        )

        today = timezone.now().date()

        # Near expiry
        Batch.objects.create(
            medicine=self.medicine1,
            batch_number="A1",
            expiry_date=today + timedelta(days=5),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            quantity=5
        )

        # Expired (force via update)
        expired_batch = Batch.objects.create(
            medicine=self.medicine2,
            batch_number="B1",
            expiry_date=today + timedelta(days=5),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("20.00"),
            quantity=8
        )

        Batch.objects.filter(pk=expired_batch.pk).update(
            expiry_date=today - timedelta(days=5)
        )

    def test_dashboard_summary_structure(self):
        result = InventoryDashboardService.get_summary()

        self.assertIn("near_expiry_count", result)
        self.assertIn("expired_count", result)
        self.assertIn("dead_stock_count", result)
        self.assertIn("low_stock_count", result)

    def test_dashboard_counts_are_correct(self):
        result = InventoryDashboardService.get_summary(
            days_near_expiry=30,
            dead_stock_days=60,
            low_stock_threshold=10
        )

        self.assertEqual(result["near_expiry_count"], 1)
        self.assertEqual(result["expired_count"], 1)
        self.assertEqual(result["dead_stock_count"], 2)
        self.assertEqual(result["low_stock_count"], 2)