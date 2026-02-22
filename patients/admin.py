from django.contrib import admin
from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'age', 'gender', 'phone', 'city', 'created_by', 'created_at')
    list_filter = ('gender', 'city')
    search_fields = ('full_name', 'phone')
    ordering = ('-created_at',)