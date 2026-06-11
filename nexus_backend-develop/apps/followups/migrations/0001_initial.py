import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0002_employee_wfh_allowed"),
        ("pmt_workflow", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FollowUp",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=300)),
                ("type", models.CharField(
                    choices=[
                        ("EMAIL", "Email"),
                        ("CALL", "Call"),
                        ("MEETING", "Meeting"),
                        ("WHATSAPP", "WhatsApp"),
                        ("SITE_VISIT", "Site Visit"),
                    ],
                    default="CALL",
                    max_length=20,
                )),
                ("description", models.TextField(blank=True, default="")),
                ("comments", models.TextField(blank=True, default="")),
                ("due_date", models.DateField(blank=True, null=True)),
                ("assignee", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assigned_followups",
                    to="accounts.employee",
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="followup_created",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("reporter", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reported_followups",
                    to="accounts.employee",
                )),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="followup_updated",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("workflow_state", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="followups",
                    to="pmt_workflow.state",
                )),
            ],
            options={
                "db_table": "crm_followup",
                "ordering": ["-created_at"],
            },
        ),
    ]
