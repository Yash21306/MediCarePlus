from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from patients.models import Patient
from pharmacy.models import MedicineCategory, Medicine, Supplier, Batch

User = get_user_model()


class Command(BaseCommand):

    help = "Create minimal demo data for workflow testing"

    def handle(self, *args, **kwargs):

        self.stdout.write("Creating demo users...")

        doctor, created = User.objects.get_or_create(
            email="doctor@test.com",
            defaults={
                "role": "DOCTOR",
                "full_name": "Dr. John",
                "phone": "1111111111",
                "is_approved": True
            }
        )

        if created:
            doctor.set_password("test123")
            doctor.save()

        pharmacist, created = User.objects.get_or_create(
            email="pharmacist@test.com",
            defaults={
                "role": "PHARMACIST",
                "full_name": "Pharmacist Mike",
                "phone": "2222222222",
                "is_approved": True
            }
        )

        if created:
            pharmacist.set_password("test123")
            pharmacist.save()

        self.stdout.write("Creating patient...")

        patient = Patient.objects.create(
            full_name="Test Patient",
            age=35,
            gender="MALE",
            phone="9999999999",
            created_by=doctor
        )

        self.stdout.write("Creating medicine category...")

        category, _ = MedicineCategory.objects.get_or_create(
            name="General"
        )

        self.stdout.write("Creating medicine...")

        medicine, _ = Medicine.objects.get_or_create(
            name="Paracetamol",
            defaults={
                "category": category,
                "default_selling_price": 10,
                "gst_percentage": 5
            }
        )

        self.stdout.write("Creating supplier...")

        supplier, _ = Supplier.objects.get_or_create(
            name="ABC Pharma",
            defaults={
                "phone": "1234567890"
            }
        )

        self.stdout.write("Creating batch...")

        Batch.objects.get_or_create(
            medicine=medicine,
            batch_number="B001",
            defaults={
                "supplier": supplier,
                "purchase_price": 5,
                "selling_price": 10,
                "quantity": 200,
                "expiry_date": "2030-01-01"
            }
        )

        self.stdout.write(
            self.style.SUCCESS(
                "\nDemo data created successfully!\n"
                "Doctor Login: doctor@test.com / test123\n"
                "Pharmacist Login: pharmacist@test.com / test123\n"
            )
        )