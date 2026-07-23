from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_attendancemonthlyreport'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Rename submitted_by -> reporting_manager
        migrations.RenameField(
            model_name='attendancemonthlyreport',
            old_name='submitted_by',
            new_name='reporting_manager',
        ),
        # Rename pm_remarks -> ceo_remarks
        migrations.RenameField(
            model_name='attendancemonthlyreport',
            old_name='pm_remarks',
            new_name='ceo_remarks',
        ),
        # Update status choices (stored values change)
        migrations.AlterField(
            model_name='attendancemonthlyreport',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING',         'Pending – Submitted to CEO'),
                    ('APPROVED_BY_CEO', 'Approved by CEO'),
                    ('REJECTED_BY_CEO', 'Rejected by CEO'),
                ],
                default='PENDING',
                max_length=20,
            ),
        ),
    ]
