from django.db import models

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Supplier(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField()
    gst_number = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class Medicine(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Batch(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="batches")
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['expiry_date']

    def __str__(self):
        return f"{self.medicine.name} - {self.batch_number}"
