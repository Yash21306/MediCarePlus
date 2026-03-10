from django.test import TestCase
from decimal import Decimal
from django.contrib.auth import get_user_model

from patients.models import Patient
from consultations.models import Consultation, Prescription, PrescriptionItem
from pharmacy.models import Medicine
from billing.models import Invoice, InvoiceItem


User = get_user_model()


class GSTCalculationTest(TestCase):

    def setUp(self):

        # Create Doctor User
        self.doctor = User.objects.create_user(
            email="doctor1@test.com",
            password="testpass123",
            role="DOCTOR",
            full_name="Test Doctor",
            phone="9999999999",
            is_approved=True
        )
        # Create Patient
        self.patient = Patient.objects.create(
            full_name="Test Patient",
            age=30,
            gender="MALE",
            phone="9999999999",
            created_by=self.doctor
        )

        # Create Consultation
        self.consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.doctor
        )

        # Create Prescription
        self.prescription = Prescription.objects.create(
            consultation=self.consultation
        )

        # Create Medicine with 18% GST
        self.medicine = Medicine.objects.create(
            name="TestMed",
            price=Decimal("99.99"),
            gst_percentage=Decimal("18")
        )

        # Create Prescription Item
        self.prescription_item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine=self.medicine,
            dosage="1 tablet",
            frequency="Twice daily",
            duration_days=5,
            quantity_prescribed=5
        )

        # Create Invoice
        self.invoice = Invoice.objects.create(
            prescription=self.prescription
        )

    def test_gst_calculation(self):

        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            prescription_item=self.prescription_item,
            quantity=3,
            price_at_sale=Decimal("99.99")
        )

        # Expected values
        self.assertEqual(item.subtotal, Decimal("299.97"))
        self.assertEqual(item.cgst_amount, Decimal("27.00"))
        self.assertEqual(item.sgst_amount, Decimal("27.00"))
        self.assertEqual(item.total_with_tax, Decimal("353.96"))

        # Refresh invoice totals
        self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.total_amount, Decimal("353.96"))

