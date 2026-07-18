from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("followups", "0002_rename_due_date_followup_end_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="followup",
            name="meeting_mode",
            field=models.CharField(
                blank=True,
                choices=[("ONLINE", "Online"), ("OFFLINE", "Offline")],
                max_length=10,
                null=True,
            ),
        ),
    ]
