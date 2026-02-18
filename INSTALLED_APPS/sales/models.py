from django.db import models
from accounts.models import CustomUser

# Create your models here.

class Sale(models.Model):
    pharmacist = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sale #{self.id}"

from inventory.models import Medicine, Batch
from django.core.exceptions import ValidationError
from django.db import transaction

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        with transaction.atomic():

            required_qty = self.quantity

            # FIFO: oldest expiry first
            batches = Batch.objects.filter(
                medicine=self.medicine,
                quantity__gt=0
            ).order_by('expiry_date')

            total_available = sum(b.quantity for b in batches)

            if total_available < required_qty:
                raise ValidationError("Not enough stock available")

            for batch in batches:
                if required_qty <= 0:
                    break

                if batch.quantity >= required_qty:
                    batch.quantity -= required_qty
                    batch.save()
                    required_qty = 0
                else:
                    required_qty -= batch.quantity
                    batch.quantity = 0
                    batch.save()

            # GST calculation
            gst_rate = self.medicine.gst_percentage
            self.gst_amount = (self.price_at_sale * self.quantity * gst_rate) / 100

            super().save(*args, **kwargs)

            # Update Sale totals
            self.sale.total_amount += self.price_at_sale * self.quantity
            self.sale.total_gst += self.gst_amount
            self.sale.save()
