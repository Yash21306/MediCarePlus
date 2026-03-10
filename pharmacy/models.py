from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum

class MedicineCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subcategories"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    gst_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class Medicine(models.Model):
    name = models.CharField(max_length=255, unique=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    default_selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Default selling price per unit"
    )

    # 🔵 NEW FIELD
    gst_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Total GST percentage (will be split into CGST + SGST)"
    )

    category = models.ForeignKey(
        MedicineCategory,
        on_delete=models.PROTECT,
        related_name="medicines"
    )

    hsn_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="HSN code for GST reporting"
    )

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
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="batches",
    ) 
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
        is_new = self.pk is None
        old_quantity = 0

        if not is_new:
            old_batch = Batch.objects.get(pk=self.pk)
            old_quantity = old_batch.quantity

        self.full_clean()
        super().save(*args, **kwargs)

        quantity_difference = self.quantity - old_quantity

        if is_new:
            # Log purchase
            StockMovement.objects.create(
                medicine=self.medicine,
                batch=self,
                movement_type="PURCHASE",
                quantity=self.quantity,
                reference=f"Batch {self.batch_number}"
            )
        elif quantity_difference != 0:
            # Log adjustment
            StockMovement.objects.create(
                medicine=self.medicine,
                batch=self,
                movement_type="ADJUSTMENT",
                quantity=quantity_difference,
                reference=f"Batch Update {self.batch_number}"
            )

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
    
class StockMovement(models.Model):

    MOVEMENT_TYPES = (
        ("PURCHASE", "Purchase"),
        ("SALE", "Sale"),
        ("ADJUSTMENT", "Adjustment"),
        ("RETURN", "Return"),
    )

    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name="stock_movements"
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movements"
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPES
    )

    quantity = models.IntegerField(
        help_text="Positive for incoming, negative for outgoing"
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Invoice number or manual reference"
    )

    performed_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.medicine.name} | {self.movement_type} | {self.quantity}"
    
