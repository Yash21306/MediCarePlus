from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from pharmacy.models import Medicine, Batch, StockMovement
from consultations.models import Prescription, Consultation, PrescriptionItem
from patients.models import Patient
from billing.models import Invoice, InvoiceItem, Payment
from billing.services.invoice_service import InvoiceService


User = get_user_model()


class StockLedgerTestCase(TestCase):

    def setUp(self):
        from accounts.models import City

        # Create City (required by your CustomUser)
        self.city = City.objects.create(
            name="Surat",
            state="Gujarat",
            country="India"
        )

        # Create Pharmacist (email-based user model)
        self.pharmacist = User.objects.create_user(
            email="pharma1@test.com",
            password="test123",
            role="PHARMACIST",
            full_name="Pharma One",
            phone="9999999999",
            city=self.city,
            is_approved=True
        )

        # Create Patient
        self.patient = Patient.objects.create(
            full_name="John Doe",
            age=30,
            gender="MALE",
            phone="9999999999",
            city=self.city,
            created_by=self.pharmacist
        )

        # Create Medicine
        self.medicine = Medicine.objects.create(
            name="Paracetamol",
            price=Decimal("10.00"),
            gst_percentage=Decimal("5.00")
        )

        # Create Batches (FIFO scenario)
        self.batch1 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B001",
            expiry_date=timezone.now().date() + timezone.timedelta(days=60),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            quantity=10
        )

        self.batch2 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B002",
            expiry_date=timezone.now().date() + timezone.timedelta(days=120),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            quantity=10
        )

        # Create Consultation
        self.consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.pharmacist
        )

        # Create Prescription
        self.prescription = Prescription.objects.create(
            consultation=self.consultation
        )

        # Create Prescription Item (require 12 units)
        self.prescription_item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine=self.medicine,
            dosage="1 tab",
            frequency="Twice daily",
            duration_days=6,
            quantity_prescribed=12
        )

        # Create Invoice
        self.invoice = Invoice.objects.create(
            prescription=self.prescription
        )

        # Create InvoiceItem
        self.invoice_item = InvoiceItem.objects.create(
            invoice=self.invoice,
            prescription_item=self.prescription_item,
            quantity=12,
            price_at_sale=Decimal("10.00")
        )

        self.invoice.calculate_total()

        # Create full Payment
        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

    def test_fifo_deduction_and_ledger(self):

        # Process payment
        InvoiceService.process_payment(
            self.invoice,
            performed_by=self.pharmacist
        )

        self.invoice.refresh_from_db()

        # 1️⃣ Invoice should be PAID
        self.assertEqual(self.invoice.status, "PAID")

        # 2️⃣ Batch quantities should follow FIFO
        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()

        # Batch1 had 10 → fully used
        self.assertEqual(self.batch1.quantity, 0)

        # Batch2 had 10 → 2 used
        self.assertEqual(self.batch2.quantity, 8)

        # 3️⃣ StockMovement SALE entries
        sales = StockMovement.objects.filter(
            movement_type="SALE"
        )

        self.assertEqual(sales.count(), 2)

        total_sold = sum(abs(s.quantity) for s in sales)
        self.assertEqual(total_sold, 12)

        # Ensure negative quantities
        for s in sales:
            self.assertTrue(s.quantity < 0)