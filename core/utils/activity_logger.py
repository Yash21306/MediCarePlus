from core.models import ActivityLog


def log_activity(user, action_type, description):

    ActivityLog.objects.create(
        user=user,
        action_type=action_type,
        description=description
    )