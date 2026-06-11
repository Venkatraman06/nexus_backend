import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timesheets", "0001_initial"),
        ("workitems", "0003_remove_worklog_work_log_work_it_c29d0f_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="worklog",
            name="description",
            field=models.TextField(blank=True, default="", help_text="Work performed"),
        ),
        migrations.AddField(
            model_name="worklog",
            name="category",
            field=models.CharField(
                choices=[
                    ("BILLABLE", "Billable"),
                    ("NON_BILLABLE", "Non-Billable"),
                    ("INTERNAL", "Internal"),
                    ("TRAINING", "Training"),
                    ("SUPPORT", "Support"),
                ],
                default="BILLABLE",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="worklog",
            name="weekly_timesheet",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="work_logs",
                to="timesheets.weeklytimesheet",
            ),
        ),
    ]
