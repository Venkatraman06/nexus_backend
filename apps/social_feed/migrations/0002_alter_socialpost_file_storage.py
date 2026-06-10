from django.db import migrations, models

import packages.storages.dynamic_storage


class Migration(migrations.Migration):

    dependencies = [
        ("social_feed", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialpost",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                storage=packages.storages.dynamic_storage.DynamicS3Storage,
                upload_to="social_feed/images/",
            ),
        ),
        migrations.AlterField(
            model_name="socialpost",
            name="attachment",
            field=models.FileField(
                blank=True,
                null=True,
                storage=packages.storages.dynamic_storage.DynamicS3Storage,
                upload_to="social_feed/attachments/",
            ),
        ),
    ]
