from django.db import migrations, models


class Migration(migrations.Migration):
    """Update Ticket.priority choices to 5 levels: IMMEDIATE, CRITICAL, HIGH, MEDIUM, DEFERRED."""

    dependencies = [
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ticket",
            name="priority",
            field=models.CharField(
                choices=[
                    ("IMMEDIATE", "Immediate"),
                    ("CRITICAL",  "Critical"),
                    ("HIGH",      "High"),
                    ("MEDIUM",    "Medium"),
                    ("DEFERRED",  "Deferred"),
                ],
                default="MEDIUM",
                max_length=10,
            ),
        ),
    ]
