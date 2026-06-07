from django.db import migrations


def sync_notification_templates(apps, schema_editor):
    from apps.notifications.templates_registry import sync_templates
    sync_templates()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sync_notification_templates, migrations.RunPython.noop),
    ]
