from django.test import TestCase
from django.contrib.auth import get_user_model
from patients.models import Patient
from consultations.models import Consultation, Prescription, PrescriptionItem
from pharmacy.models import MedicineCategory, Medicine, Supplier, Batch
from billing.models import Invoice, InvoiceItem, Payment

User = get_user_model()


class FullWorkflowTest(TestCase):

    def setUp(self):

        # Users
        self.doctor = User.objects.create_user(
            email="doctor@test.com",
            password="test",
            role="DOCTOR",
            full_name="Doctor",
            phone="111",
            is_approved=True
        )

        self.pharmacist = User.objects.create_user(
            email="pharm@test.com",
            password="test",
            role="PHARMACIST",
            full_name="Pharmacist",
            phone="222",
            is_approved=True
        )

        # Patient
        self.patient = Patient.objects.create(
            full_name="Test Patient",
            age=30,
            gender="MALE",
            phone="999",
            created_by=self.doctor
        )

        # Medicine
        category = MedicineCategory.objects.create(name="General")

        self.medicine = Medicine.objects.create(
            name="Test Medicine",
            category=category,
            default_selling_price=10,
            gst_percentage=5
        )

        supplier = Supplier.objects.create(
            name="Test Supplier",
            phone="111"
        )

        self.batch = Batch.objects.create(
            medicine=self.medicine,
            supplier=supplier,
            batch_number="B1",
            purchase_price=5,
            selling_price=10,
            quantity=100,
            expiry_date="2030-01-01"
        )

    def test_full_pharmacy_workflow(self):

        # Consultation
        consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.doctor
        )

        # Prescription
        prescription = Prescription.objects.create(
            consultation=consultation
        )

        # Prescription Item
        p_item = PrescriptionItem.objects.create(
            prescription=prescription,
            medicine=self.medicine,
            dosage="500mg",
            frequency="3x",
            duration_days=5,
            quantity_prescribed=10
        )

        # Invoice
        invoice = Invoice.objects.create(
            prescription=prescription
        )

        item = InvoiceItem.objects.create(
            invoice=invoice,
            prescription_item=p_item,
            quantity=10,
            price_at_sale=10
        )

        invoice.calculate_total()

        # Payment
        Payment.objects.create(
            invoice=invoice,
            amount=invoice.total_amount,
            method="CASH",
            received_by=self.pharmacist
        )

        # Refresh objects
        self.batch.refresh_from_db()
        prescription.refresh_from_db()
        consultation.refresh_from_db()
        invoice.refresh_from_db()

        # Assertions
        self.assertEqual(invoice.status, "PAID")
        self.assertEqual(self.batch.quantity, 90)
        self.assertEqual(prescription.status, "BILLED")
        self.assertEqual(consultation.status, "CLOSED")