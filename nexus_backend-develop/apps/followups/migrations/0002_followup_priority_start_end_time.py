from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("followups", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="followup",
            name="priority",
            field=models.CharField(
                choices=[
                    ("IMPORTANT", "Important"),
                    ("HIGH", "High"),
                    ("MEDIUM", "Medium"),
                    ("LOW", "Low"),
                ],
                default="MEDIUM",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="followup",
            name="start_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="followup",
            name="end_time",
            field=models.TimeField(blank=True, null=True),
        ),
    ]
