from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("projects", "0001_initial"),
        ("pmt_workflow", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Ticket",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_deleted", models.BooleanField(default=False, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ticket_id", models.CharField(blank=True, db_index=True, max_length=50, unique=True)),
                ("title", models.CharField(max_length=300)),
                ("description", models.TextField(blank=True, default="")),
                ("type", models.CharField(
                    choices=[
                        ("EPIC", "Epic"), ("STORY", "Story"), ("TASK", "Task"),
                        ("SUBTASK", "Sub-Task"), ("BUG", "Bug"),
                        ("CHANGE_REQUEST", "Change Request"), ("DEPLOYMENT", "Deployment"),
                        ("DOCUMENT", "Document"), ("MILESTONE", "Milestone"),
                    ],
                    default="TASK", max_length=20,
                )),
                ("priority", models.CharField(
                    choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High")],
                    default="MEDIUM", max_length=10,
                )),
                ("due_date", models.DateField(blank=True, null=True)),
                ("original_estimate", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("approved", models.BooleanField(default=False)),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="tickets", to="projects.project",
                )),
                ("parent", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="children", to="tickets.ticket",
                )),
                ("assignee", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assigned_tickets", to="accounts.employee",
                )),
                ("reporter", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reported_tickets", to="accounts.employee",
                )),
                ("workflow_state", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="tickets", to="pmt_workflow.state",
                )),
                ("notify_users", models.ManyToManyField(
                    blank=True, related_name="notified_tickets", to="accounts.employee",
                )),
            ],
            options={"db_table": "ticket", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="TicketAttachment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file_name", models.CharField(blank=True, default="", max_length=300)),
                ("file_size", models.PositiveBigIntegerField(default=0)),
                ("content_type", models.CharField(blank=True, default="", max_length=100)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("ticket", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="attachments", to="tickets.ticket",
                )),
                ("uploaded_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="accounts.employee",
                )),
            ],
            options={"db_table": "ticket_attachment", "ordering": ["-uploaded_at"]},
        ),
        migrations.CreateModel(
            name="TicketComment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_deleted", models.BooleanField(default=False, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("body", models.TextField()),
                ("is_edited", models.BooleanField(default=False)),
                ("ticket", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="comments", to="tickets.ticket",
                )),
                ("author", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ticket_comments", to="accounts.employee",
                )),
            ],
            options={"db_table": "ticket_comment", "ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="TicketHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(default="update", max_length=20)),
                ("changes", models.JSONField(default=dict)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("ticket", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="history", to="tickets.ticket",
                )),
                ("changed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ticket_history_entries", to="accounts.employee",
                )),
            ],
            options={"db_table": "ticket_history", "ordering": ["-changed_at"]},
        ),
    ]
