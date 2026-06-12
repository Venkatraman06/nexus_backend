import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TimesheetConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("daily_capacity_hours", models.DecimalField(decimal_places=2, default=8, help_text="Effective daily capacity in hours (8, 9, or 10)", max_digits=4)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "timesheet_config",
            },
        ),
        migrations.CreateModel(
            name="WeeklyTimesheet",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("week_start", models.DateField(help_text="Monday of the week")),
                ("week_end", models.DateField(help_text="Friday of the week")),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("SUBMITTED", "Submitted"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="DRAFT", max_length=12)),
                ("total_hours", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("expected_hours", models.DecimalField(decimal_places=2, default=40, max_digits=7)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_comment", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weekly_timesheets", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_timesheets", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "weekly_timesheet",
                "ordering": ["-week_start"],
            },
        ),
        migrations.CreateModel(
            name="TimesheetReviewLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("action", models.CharField(max_length=20)),
                ("comment", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("performed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="timesheet_review_actions", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_updated", to=settings.AUTH_USER_MODEL)),
                ("weekly_timesheet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="review_logs", to="timesheets.weeklytimesheet")),
            ],
            options={
                "db_table": "timesheet_review_log",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="weeklytimesheet",
            index=models.Index(fields=["employee", "week_start"], name="weekly_time_employe_0a8f2a_idx"),
        ),
        migrations.AddIndex(
            model_name="weeklytimesheet",
            index=models.Index(fields=["status", "week_start"], name="weekly_time_status_9c3b1d_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="weeklytimesheet",
            unique_together={("employee", "week_start")},
        ),
    ]
