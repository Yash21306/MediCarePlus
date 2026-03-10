from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random

from patients.models import Patient
from consultations.models import Consultation, Prescription, PrescriptionItem
from pharmacy.models import Medicine, Batch, MedicineCategory, Supplier
from billing.models import Invoice, InvoiceItem, Payment

User = get_user_model()


class Command(BaseCommand):
    help = "Seed realistic demo data for MediCarePlus"

    def handle(self, *args, **kwargs):

        self.stdout.write("Creating demo users...")

        admin, created = User.objects.get_or_create(
            email="admin@medicare.com",
            defaults={
                "full_name": "System Admin",
                "phone": "9000000000",
                "role": "ADMIN",
                "is_staff": True,
                "is_superuser": True,
                "is_approved": True,
            }
        )
        if created:
            admin.set_password("admin123")
            admin.save()

        doctors = []
        for i in range(2):
            doctor, created = User.objects.get_or_create(
                email=f"doctor{i}@medicare.com",
                defaults={
                    "full_name": f"Doctor {i}",
                    "phone": f"910000000{i}",
                    "role": "DOCTOR",
                    "is_approved": True,
                },
            )
            if created:
                doctor.set_password("doctor123")
                doctor.save()

            doctors.append(doctor)

        pharmacists = []
        for i in range(2):
            pharmacist, created = User.objects.get_or_create(
                email=f"pharmacist{i}@medicare.com",
                defaults={
                    "full_name": f"Pharmacist {i}",
                    "phone": f"920000000{i}",
                    "role": "PHARMACIST",
                    "is_approved": True,
                },
            )
            if created:
                pharmacist.set_password("pharma123")
                pharmacist.save()

            pharmacists.append(pharmacist)

        self.stdout.write("Creating patients...")

        patients = []

        for i in range(10):
            patient = Patient.objects.create(
                full_name=f"Patient {i}",
                age=random.randint(18, 70),
                gender=random.choice(["MALE", "FEMALE"]),
                phone=f"999000{i}",
                address="Ahmedabad",
                medical_history="None",
                created_by=doctors[0],
            )

            patients.append(patient)

        self.stdout.write("Creating medicine category...")

        category, _ = MedicineCategory.objects.get_or_create(
            name="General Medicines",
            defaults={"description": "Default category"},
        )

        self.stdout.write("Creating supplier...")

        supplier, _ = Supplier.objects.get_or_create(
            name="Demo Supplier",
            defaults={
                "contact_person": "Supplier Manager",
                "phone": "9888888888",
                "email": "supplier@demo.com",
                "address": "Ahmedabad",
            },
        )

        self.stdout.write("Creating medicines...")

        medicine_names = [
            "Paracetamol",
            "Amoxicillin",
            "Azithromycin",
            "Ibuprofen",
            "Dolo 650",
            "Crocin",
            "Vitamin C",
            "Cetirizine",
            "Pantoprazole",
            "Metformin",
        ]

        medicines = []

        for name in medicine_names:
            medicine, _ = Medicine.objects.get_or_create(
                name=name,
                defaults={
                    "manufacturer": "Demo Pharma",
                    "default_selling_price": Decimal(random.randint(10, 50)),
                    "gst_percentage": Decimal("5.00"),
                    "category": category,
                    "stock_quantity": 0,
                },
            )

            medicines.append(medicine)

        self.stdout.write("Creating batches...")

        for med in medicines:
            for b in range(2):
                Batch.objects.create(
                    medicine=med,
                    supplier=supplier,
                    batch_number=f"B{random.randint(1000,9999)}",
                    expiry_date=timezone.now().date().replace(year=2027 + b),
                    purchase_price=Decimal("5.00"),
                    selling_price=med.default_selling_price,
                    quantity=random.randint(50, 150),
                )

        self.stdout.write("Creating consultations...")

        prescriptions = []

        for i in range(8):

            consultation = Consultation.objects.create(
                patient=random.choice(patients),
                doctor=random.choice(doctors),
                symptoms="Fever and headache",
                notes="General viral infection",
            )

            prescription = Prescription.objects.create(
                consultation=consultation,
                status="PENDING",
            )

            for med in random.sample(medicines, 2):
                PrescriptionItem.objects.create(
                    prescription=prescription,
                    medicine=med,
                    dosage="500 mg",
                    frequency="3 times daily",
                    duration_days=5,
                    quantity_prescribed=random.randint(5, 10),
                )

            prescriptions.append(prescription)

        self.stdout.write("Creating invoices...")

        invoices = []

        for prescription in prescriptions[:5]:

            invoice = Invoice.objects.create(
                prescription=prescription
            )

            for item in prescription.items.all():
                InvoiceItem.objects.create(
                    invoice=invoice,
                    prescription_item=item,
                    quantity=item.quantity_prescribed,
                    price_at_sale=item.medicine.default_selling_price,
                )

            invoice.calculate_total()

            invoices.append(invoice)

        self.stdout.write("Creating payments...")

        for invoice in invoices[:3]:

            Payment.objects.create(
                invoice=invoice,
                amount=invoice.total_amount,
                method="CASH",
                received_by=random.choice(pharmacists),
            )

        self.stdout.write(
            self.style.SUCCESS("Realistic demo data created successfully!")
        )