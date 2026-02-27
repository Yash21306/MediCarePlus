from django.contrib import admin
from .models import (
    Invoice,
    InvoiceItem,
    Payment,
    InvoiceLog,
    InvoiceItemBatch
)

# =========================
# Invoice Admin
# =========================
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'prescription', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('invoice_number', 'prescription__consultation__visit_number')
    readonly_fields = ('invoice_number', 'total_amount', 'created_at')

# =========================
# Invoice Item Admin
# =========================
@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'medicine', 'quantity', 'price_at_sale', 'subtotal')
    search_fields = ('invoice__invoice_number', 'medicine__name')

# =========================
# Payment Admin
# =========================
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'method', 'transaction_id', 'received_by', 'created_at')
    list_filter = ('method', 'created_at')
    search_fields = ('invoice__invoice_number', 'transaction_id')

# =========================
# Invoice Log Admin
# =========================
@admin.register(InvoiceLog)
class InvoiceLogAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'action', 'performed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('invoice__invoice_number', 'performed_by__email')

# =========================
# Invoice Item Batch Admin
# =========================
@admin.register(InvoiceItemBatch)
class InvoiceItemBatchAdmin(admin.ModelAdmin):
    list_display = ('invoice_item', 'batch', 'quantity')
    search_fields = ('invoice_item__invoice__invoice_number', 'batch__batch_number', 'invoice_item__medicine__name')