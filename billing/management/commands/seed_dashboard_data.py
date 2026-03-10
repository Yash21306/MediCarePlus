from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import random

from accounts.models import CustomUser, City
from patients.models import Patient
from consultations.models import Consultation, Prescription, PrescriptionItem
from pharmacy.models import Medicine, Batch, MedicineCategory, Supplier
from billing.models import Invoice, InvoiceItem, Payment
from billing.services.invoice_service import InvoiceService


class Command(BaseCommand):
    help = "Seed dashboard data for development"

    def handle(self, *args, **kwargs):

        self.stdout.write(self.style.WARNING("Seeding dashboard data..."))

        # City
        city, _ = City.objects.get_or_create(
            name="Ahmedabad",
            state="Gujarat",
            country="India"
        )

        # Doctor
        doctor, created = CustomUser.objects.get_or_create(
            email="doctor@dev.com",
            defaults={
                "role": "DOCTOR",
                "full_name": "Dev Doctor",
                "phone": "9999999999",
                "city": city,
                "is_approved": True
            }
        )

        if created:
            doctor.set_password("pass123")
            doctor.save()

        # Pharmacist
        pharmacist, created = CustomUser.objects.get_or_create(
            email="pharma@dev.com",
            defaults={
                "role": "PHARMACIST",
                "full_name": "Dev Pharmacist",
                "phone": "8888888888",
                "city": city,
                "is_approved": True
            }
        )

        if created:
            pharmacist.set_password("pass123")
            pharmacist.save()

        # Medicine category
        category, _ = MedicineCategory.objects.get_or_create(
            name="General"
        )

        # Supplier
        supplier, _ = Supplier.objects.get_or_create(
            name="Dashboard Supplier",
            defaults={
                "phone": "7777777777"
            }
        )

        # Medicines
        medicines = []

        for i in range(5):

            price = Decimal(random.randint(10, 50))

            med, _ = Medicine.objects.get_or_create(
                name=f"Medicine-{i}",
                defaults={
                    "category": category,
                    "default_selling_price": price,
                    "gst_percentage": Decimal("5.00")
                }
            )

            medicines.append(med)

            Batch.objects.get_or_create(
                medicine=med,
                batch_number=f"B-{i}",
                defaults={
                    "supplier": supplier,
                    "expiry_date": timezone.now().date() + timedelta(days=90),
                    "purchase_price": price / 2,
                    "selling_price": price,
                    "quantity": 200
                }
            )

        # Create invoices over last 14 days
        for day in range(14):

            patient = Patient.objects.create(
                full_name=f"Patient-{day}",
                age=30,
                gender="MALE",
                phone=f"70000000{day}",
                city=city,
                created_by=doctor
            )

            consultation = Consultation.objects.create(
                patient=patient,
                doctor=doctor
            )

            prescription = Prescription.objects.create(
                consultation=consultation
            )

            medicine = random.choice(medicines)

            pres_item = PrescriptionItem.objects.create(
                prescription=prescription,
                medicine=medicine,
                dosage="500mg",
                frequency="2 times daily",
                duration_days=5,
                quantity_prescribed=20
            )

            invoice = Invoice.objects.create(
                prescription=prescription
            )

            InvoiceItem.objects.create(
                invoice=invoice,
                prescription_item=pres_item,
                quantity=random.randint(1, 5),
                price_at_sale=medicine.default_selling_price
            )

            invoice.calculate_total()

            Payment.objects.create(
                invoice=invoice,
                amount=invoice.total_amount,
                method="CASH",
                received_by=pharmacist
            )

            # simulate different days
            invoice.created_at = timezone.now() - timedelta(days=day)
            invoice.save(update_fields=["created_at"])

            InvoiceService.process_payment(invoice, pharmacist)

        self.stdout.write(self.style.SUCCESS("Dashboard data seeded successfully!"))