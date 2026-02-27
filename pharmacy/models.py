from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum

class Medicine(models.Model):
    name = models.CharField(max_length=255, unique=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit")
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    def __str__(self):
        return f"{self.name} ({self.stock_quantity} in stock)"

class Batch(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="batches")
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expiry_date"]

    def __str__(self):
        return f"{self.medicine.name} - {self.batch_number} ({self.quantity})"

    def save(self, *args, **kwargs):
        self.full_clean()  # validate first
        super().save(*args, **kwargs)
        self.update_medicine_stock()

    def delete(self, *args, **kwargs):
        medicine = self.medicine
        super().delete(*args, **kwargs)
        total = medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0
        medicine.stock_quantity = total
        medicine.save(update_fields=["stock_quantity"])

    def clean(self):
        if self.expiry_date and self.expiry_date <= timezone.now().date():
            raise ValidationError("Cannot create batch with past expiry date.")
        if self.quantity < 0:
            raise ValidationError("Batch quantity cannot be negative.")

    def update_medicine_stock(self):
        total = self.medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0
        self.medicine.stock_quantity = total
        self.medicine.save(update_fields=["stock_quantity"])

    def is_near_expiry(self, days=30):
        from django.utils import timezone
        today = timezone.now().date()
        return today <= self.expiry_date <= today + timezone.timedelta(days=days)

    def is_expired(self):
        from django.utils import timezone
        return self.expiry_date < timezone.now().date()