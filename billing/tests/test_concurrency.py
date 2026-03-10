from django.test import TransactionTestCase
from django.utils import timezone
from decimal import Decimal
from threading import Thread

from accounts.models import CustomUser, City
from patients.models import Patient
from consultations.models import Consultation, Prescription, PrescriptionItem
from pharmacy.models import Medicine, Batch
from billing.models import Invoice, InvoiceItem, Payment
from billing.services.invoice_service import InvoiceService


class ConcurrencyTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.city = City.objects.create(
            name="Surat",
            state="Gujarat",
            country="India"
        )

        self.pharmacist = CustomUser.objects.create_user(
            email="pharma@test.com",
            password="pass123",
            role="PHARMACIST",
            full_name="Pharma",
            phone="9999999999",
            city=self.city,
            is_approved=True
        )

        self.patient = Patient.objects.create(
            full_name="Test Patient",
            age=30,
            gender="MALE",
            phone="7777777777",
            city=self.city,
            created_by=self.pharmacist
        )

        self.consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.pharmacist
        )

        self.prescription = Prescription.objects.create(
            consultation=self.consultation
        )

        self.medicine = Medicine.objects.create(
            name="Paracetamol",
            price=Decimal("10.00")
        )

        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B1",
            expiry_date=timezone.now().date() + timezone.timedelta(days=30),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            quantity=10
        )

        self.prescription_item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine=self.medicine,
            dosage="500mg",
            frequency="2 times daily",
            duration_days=5,
            quantity_prescribed=10
        )

        self.invoice1 = Invoice.objects.create(prescription=self.prescription)
        InvoiceItem.objects.create(
            invoice=self.invoice1,
            prescription_item=self.prescription_item,
            quantity=10,
            price_at_sale=Decimal("10.00")
        )
        self.invoice1.calculate_total()

        Payment.objects.create(
            invoice=self.invoice1,
            amount=self.invoice1.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

    def _process_payment(self):
        try:
            InvoiceService.process_payment(self.invoice1, self.pharmacist)
        except Exception:
            pass

    def test_double_processing_concurrently(self):
        t1 = Thread(target=self._process_payment)
        t2 = Thread(target=self._process_payment)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        self.batch.refresh_from_db()

        # Stock should be deducted only once
        self.assertEqual(self.batch.quantity, 0)