from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    """
    Replaces WorkItem/WorkItemAttachment with the new Ticket model.
    WorkLog gains a nullable ticket FK; work_item FK is removed.
    """

    dependencies = [
        ("workitems", "0001_initial"),
        ("tickets", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add ticket FK to WorkLog (nullable)
        migrations.AddField(
            model_name="worklog",
            name="ticket",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="work_logs",
                to="tickets.ticket",
            ),
        ),

        # 2. Remove old indexes that reference work_item
        migrations.AlterIndexTogether(
            name="worklog",
            index_together=set(),
        ),

        # 3. Remove work_item FK from WorkLog
        migrations.RemoveField(
            model_name="worklog",
            name="work_item",
        ),

        # 4. Add new index on (ticket, employee)
        migrations.AddIndex(
            model_name="worklog",
            index=models.Index(fields=["log_date", "employee"], name="worklog_log_date_emp_idx"),
        ),
        migrations.AddIndex(
            model_name="worklog",
            index=models.Index(fields=["ticket", "employee"], name="worklog_ticket_emp_idx"),
        ),

        # 5. Drop WorkItemAttachment
        migrations.DeleteModel(name="WorkItemAttachment"),

        # 6. Drop WorkItem
        migrations.DeleteModel(name="WorkItem"),
    ]
