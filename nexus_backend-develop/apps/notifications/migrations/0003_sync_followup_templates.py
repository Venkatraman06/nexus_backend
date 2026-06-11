from django.db import migrations


def sync_followup_templates(apps, schema_editor):
    from apps.notifications.templates_registry import sync_templates
    sync_templates()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_sync_templates"),
    ]

    operations = [
        migrations.RunPython(sync_followup_templates, migrations.RunPython.noop),
    ]
