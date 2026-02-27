from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from consultations.models import Prescription, PrescriptionItem
from pharmacy.models import Medicine, Batch

# =========================
# Invoice Model
# =========================
class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name="invoices")
    invoice_number = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.status}"

    def calculate_total(self):
        total = self.items.aggregate(total=Sum("subtotal"))["total"] or 0
        self.total_amount = total
        self.save(update_fields=["total_amount"])

    def generate_invoice_number(self):
        year = timezone.now().year
        last_invoice = Invoice.objects.select_for_update().filter(invoice_number__startswith=f"INV-{year}-").order_by("-invoice_number").first()
        if last_invoice:
            last_number = int(last_invoice.invoice_number.split("-")[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        return f"INV-{year}-{str(new_number).zfill(5)}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            with transaction.atomic():
                self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)


# =========================
# Invoice Item
# =========================
class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, related_name="invoice_items")
    quantity = models.PositiveIntegerField()
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    prescription_item = models.ForeignKey(PrescriptionItem, on_delete=models.CASCADE, related_name="invoice_items", null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.invoice and self.invoice.status == 'PAID' and self.pk:
            raise ValidationError("Cannot modify items of a PAID invoice.")

        if not self.prescription_item:
            raise ValidationError("Prescription item is required.")

        self.medicine = self.prescription_item.medicine
        self.full_clean()
        self.subtotal = self.quantity * self.price_at_sale
        super().save(*args, **kwargs)

        if self.invoice:
            self.invoice.calculate_total()

    def clean(self):
        super().clean()
        if not self.prescription_item:
            raise ValidationError("Prescription item is required.")
        if self.invoice and self.invoice.status == "PAID" and self.pk:
            raise ValidationError("Cannot modify items of a PAID invoice.")

        prescribed_qty = self.prescription_item.quantity_prescribed
        already_dispensed = InvoiceItem.objects.filter(prescription_item=self.prescription_item, invoice__status='PAID').exclude(pk=self.pk).aggregate(total=Sum('quantity'))['total'] or 0
        remaining = prescribed_qty - already_dispensed
        if self.quantity > remaining:
            raise ValidationError(f"Cannot dispense {self.quantity}. Only {remaining} remaining from prescription.")

    def __str__(self):
        return f"{self.medicine.name} x {self.quantity}"


# =========================
# Payment Model
# =========================
class Payment(models.Model):
    METHOD_CHOICES = (('CASH','Cash'),('CARD','Card'),('UPI','UPI'),('BANK','Bank Transfer'))

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, limit_choices_to={'role':'PHARMACIST'})
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            total_paid = self.invoice.payments.aggregate(total=Sum('amount'))['total'] or 0
            if total_paid + self.amount > self.invoice.total_amount:
                raise ValidationError("Payment exceeds invoice total amount.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount}"


# =========================
# Invoice Log
# =========================
class InvoiceLog(models.Model):
    ACTION_CHOICES = (('PAID','Paid'),('CANCELLED','Cancelled'))
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.action}"


# =========================
# Invoice Item Batch
# =========================
class InvoiceItemBatch(models.Model):
    invoice_item = models.ForeignKey(InvoiceItem, on_delete=models.CASCADE, related_name='batch_allocations')
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='invoice_allocations')
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.invoice_item} -> {self.batch.batch_number} ({self.quantity})"