from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db.models import Sum

from pharmacy.models import Medicine, Batch


class BatchLogicTest(TestCase):

    def setUp(self):
        self.medicine = Medicine.objects.create(
            name="Amoxicillin",
            price=Decimal("25.00")
        )

        self.batch1 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="A1",
            expiry_date=timezone.now().date() + timedelta(days=30),
            purchase_price=Decimal("15"),
            selling_price=Decimal("25"),
            quantity=10
        )

        self.batch2 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="A2",
            expiry_date=timezone.now().date() + timedelta(days=60),
            purchase_price=Decimal("15"),
            selling_price=Decimal("25"),
            quantity=20
        )

    def test_cannot_create_expired_batch(self):
        with self.assertRaises(ValidationError):
            batch = Batch(
                medicine=self.medicine,
                batch_number="EX1",
                expiry_date=timezone.now().date() - timedelta(days=1),
                purchase_price=Decimal("10"),
                selling_price=Decimal("20"),
                quantity=5
            )
            batch.full_clean()

    def test_cannot_reduce_quantity_below_zero(self):
        self.batch1.quantity = -5
        with self.assertRaises(ValidationError):
            self.batch1.full_clean()

    def test_fifo_ordering(self):
        batches = Batch.objects.filter(
            medicine=self.medicine,
            expiry_date__gt=timezone.now().date(),
            quantity__gt=0
        ).order_by("expiry_date")

        self.assertEqual(batches.first().batch_number, "A1")

    def test_total_stock_calculation(self):
        total_stock = Batch.objects.filter(
            medicine=self.medicine
        ).aggregate(total=Sum("quantity"))["total"]

        self.assertEqual(total_stock, 30)