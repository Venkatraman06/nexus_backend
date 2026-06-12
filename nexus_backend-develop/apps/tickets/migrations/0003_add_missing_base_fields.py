from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Add is_active, created_by, updated_by that BaseModel provides but 0001 missed."""

    dependencies = [
        ("tickets", "0002_update_priority_choices"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(app_label)s_%(class)s_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="updated_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(app_label)s_%(class)s_updated",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Same fields for TicketComment (also inherits BaseModel)
        migrations.AddField(
            model_name="ticketcomment",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="ticketcomment",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(app_label)s_%(class)s_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="ticketcomment",
            name="updated_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(app_label)s_%(class)s_updated",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
