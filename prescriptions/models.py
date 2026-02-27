from django.db import models
from accounts.models import CustomUser
from patients.models import Patient   # assuming you have Patient model


# =========================
# Diagnosis Model
# =========================
class Diagnosis(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_common = models.BooleanField(default=False)  # For popular diseases
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name