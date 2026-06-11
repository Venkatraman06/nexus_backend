from django.db import migrations


class Migration(migrations.Migration):
    """Remove Epic and Story models — replaced by Ticket hierarchy."""

    dependencies = [
        ("projects", "0001_initial"),
        ("workitems", "0002_drop_workitem_add_ticket_fk"),
    ]

    operations = [
        migrations.DeleteModel(name="Story"),
        migrations.DeleteModel(name="Epic"),
    ]
