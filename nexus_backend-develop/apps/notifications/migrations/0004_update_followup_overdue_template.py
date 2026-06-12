from django.db import migrations


def sync_followup_overdue_template(apps, schema_editor):
    from apps.notifications.templates_registry import sync_templates
    sync_templates()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_sync_followup_templates"),
    ]

    operations = [
        migrations.RunPython(sync_followup_overdue_template, migrations.RunPython.noop),
    ]
