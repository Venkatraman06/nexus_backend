# Generated migration for notifications app

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
            name="NotificationTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event_type", models.CharField(choices=[
                    ("ticket.assigned", "Ticket Assigned"),
                    ("ticket.due_today", "Ticket Due Today"),
                    ("project.allocation", "Project Allocation"),
                    ("project.manager_assigned", "Project Manager Assigned"),
                    ("project.due_reminder", "Project Due Reminder"),
                    ("timesheet.submitted", "Timesheet Submitted"),
                    ("timesheet.approved", "Timesheet Approved"),
                    ("timesheet.rejected", "Timesheet Rejected"),
                    ("employee.onboarded", "Employee Onboarded"),
                    ("leave.requested", "Leave Requested"),
                    ("payroll.finalized", "Payroll Finalized"),
                    ("invoice.due_reminder", "Invoice Due Reminder"),
                    ("milestone.due_reminder", "Milestone Due Reminder"),
                    ("payment.overdue", "Payment Overdue"),
                ], max_length=64, unique=True)),
                ("title_template", models.CharField(max_length=255)),
                ("message_template", models.TextField()),
                ("severity", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("urgent", "Urgent")], default="info", max_length=16)),
                ("default_action_url", models.CharField(blank=True, default="", max_length=512)),
                ("supported_channels", models.JSONField(default=list)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "notification_templates", "ordering": ["event_type"]},
        ),
        migrations.CreateModel(
            name="NotificationEventLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event_type", models.CharField(db_index=True, max_length=64)),
                ("reference_type", models.CharField(blank=True, default="", max_length=32)),
                ("reference_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("payload", models.JSONField(default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("notifications_created", models.PositiveIntegerField(default=0)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_notification_events", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(app_label)s_%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "notification_event_logs", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(choices=[
                    ("ticket.assigned", "Ticket Assigned"),
                    ("ticket.due_today", "Ticket Due Today"),
                    ("project.allocation", "Project Allocation"),
                    ("project.manager_assigned", "Project Manager Assigned"),
                    ("project.due_reminder", "Project Due Reminder"),
                    ("timesheet.submitted", "Timesheet Submitted"),
                    ("timesheet.approved", "Timesheet Approved"),
                    ("timesheet.rejected", "Timesheet Rejected"),
                    ("employee.onboarded", "Employee Onboarded"),
                    ("leave.requested", "Leave Requested"),
                    ("payroll.finalized", "Payroll Finalized"),
                    ("invoice.due_reminder", "Invoice Due Reminder"),
                    ("milestone.due_reminder", "Milestone Due Reminder"),
                    ("payment.overdue", "Payment Overdue"),
                ], db_index=True, max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField()),
                ("reference_type", models.CharField(blank=True, choices=[
                    ("ticket", "Ticket"), ("project", "Project"), ("allocation", "Allocation"),
                    ("timesheet", "Timesheet"), ("employee", "Employee"), ("leave", "Leave Request"),
                    ("payroll", "Payroll"), ("invoice", "Invoice"), ("milestone", "Milestone"),
                    ("payment", "Payment"),
                ], default="", max_length=32)),
                ("reference_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("action_url", models.CharField(blank=True, default="", max_length=512)),
                ("severity", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("urgent", "Urgent")], default="info", max_length=16)),
                ("channel", models.CharField(choices=[("in_app", "In-App"), ("email", "Email"), ("push", "Push"), ("slack", "Slack"), ("teams", "Microsoft Teams"), ("whatsapp", "WhatsApp")], default="in_app", max_length=16)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("dedup_key", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="triggered_notifications", to=settings.AUTH_USER_MODEL)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "notifications", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "is_read", "-created_at"], name="notificatio_recipie_6a8f2d_idx"),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=~models.Q(dedup_key=""),
                fields=("recipient", "dedup_key"),
                name="unique_notification_dedup_per_recipient",
            ),
        ),
    ]
