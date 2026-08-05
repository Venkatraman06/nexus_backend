from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0002_add_policy_acknowledgment"),
    ]

    operations = [
        migrations.AddField(
            model_name="policydocumentacknowledgment",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]
