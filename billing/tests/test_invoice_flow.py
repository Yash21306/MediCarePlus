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

        # --- Valid Batches (FIFO: earlier expiry first) ---

        self.batch1 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B1",
            expiry_date=timezone.now().date() + timedelta(days=30),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            quantity=5
        )

        self.batch2 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B2",
            expiry_date=timezone.now().date() + timedelta(days=60),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
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
        Batch.objects.filter(pk=self.batch1.pk).update(
            expiry_date=timezone.now().date() - timedelta(days=1)
        )
        self.batch1.refresh_from_db()

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

    def test_partial_then_full_payment_processes_correctly(self):
        self.invoice.calculate_total()

        total_amount = self.invoice.total_amount

        # First partial payment
        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("20.00"),
            method="CASH",
            received_by=self.pharmacist
        )

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "DRAFT")

        # Stock should NOT change yet
        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()
        self.assertEqual(self.batch1.quantity, 5)
        self.assertEqual(self.batch2.quantity, 10)

        # Second payment to complete total
        remaining = total_amount - Decimal("20.00")

        Payment.objects.create(
            invoice=self.invoice,
            amount=remaining,
            method="CASH",
            received_by=self.pharmacist
        )

        InvoiceService.process_payment(self.invoice, self.pharmacist)

        self.invoice.refresh_from_db()
        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()

        # Now invoice should be paid
        self.assertEqual(self.invoice.status, "PAID")

        # FIFO deduction should happen ONCE
        self.assertEqual(self.batch1.quantity, 0)
        self.assertEqual(self.batch2.quantity, 7)

    def test_processing_payment_twice_does_not_double_deduct_stock(self):
        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        # First processing
        InvoiceService.process_payment(self.invoice, self.pharmacist)

        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()

        self.assertEqual(self.batch1.quantity, 0)
        self.assertEqual(self.batch2.quantity, 7)

        # Second processing attempt
        InvoiceService.process_payment(self.invoice, self.pharmacist)

        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()

        # Stock must remain unchanged
        self.assertEqual(self.batch1.quantity, 0)
        self.assertEqual(self.batch2.quantity, 7)

    def test_multiple_invoices_respect_prescription_limit(self):
        # Adjust prescription to 10
        self.prescription_item.quantity_prescribed = 10
        self.prescription_item.save()

        # First invoice – 4 tablets
        invoice1 = Invoice.objects.create(prescription=self.prescription)
        item1 = InvoiceItem.objects.create(
            invoice=invoice1,
            prescription_item=self.prescription_item,
            quantity=4,
            price_at_sale=Decimal("10.00")
        )
        invoice1.calculate_total()

        Payment.objects.create(
            invoice=invoice1,
            amount=invoice1.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )
        InvoiceService.process_payment(invoice1, self.pharmacist)

        # Second invoice – 3 tablets
        invoice2 = Invoice.objects.create(prescription=self.prescription)
        item2 = InvoiceItem.objects.create(
            invoice=invoice2,
            prescription_item=self.prescription_item,
            quantity=3,
            price_at_sale=Decimal("10.00")
        )
        invoice2.calculate_total()

        Payment.objects.create(
            invoice=invoice2,
            amount=invoice2.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )
        InvoiceService.process_payment(invoice2, self.pharmacist)

        # Third invoice – try exceeding limit
        invoice3 = Invoice.objects.create(prescription=self.prescription)

        with self.assertRaises(ValidationError):
            InvoiceItem.objects.create(
                invoice=invoice3,
                prescription_item=self.prescription_item,
                quantity=5,  # exceeds remaining (only 3 left)
                price_at_sale=Decimal("10.00")
            )

    def test_multi_invoice_stock_insufficient(self):
        # Set prescription to 10
        self.prescription_item.quantity_prescribed = 10
        self.prescription_item.save()

        # Adjust stock: only 8 available total
        self.batch1.quantity = 3
        self.batch1.save(update_fields=["quantity"])
        self.batch2.quantity = 5
        self.batch2.save(update_fields=["quantity"])

        # First invoice – 6
        invoice1 = Invoice.objects.create(prescription=self.prescription)
        InvoiceItem.objects.create(
            invoice=invoice1,
            prescription_item=self.prescription_item,
            quantity=6,
            price_at_sale=Decimal("10.00")
        )
        invoice1.calculate_total()

        Payment.objects.create(
            invoice=invoice1,
            amount=invoice1.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )
        InvoiceService.process_payment(invoice1, self.pharmacist)

        # Second invoice – attempt 4 (only 2 stock left)
        invoice2 = Invoice.objects.create(prescription=self.prescription)
        InvoiceItem.objects.create(
            invoice=invoice2,
            prescription_item=self.prescription_item,
            quantity=4,
            price_at_sale=Decimal("10.00")
        )
        invoice2.calculate_total()

        Payment.objects.create(
            invoice=invoice2,
            amount=invoice2.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        with self.assertRaises(ValidationError):
            InvoiceService.process_payment(invoice2, self.pharmacist)

    def test_cancel_one_of_multiple_invoices_updates_prescription_status(self):
        # Prescription = 10
        self.prescription_item.quantity_prescribed = 10
        self.prescription_item.save()

        # Invoice 1 – 6
        invoice1 = Invoice.objects.create(prescription=self.prescription)
        InvoiceItem.objects.create(
            invoice=invoice1,
            prescription_item=self.prescription_item,
            quantity=6,
            price_at_sale=Decimal("10.00")
        )
        invoice1.calculate_total()

        Payment.objects.create(
            invoice=invoice1,
            amount=invoice1.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )
        InvoiceService.process_payment(invoice1, self.pharmacist)

        # Invoice 2 – 4
        invoice2 = Invoice.objects.create(prescription=self.prescription)
        InvoiceItem.objects.create(
            invoice=invoice2,
            prescription_item=self.prescription_item,
            quantity=4,
            price_at_sale=Decimal("10.00")
        )
        invoice2.calculate_total()

        Payment.objects.create(
            invoice=invoice2,
            amount=invoice2.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )
        InvoiceService.process_payment(invoice2, self.pharmacist)

        # At this point → fully billed
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.status, "BILLED")

        # Cancel second invoice
        InvoiceService.cancel_invoice(invoice2, self.pharmacist)

        self.prescription.refresh_from_db()
        self.consultation.refresh_from_db()

        # Should revert to PARTIALLY_BILLED
        self.assertEqual(self.prescription.status, "PARTIALLY_BILLED")
        self.assertEqual(self.consultation.status, "OPEN")

    def test_doctor_cannot_process_payment(self):
        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        with self.assertRaises(ValidationError):
            InvoiceService.process_payment(self.invoice, self.doctor)

    def test_unapproved_pharmacist_cannot_process_payment(self):
        unapproved = CustomUser.objects.create_user(
            email="unapproved@test.com",
            password="pass123",
            role="PHARMACIST",
            full_name="Unapproved",
            phone="1234567890",
            city=self.city,
            is_approved=False
        )

        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        with self.assertRaises(ValidationError):
            InvoiceService.process_payment(self.invoice, unapproved)

    def test_doctor_cannot_cancel_invoice(self):
        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        InvoiceService.process_payment(self.invoice, self.pharmacist)

        with self.assertRaises(ValidationError):
            InvoiceService.cancel_invoice(self.invoice, self.doctor)

    def test_unapproved_pharmacist_cannot_cancel_invoice(self):
        unapproved = CustomUser.objects.create_user(
            email="unapproved2@test.com",
            password="pass123",
            role="PHARMACIST",
            full_name="Unapproved2",
            phone="1234567891",
            city=self.city,
            is_approved=False
        )

        self.invoice.calculate_total()

        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        InvoiceService.process_payment(self.invoice, self.pharmacist)

        with self.assertRaises(ValidationError):
            InvoiceService.cancel_invoice(self.invoice, unapproved)