import json
from patients.models import Patient
from pharmacy.models import Medicine
from pharmacy.services import (
    get_low_stock_medicines,
    get_near_expiry_batches,
    get_expired_batches
)
from billing.services.report_service import ReportService


class DashboardService:

    @staticmethod
    def doctor_dashboard_data(user):
        patient_count = Patient.objects.filter(created_by=user).count()

        return {
            "patient_count": patient_count,
        }

    @staticmethod
    def pharmacist_dashboard_data():

        # Revenue trend
        trend_labels, trend_values = ReportService.last_7_days_revenue()

        # Top medicines
        top_medicines = ReportService.top_selling_medicines()
        top_labels = [item["prescription_item__medicine__name"] for item in top_medicines]
        top_values = [item["total_sold"] for item in top_medicines]

        return {
            "total_revenue": ReportService.total_revenue(),

            # inventory stats
            "total_medicines": Medicine.objects.count(),
            "low_stock_count": len(get_low_stock_medicines()),
            "near_expiry_count": len(get_near_expiry_batches()),
            "expired_count": len(get_expired_batches()),

            # charts
            "trend_labels_json": json.dumps(trend_labels),
            "trend_values_json": json.dumps([float(v) for v in trend_values]),

            "top_labels_json": json.dumps(top_labels),
            "top_values_json": json.dumps(top_values),
        }