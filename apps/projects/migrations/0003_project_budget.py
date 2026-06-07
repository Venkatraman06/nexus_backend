from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0002_remove_epic_story"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="budget",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Total project budget in INR",
                max_digits=14,
            ),
        ),
    ]
