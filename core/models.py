from django.conf import settings
from django.db import models


class ActivityLog(models.Model):

    ACTION_TYPES = [
        ("USER_APPROVED", "User Approved"),
        ("USER_REJECTED", "User Rejected"),
        ("MEDICINE_SOLD", "Medicine Sold"),
        ("STOCK_UPDATED", "Stock Updated"),
        ("INVOICE_CREATED", "Invoice Created"),
        ("USER_REGISTERED", "User Registered"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)

    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action_type} - {self.created_at}"
    
class Notification(models.Model):

    TYPE_CHOICES = [
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("CRITICAL", "Critical"),
    ]

    title = models.CharField(max_length=255)
    message = models.TextField()

    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="INFO"
    )

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title