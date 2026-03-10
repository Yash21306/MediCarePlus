from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from accounts.models import CustomUser, City
from patients.models import Patient
from consultations.models import Consultation, Prescription, PrescriptionItem
from pharmacy.models import Medicine, Batch
from billing.models import Invoice, InvoiceItem, Payment
from billing.services.invoice_service import InvoiceService
from billing.services.report_service import ReportService


class ReportingServiceTest(TestCase):

    def setUp(self):
        self.city = City.objects.create(
            name="Surat",
            state="Gujarat",
            country="India"
        )

        self.doctor = CustomUser.objects.create_user(
            email="doc@test.com",
            password="pass123",
            role="DOCTOR",
            full_name="Doc",
            phone="9999999999",
            city=self.city,
            is_approved=True
        )

        self.pharmacist = CustomUser.objects.create_user(
            email="pharma@test.com",
            password="pass123",
            role="PHARMACIST",
            full_name="Pharma",
            phone="8888888888",
            city=self.city,
            is_approved=True
        )

        self.patient = Patient.objects.create(
            full_name="Test Patient",
            age=30,
            gender="MALE",
            phone="7777777777",
            city=self.city,
            created_by=self.doctor
        )

        self.consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.doctor
        )

        self.prescription = Prescription.objects.create(
            consultation=self.consultation
        )

        self.medicine = Medicine.objects.create(
            name="Paracetamol",
            price=Decimal("10.00"),
            gst_percentage=Decimal("0.00")
        )

        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B1",
            expiry_date=timezone.now().date() + timedelta(days=30),
            purchase_price=Decimal("5.00"),
            selling_price=Decimal("10.00"),
            quantity=100
        )

        self.prescription_item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine=self.medicine,
            dosage="500mg",
            frequency="2 times daily",
            duration_days=5,
            quantity_prescribed=10
        )

    def _create_paid_invoice(self, quantity, days_offset=0):
        invoice = Invoice.objects.create(
            prescription=self.prescription
        )

        InvoiceItem.objects.create(
            invoice=invoice,
            prescription_item=self.prescription_item,
            quantity=quantity,
            price_at_sale=Decimal("10.00")
        )

        invoice.calculate_total()

        Payment.objects.create(
            invoice=invoice,
            amount=invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        # Adjust created_at if needed
        if days_offset != 0:
            invoice.created_at = timezone.now() - timedelta(days=days_offset)
            invoice.save(update_fields=["created_at"])

        InvoiceService.process_payment(invoice, self.pharmacist)

        return invoice

    def test_total_revenue(self):
        self._create_paid_invoice(2)
        self._create_paid_invoice(3)

        total = ReportService.total_revenue()
        self.assertEqual(total, Decimal("50.00"))

    def test_today_revenue(self):
        self._create_paid_invoice(4)

        revenue = ReportService.today_revenue()
        self.assertEqual(revenue, Decimal("40.00"))

    def test_monthly_revenue(self):
        self._create_paid_invoice(5)

        revenue = ReportService.monthly_revenue()
        self.assertEqual(revenue, Decimal("50.00"))

    def test_last_7_days_revenue(self):
        self._create_paid_invoice(1, days_offset=2)
        self._create_paid_invoice(2, days_offset=0)

        labels, values = ReportService.last_7_days_revenue()

        self.assertEqual(len(labels), 7)
        self.assertEqual(len(values), 7)
        self.assertTrue(any(v > 0 for v in values))

    def test_top_selling_medicines(self):
        self._create_paid_invoice(3)

        top = list(ReportService.top_selling_medicines())

        self.assertEqual(
            top[0]["prescription_item__medicine__name"],
            "Paracetamol"
        )
        self.assertEqual(top[0]["total_sold"], 3)