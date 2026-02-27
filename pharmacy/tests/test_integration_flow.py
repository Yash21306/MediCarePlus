# pharmacy/tests/test_integration_flow.py
from django.test import TestCase
from django.core.exceptions import ValidationError
from accounts.models import CustomUser, City
from patients.models import Patient
from consultations.models import Consultation, Prescription, PrescriptionItem
from pharmacy.models import Medicine, Batch
from billing.models import Invoice, InvoiceItem

class FullSystemIntegrationTest(TestCase):
    def setUp(self):
        # --- City ---
        self.city = City.objects.create(name="Surat", state="GJ", country="IN")

        # --- Users ---
        self.doctor = CustomUser.objects.create_user(
            email="doc@test.com",
            password="123456",
            full_name="Dr Test",
            phone="9999999999",
            role="DOCTOR",
            city=self.city,
            is_approved=True
        )

        self.pharmacist = CustomUser.objects.create_user(
            email="pharma@test.com",
            password="123456",
            full_name="Pharma Test",
            phone="8888888888",
            role="PHARMACIST",
            city=self.city,
            is_approved=True
        )

        # --- Patient ---
        self.patient = Patient.objects.create(
            full_name="John Doe",
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

        # --- Prescription ---
        self.prescription = Prescription.objects.create(
            consultation=self.consultation
        )

        # --- Medicine and Batch ---
        self.medicine = Medicine.objects.create(
            name="Paracetamol",
            price=10,
            stock_quantity=0,
            is_active=True
        )

        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number="B001",
            expiry_date="2030-12-31",
            purchase_price=5,
            selling_price=10,
            quantity=100
        )

        # --- Prescription Item ---
        self.prescription_item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine=self.medicine,
            dosage="500mg",
            frequency="2 times daily",
            duration_days=5,
            quantity_prescribed=10
        )

        # --- Invoice ---
        self.invoice = Invoice.objects.create(
            prescription=self.prescription
        )

        self.invoice_item = InvoiceItem.objects.create(
            invoice=self.invoice,
            prescription_item=self.prescription_item,
            quantity=5,
            price_at_sale=10
        )

    def test_invoice_total_calculation(self):
        self.assertEqual(self.invoice.total_amount, 50)

        # Add another invoice item
        InvoiceItem.objects.create(
            invoice=self.invoice,
            prescription_item=self.prescription_item,
            quantity=3,
            price_at_sale=10
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, 80)

    def test_batch_stock_update(self):
        # Medicine stock should match batch quantity
        self.assertEqual(self.medicine.stock_quantity, 100)

        # Reduce batch quantity
        self.batch.quantity = 60
        self.batch.save()
        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.stock_quantity, 60)

    def test_prescription_item_dispense_limit(self):
        # Trying to dispense more than prescribed
        with self.assertRaises(ValidationError):
            InvoiceItem.objects.create(
                invoice=self.invoice,
                prescription_item=self.prescription_item,
                quantity=20,
                price_at_sale=10
            )

    def test_invoice_item_modification_lock(self):
        # Mark invoice as PAID
        self.invoice.status = "PAID"
        self.invoice.save()

        # Trying to modify invoice item now should fail
        self.invoice_item.quantity = 2
        with self.assertRaises(ValidationError):
            self.invoice_item.save()

    def test_full_clinic_flow(self):
        # Integration sanity check
        self.assertEqual(self.invoice.items.count(), 1)
        self.assertEqual(self.invoice_item.medicine, self.medicine)
        self.assertEqual(self.medicine.stock_quantity, 100)