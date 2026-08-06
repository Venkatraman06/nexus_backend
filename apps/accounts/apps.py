from django.apps import AppConfig
from django.db.models.signals import post_migrate


def setup_periodic_tasks(sender, **kwargs):
    import logging
    logger = logging.getLogger(__name__)

    try:
        from django_celery_beat.models import PeriodicTask, CrontabSchedule

        # 1. Sync Keycloak users every 5 minutes
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="*/5",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="Asia/Kolkata",
        )
        PeriodicTask.objects.get_or_create(
            name="Sync Employees with Keycloak",
            defaults={
                "task": "accounts.sync_keycloak_users",
                "crontab": schedule,
            }
        )

        # 2. Scan due date reminders daily at 9:00 AM
        daily_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="9",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="Asia/Kolkata",
        )
        PeriodicTask.objects.get_or_create(
            name="Scan Due Date Reminders",
            defaults={
                "task": "notifications.scan_due_date_reminders",
                "crontab": daily_schedule,
            }
        )

        logger.info("Keycloak and Due-Date sync tasks registered in database successfully.")
    except Exception as exc:
        logger.debug("Could not auto-register celery beat tasks: %s", exc)


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        post_migrate.connect(setup_periodic_tasks, sender=self)

