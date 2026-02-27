from django.contrib import admin
from .models import Medicine, Batch

# =========================
# Batch Inline for Medicine
# =========================
class BatchInline(admin.TabularInline):
    model = Batch
    extra = 1

# =========================
# Medicine Admin
# =========================
@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'manufacturer',
        'price',
        'stock_quantity',
        'is_active'
    )
    list_filter = ('is_active',)
    search_fields = ('name',)
    inlines = [BatchInline]

# =========================
# Batch Admin
# =========================
@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        'medicine',
        'batch_number',
        'expiry_date',
        'quantity'
    )
    list_filter = ('expiry_date',)
    search_fields = ('medicine__name', 'batch_number')