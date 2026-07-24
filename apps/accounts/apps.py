from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        # Auto-register celery beat periodic tasks in the database
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
            # Table may not exist during initial migration
            logger.debug("Could not auto-register celery beat tasks: %s", exc)
