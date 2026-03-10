from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from billing.models import Invoice
from django.contrib.auth import get_user_model
from patients.models import Patient
from consultations.models import Consultation, Prescription

User = get_user_model()

class SalesReportViewTest(TestCase):

    def setUp(self):
        # Create doctor user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass",
            role="DOCTOR",
            full_name="Test Doctor",
            phone="9999999999"
        )

        # Create patient
        self.patient = Patient.objects.create(
            full_name="Test Patient",
            age=30,
            gender="MALE",
            phone="8888888888",
            created_by=self.user
        )

        # Create consultation (IMPORTANT STEP YOU WERE MISSING)
        self.consultation = Consultation.objects.create(
            patient=self.patient,
            doctor=self.user
        )

        # Create prescription (linked to consultation)
        self.prescription = Prescription.objects.create(
            consultation=self.consultation
        )

        # Create invoices
        Invoice.objects.create(
            prescription=self.prescription,
            total_amount=Decimal("100.00"),
            status="PAID"
        )

        Invoice.objects.create(
            prescription=self.prescription,
            total_amount=Decimal("200.00"),
            status="PAID"
        )

    def test_sales_report_total(self):
        response = self.client.get("/billing/reports/sales/")
        self.assertEqual(response.status_code, 200)

        # Total should be 300 (only PAID)
        self.assertContains(response, "300")

    def test_date_filter(self):
        today = timezone.now().date()

        response = self.client.get(
            "/billing/reports/sales/",
            {
                "start_date": today,
                "end_date": today,
            }
        )

        self.assertEqual(response.status_code, 200)