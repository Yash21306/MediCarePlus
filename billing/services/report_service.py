from django.db.models import Sum, Count
from django.utils import timezone
from billing.models import Invoice, InvoiceItem
from django.db.models.functions import TruncDate
from datetime import timedelta

class ReportService:

    @staticmethod
    def total_revenue():
        return (
            Invoice.objects
            .filter(status="PAID")
            .aggregate(total=Sum("total_amount"))["total"] or 0
        )

    @staticmethod
    def today_revenue():
        today = timezone.now().date()
        return (
            Invoice.objects
            .filter(status="PAID", created_at__date=today)
            .aggregate(total=Sum("total_amount"))["total"] or 0
        )

    @staticmethod
    def today_sales_count():
        today = timezone.now().date()
        return (
            Invoice.objects
            .filter(status="PAID", created_at__date=today)
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
            .aggregate(total=Sum("total_amount"))["total"] or 0
        )  

    @staticmethod
    def last_7_days_revenue():
        today = timezone.now().date()
        start_date = today - timedelta(days=6)

        data = (
            Invoice.objects
            .filter(status="PAID", created_at__date__gte=start_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Sum("total_amount"))
            .order_by("day")
        )

        revenue_map = {entry["day"]: float(entry["total"]) for entry in data}

        labels = []
        values = []

        for i in range(7):
            day = start_date + timedelta(days=i)
            labels.append(day.strftime("%d %b"))
            values.append(revenue_map.get(day, 0))

        return labels, values

    @staticmethod
    def top_selling_medicines():
        return (
            InvoiceItem.objects
            .filter(invoice__status="PAID")
            .values("medicine__name")
            .annotate(total_sold=Sum("quantity"))
            .order_by("-total_sold")[:5]
        )    