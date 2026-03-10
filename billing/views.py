from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.utils.timezone import now
from django.utils.dateparse import parse_date

from django.db.models import Sum, Avg, F, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncMonth

from django.http import HttpResponse
from django.template.loader import get_template

from datetime import date, timedelta
import json
import csv

from xhtml2pdf import pisa

from billing.services.report_service import ReportService
from billing.models import Invoice, InvoiceItemBatch, InvoiceItem, Payment

from consultations.models import Prescription
from django.contrib.auth.decorators import login_required

from decimal import Decimal
from pharmacy.models import Batch


# =========================
# Helper: Last N Months
# =========================
def get_last_n_months(n):
    today = now()
    months = []

    year = today.year
    month = today.month

    for _ in range(n):
        months.append(today.replace(year=year, month=month, day=1))

        month -= 1
        if month == 0:
            month = 12
            year -= 1

    return list(reversed(months))


# =========================
# Pharmacist Dashboard
# =========================
class PharmacistDashboardView(TemplateView):
    template_name = "billing/pharmacist_dashboard.html"

    def dispatch(self, request, *args, **kwargs):

        user = request.user

        if not user.is_authenticated:
            raise PermissionDenied("Login required.")

        if user.role != "PHARMACIST":
            raise PermissionDenied("Access restricted to pharmacist.")

        if not user.is_approved:
            raise PermissionDenied("User not approved.")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        today = timezone.now().date()

        total_revenue = Invoice.objects.aggregate(
            total=Sum("total_amount")
        )["total"] or 0

        today_revenue = Invoice.objects.filter(
            created_at__date=today
        ).aggregate(
            total=Sum("total_amount")
        )["total"] or 0

        monthly_revenue = Invoice.objects.filter(
            created_at__year=today.year,
            created_at__month=today.month
        ).aggregate(
            total=Sum("total_amount")
        )["total"] or 0

        total_invoices = Invoice.objects.count()

        avg_sale = Invoice.objects.aggregate(
            avg=Avg("total_amount")
        )["avg"] or 0

        context.update({
            "total_revenue": total_revenue,
            "today_revenue": today_revenue,
            "monthly_revenue": monthly_revenue,
            "total_invoices": total_invoices,
            "avg_sale": avg_sale,
        })

        context.update(ReportService.pharmacist_dashboard_data())

        labels, revenue_values, profit_values = ReportService.monthly_profit_trend(6)

        context["profit_labels_json"] = json.dumps(labels)
        context["profit_values_json"] = json.dumps(profit_values)

        return context


# =========================
# Sales Report
# =========================
def sales_report_view(request):

    invoices = Invoice.objects.filter(status="PAID").order_by("-created_at")

    total_invoices = invoices.count()

    avg_sale = invoices.aggregate(
        avg=Avg("total_amount")
    )["avg"] or 0

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if start_date and end_date:

        start = parse_date(start_date)
        end = parse_date(end_date)

        if start and end:

            invoices = invoices.filter(
                created_at__date__gte=start,
                created_at__date__lte=end
            )

    filtered_total = invoices.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    context = {
        "invoices": invoices,
        "total_revenue": filtered_total,
        "today_revenue": ReportService.today_revenue(),
        "monthly_revenue": ReportService.monthly_revenue(),
        "top_medicines": ReportService.top_selling_medicines(),
        "total_invoices": total_invoices,
        "avg_sale": avg_sale
    }

    return render(request, "billing/sales_report.html", context)


# =========================
# Medicine Profit Report
# =========================
def medicine_profit_report_view(request):

    today = timezone.now().date()

    start_date = today.replace(day=1)
    end_date = today

    if request.GET.get("start_date"):
        start_date = parse_date(request.GET.get("start_date"))

    if request.GET.get("end_date"):
        end_date = parse_date(request.GET.get("end_date"))

    report, summary = ReportService.medicine_profit_report(
        start_date=start_date,
        end_date=end_date
    )

    if request.GET.get("export") == "csv":

        response = HttpResponse(content_type="text/csv")

        response["Content-Disposition"] = 'attachment; filename="medicine_profit_report.csv"'

        writer = csv.writer(response)

        writer.writerow([
            "Medicine",
            "Quantity Sold",
            "Total Revenue",
            "Total Cost",
            "Total Profit",
            "Profit Margin %"
        ])

        for row in report:

            writer.writerow([
                row["medicine"],
                row["quantity"],
                row["revenue"],
                row["cost"],
                row["profit"],
                row["margin"]
            ])

        return response

    return render(request, "billing/medicine_profit_report.html", {
        "report": report,
        "summary": summary,
        "start_date": start_date,
        "end_date": end_date,
    })


# =========================
# Profit Trend Page
# =========================
def profit_trend_view(request):

    period = int(request.GET.get("period", "6"))

    months = get_last_n_months(period)

    profit_expression = ExpressionWrapper(
        (F("invoice_item__price_at_sale") - F("batch__purchase_price")) * F("quantity"),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    data = (
        InvoiceItemBatch.objects
        .filter(
            invoice_item__invoice__status="PAID",
            invoice_item__invoice__created_at__gte=months[0]
        )
        .annotate(month=TruncMonth("invoice_item__invoice__created_at"))
        .annotate(profit=profit_expression)
        .values("month")
        .annotate(total_profit=Sum("profit"))
        .order_by("month")
    )

    revenue_data = (
        Invoice.objects
        .filter(status="PAID", created_at__gte=months[0])
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total_revenue=Sum("total_amount"))
        .order_by("month")
    )

    profit_dict = {}

    for entry in data:
        key = entry['month'].strftime('%Y-%m')
        profit_dict[key] = float(entry['total_profit'] or 0)

    revenue_dict = {}

    for entry in revenue_data:
        key = entry["month"].strftime("%Y-%m")
        revenue_dict[key] = float(entry["total_revenue"] or 0)

    labels = []
    profit_values = []
    revenue_values = []

    for month in months:

        key = month.strftime("%Y-%m")

        labels.append(month.strftime("%b %Y"))

        profit_values.append(profit_dict.get(key, 0))

        revenue_values.append(revenue_dict.get(key, 0))

    context = {
        "labels": json.dumps(labels),
        "profit_values": json.dumps(profit_values),
        "revenue_values": json.dumps(revenue_values),
        "selected_period": period
    }

    return render(request, 'billing/profit_trend.html', context)


# =========================
# Invoice PDF
# =========================
def invoice_pdf(request, invoice_id):

    invoice = get_object_or_404(Invoice, id=invoice_id)

    invoice_items = InvoiceItemBatch.objects.select_related(
        "invoice_item__medicine",
        "batch"
    ).filter(invoice_item__invoice=invoice)

    payments = invoice.payments.all()

    template = get_template("billing/invoice_pdf.html")

    html = template.render({
        "invoice": invoice,
        "invoice_items": invoice_items,
        "payments": payments
    })

    response = HttpResponse(content_type="application/pdf")

    response["Content-Disposition"] = f'inline; filename="invoice_{invoice.invoice_number}.pdf"'

    pisa.CreatePDF(html, dest=response)

    return response


# =========================
# Prescription Queue
# =========================
@login_required
def prescription_queue(request):

    if request.user.role != "PHARMACIST":
        raise PermissionDenied("Pharmacists only.")

    prescriptions = Prescription.objects.filter(
        status__in=["PENDING", "PARTIALLY_BILLED"]
    ).select_related(
        "consultation",
        "consultation__patient",
        "consultation__doctor"
    )

    return render(
        request,
        "billing/prescription_queue.html",
        {"prescriptions": prescriptions}
    )


# =========================
# Create Invoice
# =========================
@login_required
def create_invoice(request, prescription_id):

    if request.user.role != "PHARMACIST":
        raise PermissionDenied("Pharmacists only.")

    prescription = get_object_or_404(Prescription, pk=prescription_id)

    invoice = Invoice.objects.create(
        prescription=prescription
    )

    for item in prescription.items.all():

        already_dispensed = (
            InvoiceItem.objects
            .filter(
                prescription_item=item,
                invoice__status="PAID"
            )
            .aggregate(total=Sum("quantity"))["total"] or 0
        )

        remaining = item.quantity_prescribed - already_dispensed

        if remaining <= 0:
            continue

        medicine = item.medicine

        batch = Batch.objects.filter(
            medicine=medicine,
            quantity__gt=0
        ).order_by("expiry_date").first()

        if not batch:
            raise ValidationError(f"No stock available for {medicine.name}")

        InvoiceItem.objects.create(
            invoice=invoice,
            prescription_item=item,
            quantity=remaining,
            price_at_sale=medicine.default_selling_price
        )

    invoice.calculate_total()

    prescription.status = "BILLED"

    prescription.save(update_fields=["status"])

    return redirect("billing:invoice_detail", invoice.pk)


# =========================
# Invoice Detail
# =========================
@login_required
def invoice_detail(request, pk):

    if request.user.role != "PHARMACIST":
        raise PermissionDenied("Pharmacists only.")

    invoice = get_object_or_404(Invoice, pk=pk)

    return render(
        request,
        "billing/invoice_detail.html",
        {"invoice": invoice}
    )


# =========================
# Invoice List
# =========================
@login_required
def invoice_list(request):

    if request.user.role != "PHARMACIST":
        raise PermissionDenied("Pharmacists only.")

    invoices = Invoice.objects.select_related(
        "prescription",
        "prescription__consultation__patient"
    )

    query = request.GET.get("q")
    status = request.GET.get("status")

    if query:
        invoices = invoices.filter(
            prescription__consultation__patient__full_name__icontains=query
        )

    if status:
        invoices = invoices.filter(status=status)

    invoices = invoices.order_by("-created_at")

    return render(
        request,
        "billing/invoice_list.html",
        {"invoices": invoices}
    )


# =========================
# Add Payment
# =========================
@login_required
def add_payment(request, invoice_id):

    if request.user.role != "PHARMACIST":
        raise PermissionDenied("Pharmacists only.")

    invoice = get_object_or_404(Invoice, pk=invoice_id)

    if request.method == "POST":

        amount = Decimal(request.POST.get("amount"))
        method = request.POST.get("method")

        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            method=method,
            received_by=request.user
        )

        from billing.services.invoice_service import InvoiceService

        InvoiceService.process_payment(invoice, performed_by=request.user)

        return redirect("billing:invoice_detail", invoice.pk)

    return render(
        request,
        "billing/add_payment.html",
        {"invoice": invoice}
    )