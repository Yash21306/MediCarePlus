from django.contrib import admin
from .models import ActivityLog, Notification


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action_type", "created_at")
    search_fields = ("description",)
    list_filter = ("action_type",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "notification_type", "created_at", "is_read")
    list_filter = ("notification_type", "is_read")
    search_fields = ("title", "message")