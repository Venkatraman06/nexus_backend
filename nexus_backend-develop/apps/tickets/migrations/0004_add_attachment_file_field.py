from django.db import migrations, models
import packages.storages.dynamic_storage


class Migration(migrations.Migration):
    """Add the missing `file` column to ticket_attachment table."""

    dependencies = [
        ("tickets", "0003_add_missing_base_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketattachment",
            name="file",
            field=models.FileField(
                upload_to="tickets/attachments/",
                storage=packages.storages.dynamic_storage.DynamicS3Storage,
                default="",
                blank=True,
            ),
            preserve_default=False,
        ),
    ]
