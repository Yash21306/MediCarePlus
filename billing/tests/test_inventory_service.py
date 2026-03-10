from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from accounts.models import CustomUser, City
from pharmacy.models import Medicine, Batch, StockMovement
from billing.services.inventory_service import InventoryService


class InventoryServiceTest(TestCase):

    def setUp(self):
        self.city = City.objects.create(
            name="Surat",
            state="Gujarat",
            country="India"
        )

        self.user = CustomUser.objects.create_user(
            email="pharma@test.com",
            password="pass123",
            role="PHARMACIST",
            full_name="Pharma",
            phone="9999999999",
            city=self.city,
            is_approved=True
        )

        self.medicine1 = Medicine.objects.create(
            name="Paracetamol",
            price=Decimal("10.00"),
            gst_percentage=Decimal("5.00")
        )

        self.medicine2 = Medicine.objects.create(
            name="Ibuprofen",
            price=Decimal("20.00"),
            gst_percentage=Decimal("5.00")
        )

        today = timezone.now().date()

        # Near expiry (valid)
        self.near_batch = Batch.objects.create(
            medicine=self.medicine1,
            batch_number="N1",
            expiry_date=today + timedelta(days=10),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            quantity=10
        )

        # Far expiry
        self.far_batch = Batch.objects.create(
            medicine=self.medicine1,
            batch_number="F1",
            expiry_date=today + timedelta(days=120),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            quantity=10
        )

        # Create valid first
        self.expired_batch = Batch.objects.create(
            medicine=self.medicine2,
            batch_number="E1",
            expiry_date=today + timedelta(days=5),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("20.00"),
            quantity=15
        )

        # Force expiry via DB update (bypass model validation)
        Batch.objects.filter(pk=self.expired_batch.pk).update(
            expiry_date=today - timedelta(days=5)
        )

        self.expired_batch.refresh_from_db()

    # --------------------------------------------------
    # Near Expiry Tests
    # --------------------------------------------------

    def test_near_expiry_batches(self):
        result = InventoryService.near_expiry_batches(days=30)

        self.assertIn(self.near_batch, result)
        self.assertNotIn(self.far_batch, result)
        self.assertNotIn(self.expired_batch, result)

    def test_near_expiry_respects_quantity(self):
        self.near_batch.quantity = 0
        self.near_batch.save(update_fields=["quantity"])

        result = InventoryService.near_expiry_batches(days=30)

        self.assertNotIn(self.near_batch, result)

    # --------------------------------------------------
    # Expired Tests
    # --------------------------------------------------

    def test_expired_batches(self):
        result = InventoryService.expired_batches()

        self.assertIn(self.expired_batch, result)
        self.assertNotIn(self.near_batch, result)
        self.assertNotIn(self.far_batch, result)

    def test_expired_batches_respects_quantity(self):
        # Bypass validation again using update()
        Batch.objects.filter(pk=self.expired_batch.pk).update(quantity=0)
        self.expired_batch.refresh_from_db()

        result = InventoryService.expired_batches()

        self.assertNotIn(self.expired_batch, result)

    # --------------------------------------------------
    # Dead Stock Tests
    # --------------------------------------------------

    def test_dead_stock_detects_unsold_medicines(self):
        StockMovement.objects.create(
            medicine=self.medicine1,
            batch=self.near_batch,
            movement_type="SALE",
            quantity=-2
        )

        result = InventoryService.dead_stock(days_without_sale=60)

        self.assertNotIn(self.medicine1, result)
        self.assertIn(self.medicine2, result)

    def test_dead_stock_all_if_no_sales(self):
        result = InventoryService.dead_stock(days_without_sale=60)

        self.assertIn(self.medicine1, result)
        self.assertIn(self.medicine2, result)