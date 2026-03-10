from django.db.models import Sum, F
from django.utils import timezone
from django.db.models.functions import TruncDate, TruncMonth
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from billing.models import Invoice, InvoiceItem, InvoiceItemBatch



class ReportService:

    # =========================
    # BASIC REVENUE REPORTS
    # =========================

    @staticmethod
    def total_revenue():
        return (
            Invoice.objects
            .filter(status="PAID")
            .aggregate(total=Sum("total_amount"))["total"]
            or Decimal("0.00")
        )

    @staticmethod
    def today_revenue():
        today = timezone.now().date()
        start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        end = start + timedelta(days=1)

        return (
            Invoice.objects
            .filter(
                status="PAID",
                created_at__gte=start,
                created_at__lt=end
            )
            .aggregate(total=Sum("total_amount"))["total"]
            or Decimal("0.00")
        )

    @staticmethod
    def today_sales_count():
        today = timezone.now().date()
        start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        end = start + timedelta(days=1)

        return (
            Invoice.objects
            .filter(
                status="PAID",
                created_at__gte=start,
                created_at__lt=end
            )
            .count()
        )

    @staticmethod
    def monthly_revenue():
        now = timezone.now()
        return (
            Invoice.objects
            .filter(
                status="PAID",
                created_at__year=now.year,
                created_at__month=now.month
            )
            .aggregate(total=Sum("total_amount"))["total"]
            or Decimal("0.00")
        )

    @staticmethod
    def last_7_days_revenue():
        today = timezone.now().date()
        start_date = today - timedelta(days=6)

        data = (
            Invoice.objects
            .filter(
                status="PAID",
                created_at__date__gte=start_date
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Sum("total_amount"))
            .order_by("day")
        )

        revenue_map = {
            entry["day"]: entry["total"]
            for entry in data
        }

        labels = []
        values = []

        for i in range(7):
            day = start_date + timedelta(days=i)
            labels.append(day.strftime("%d %b"))
            values.append(revenue_map.get(day, Decimal("0.00")))

        return labels, values

    @staticmethod
    def top_selling_medicines():
        return (
            InvoiceItem.objects
            .filter(invoice__status="PAID")
            .values("prescription_item__medicine__name")
            .annotate(total_sold=Sum("quantity"))
            .order_by("-total_sold")[:5]
        )

    @staticmethod
    def pharmacist_dashboard_data():
        return {
            "total_revenue": ReportService.total_revenue(),
            "today_revenue": ReportService.today_revenue(),
            "today_sales_count": ReportService.today_sales_count(),
            "monthly_revenue": ReportService.monthly_revenue(),
            "last_7_days": ReportService.last_7_days_revenue(),
            "top_medicines": list(ReportService.top_selling_medicines())
        }

    @staticmethod
    def sales_by_date_range(start_date=None, end_date=None):
        invoices = Invoice.objects.filter(status="PAID")

        if start_date:
            invoices = invoices.filter(created_at__date__gte=start_date)

        if end_date:
            invoices = invoices.filter(created_at__date__lte=end_date)

        invoices = invoices.order_by("-created_at")

        total_revenue = (
            invoices.aggregate(total=Sum("total_amount"))["total"]
            or Decimal("0.00")
        )

        return invoices, total_revenue

    # =========================
    # MEDICINE PROFIT REPORT
    # =========================

    @staticmethod
    def medicine_profit_report(start_date=None, end_date=None):

        allocations = InvoiceItemBatch.objects.filter(
            invoice_item__invoice__status="PAID"
        ).select_related(
            "invoice_item",
            "batch",
            "invoice_item__medicine"
        )

        if start_date:
            allocations = allocations.filter(
                invoice_item__invoice__created_at__date__gte=start_date
            )

        if end_date:
            allocations = allocations.filter(
                invoice_item__invoice__created_at__date__lte=end_date
            )

        report = {}

        for allocation in allocations:
            medicine = allocation.invoice_item.medicine
            qty = allocation.quantity

            sale_price = allocation.invoice_item.price_at_sale
            purchase_price = allocation.batch.purchase_price

            revenue = qty * sale_price
            cost = qty * purchase_price
            profit = revenue - cost

            if medicine.id not in report:
                report[medicine.id] = {
                    "medicine": medicine.name,
                    "quantity_sold": 0,
                    "revenue": Decimal("0.00"),
                    "cost": Decimal("0.00"),
                    "profit": Decimal("0.00"),
                    "margin": 0,
                }

            report[medicine.id]["quantity_sold"] += qty
            report[medicine.id]["revenue"] += revenue
            report[medicine.id]["cost"] += cost
            report[medicine.id]["profit"] += profit

        result = list(report.values())

        # Calculate margin and sort
        for item in result:
            if item["revenue"] > 0:
                item["margin"] = round(
                    (item["profit"] / item["revenue"]) * 100, 2
                )
            else:
                item["margin"] = 0

        result.sort(key=lambda x: x["profit"], reverse=True)

        total_revenue = sum(item["revenue"] for item in result)
        total_cost = sum(item["cost"] for item in result)
        total_profit = sum(item["profit"] for item in result)

        if total_revenue > 0:
            total_margin = round((total_profit / total_revenue) * 100, 2)
        else:
            total_margin = 0

        summary = {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_profit": total_profit,
            "total_margin": total_margin,
        }

        return result, summary


    @staticmethod
    def monthly_profit_trend(months=6):

        today = datetime.today()
        start_date = today - relativedelta(months=months-1)

        data = (
            InvoiceItemBatch.objects
            .filter(invoice_item__invoice__created_at__date__gte=start_date)
            .annotate(month=TruncMonth("invoice_item__invoice__created_at"))
            .values("month")
            .annotate(
                revenue=Sum("invoice_item__total_with_tax"),
                profit=Sum("invoice_item__subtotal")
            )
            .order_by("month")
        )

        data_dict = {
            d["month"].strftime("%Y-%m"): d
            for d in data
        }

        labels = []
        revenue_values = []
        profit_values = []

        current = start_date.replace(day=1)

        for i in range(months):

            key = current.strftime("%Y-%m")

            labels.append(current.strftime("%b %Y"))

            if key in data_dict:
                revenue_values.append(float(data_dict[key]["revenue"] or 0))
                profit_values.append(float(data_dict[key]["profit"] or 0))
            else:
                revenue_values.append(0)
                profit_values.append(0)

            current += relativedelta(months=1)

        return labels, revenue_values, profit_values

    @staticmethod
    def dashboard_analytics():

        from billing.models import InvoiceItem
        from pharmacy.models import Batch

        # ----- TOTAL STOCK VALUE -----
        stock_value = Batch.objects.aggregate(
            value=Sum(F("quantity") * F("purchase_price"))
        )["value"] or 0

        # ----- MOST PROFITABLE MEDICINE -----
        top = (
            InvoiceItem.objects
            .values("medicine__name")
            .annotate(profit=Sum("subtotal"))
            .order_by("-profit")
            .first()
        )

        most_profitable = top["medicine__name"] if top else "N/A"


        # ----- MONTHLY GROWTH -----
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.now().date()

        this_month = today.replace(day=1)
        last_month = (this_month - timedelta(days=1)).replace(day=1)

        this_rev = InvoiceItem.objects.filter(
            invoice__created_at__date__gte=this_month
        ).aggregate(total=Sum("total_with_tax"))["total"] or 0


        last_rev = InvoiceItem.objects.filter(
            invoice__created_at__date__gte=last_month,
            invoice__created_at__date__lt=this_month
        ).aggregate(total=Sum("total_with_tax"))["total"] or 0


        growth = 0

        if last_rev > 0:
            growth = ((this_rev - last_rev) / last_rev) * 100


        return {
            "stock_value": round(stock_value, 2),
            "most_profitable": most_profitable,
            "monthly_growth": round(growth, 1)
        }
    
    @staticmethod
    def sales_by_category():

        from billing.models import InvoiceItem

        sales = (
            InvoiceItem.objects
            .values("medicine__category__name")
            .annotate(total=Sum("quantity"))
            .order_by("-total")[:5]
        )

        labels = []
        values = []

        for s in sales:
            labels.append(s["medicine__category__name"] or "Other")
            values.append(s["total"])

        return labels, values

    @staticmethod
    def top_medicines_today():

        from billing.models import InvoiceItem

        today = timezone.now().date()

        sales = (
            InvoiceItem.objects
            .filter(invoice__created_at__date=today)
            .values("medicine__name")
            .annotate(total=Sum("quantity"))
            .order_by("-total")[:5]
        )

        labels = []
        values = []

        for s in sales:
            labels.append(s["medicine__name"])
            values.append(s["total"])

        return labels, values
    
    @staticmethod
    def dead_stock(days=60):

        from pharmacy.models import Medicine
        from billing.models import InvoiceItem
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)

        sold_recently = InvoiceItem.objects.filter(
            invoice__status="PAID",
            invoice__created_at__gte=cutoff
        ).values_list("medicine_id", flat=True)

        dead_stock = Medicine.objects.exclude(
            id__in=sold_recently
        ).filter(stock_quantity__gt=0)

        return dead_stock[:5]
    
    @staticmethod
    def fast_moving_medicines():

        from billing.models import InvoiceItem

        return (
            InvoiceItem.objects
            .filter(invoice__status="PAID")
            .values("medicine__name")
            .annotate(total_sold=Sum("quantity"))
            .order_by("-total_sold")[:5]
        )