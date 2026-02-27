from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import timedelta

from accounts.models import CustomUser, City
from patients.models import Patient
from consultations.models import Consultation, Prescription, PrescriptionItem
from pharmacy.models import Medicine, Batch
from billing.models import Invoice, InvoiceItem, Payment
from billing.services.invoice_service import InvoiceService


class InvoiceFlowTest(TestCase):

    def setUp(self):
        # --- City ---
        self.city = City.objects.create(
            name="Surat",
            state="Gujarat",
            country="India"
        )

        # --- Doctor ---
        self.doctor = CustomUser.objects.create_user(
            email="doc@test.com",
            password="pass123",
            role="DOCTOR",
            full_name="Doc",
            phone="9999999999",
            city=self.city,
            is_approved=True
        )

        # --- Pharmacist ---
        self.pharmacist = CustomUser.objects.create_user(
            email="pharma@test.com",
            password="pass123",
            role="PHARMACIST",
            full_name="Pharma",
            phone="8888888888",
            city=self.city,
            is_approved=True
        )

        # --- Patient ---
        self.patient = Patient.objects.create(
            full_name="Test Patient",
            age=30,
            gender="MALE",
            phone="7777777777",
            city=self.city,
            created_by=self.doctor
        )

        # --- Consultation ---
        self.consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.doctor
        )

        # --- Medicine ---
        self.medicine = Medicine.objects.create(
            name="Paracetamol",
            price=Decimal("10.00")
        )

        # --- Batches (FIFO: older expiry first) ---
        self.batch1 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B1",
            expiry_date=timezone.now().date() + timedelta(days=30),
            purchase_price=Decimal("5"),
            selling_price=Decimal("10"),
            quantity=5
        )

        self.batch2 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B2",
            expiry_date=timezone.now().date() + timedelta(days=60),
            purchase_price=Decimal("5"),
            selling_price=Decimal("10"),
            quantity=10
        )

        # --- Prescription ---
        self.prescription = Prescription.objects.create(
            consultation=self.consultation
        )

        self.prescription_item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine=self.medicine,
            dosage="500mg",
            frequency="2 times daily",
            duration_days=5,
            quantity_prescribed=8
        )

        # --- Invoice ---
        self.invoice = Invoice.objects.create(
            prescription=self.prescription
        )

        self.invoice_item = InvoiceItem.objects.create(
            invoice=self.invoice,
            prescription_item=self.prescription_item,
            quantity=8,
            price_at_sale=Decimal("10.00")
        )


    def test_full_payment_triggers_fifo_stock_deduction(self):
        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        InvoiceService.process_payment(self.invoice, self.pharmacist)

        self.invoice.refresh_from_db()
        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()

        self.assertEqual(self.invoice.status, "PAID")
        self.assertEqual(self.batch1.quantity, 0)  # 5 used
        self.assertEqual(self.batch2.quantity, 7)  # 3 used


    def test_overpayment_should_fail(self):
        self.invoice.calculate_total()

        with self.assertRaises(ValidationError):
            Payment.objects.create(
                invoice=self.invoice,
                amount=self.invoice.total_amount + Decimal("1"),
                method="CASH",
                received_by=self.pharmacist
            )


    def test_cannot_dispense_more_than_prescribed(self):
        with self.assertRaises(ValidationError):
            InvoiceItem.objects.create(
                invoice=self.invoice,
                prescription_item=self.prescription_item,
                quantity=20,
                price_at_sale=Decimal("10")
            )


    def test_cancel_invoice_restores_stock(self):
        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        InvoiceService.process_payment(self.invoice, self.pharmacist)

        InvoiceService.cancel_invoice(self.invoice, self.pharmacist)

        self.invoice.refresh_from_db()
        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()

        self.assertEqual(self.invoice.status, "CANCELLED")
        self.assertEqual(self.batch1.quantity, 5)
        self.assertEqual(self.batch2.quantity, 10)


    def test_prescription_status_updates(self):
        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        InvoiceService.process_payment(self.invoice, self.pharmacist)

        self.prescription.refresh_from_db()
        self.consultation.refresh_from_db()

        self.assertEqual(self.prescription.status, "BILLED")
        self.assertEqual(self.consultation.status, "CLOSED")

    def test_partial_payment_keeps_invoice_draft(self):
        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("20.00"),  # partial
            method="CASH",
            received_by=self.pharmacist
        )

        self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.status, "DRAFT")

    def test_expired_batch_not_used(self):
        # make batch1 expired
        self.batch1.expiry_date = timezone.now().date() - timedelta(days=1)
        self.batch1.save()

        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        InvoiceService.process_payment(self.invoice, self.pharmacist)

        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()

        # expired batch untouched
        self.assertEqual(self.batch1.quantity, 5)

        # all 8 taken from batch2
        self.assertEqual(self.batch2.quantity, 2)

    def test_cannot_modify_paid_invoice(self):
        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        InvoiceService.process_payment(self.invoice, self.pharmacist)

        with self.assertRaises(ValidationError):
            self.invoice_item.quantity = 2
            self.invoice_item.full_clean()        