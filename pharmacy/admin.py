from django.contrib import admin
from .models import Medicine, Batch, StockMovement, Supplier, MedicineCategory


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
        "name",
        "manufacturer",
        "category",
        "default_selling_price",
        "stock_quantity",
        "low_stock_threshold",
        "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "hsn_code")
    inlines = [BatchInline]


# =========================
# Batch Admin
# =========================
@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        "medicine",
        "supplier",
        "batch_number",
        "expiry_date",
        "quantity",
    )
    list_filter = ("supplier", "expiry_date")
    search_fields = ("medicine__name", "batch_number")


# =========================
# Stock Movement Admin
# =========================
@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "medicine",
        "movement_type",
        "quantity",
        "batch",
        "reference",
        "performed_by",
        "created_at",
    )
    list_filter = ("movement_type", "created_at")
    search_fields = ("medicine__name", "reference")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =========================
# Supplier Admin
# =========================
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone")
    search_fields = ("name", "contact_person", "phone")


# =========================
# Medicine Category Admin
# =========================
@admin.register(MedicineCategory)
class MedicineCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)