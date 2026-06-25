import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0010_leavetype_prep_for_master'),
        ('master', '0003_leavetype'),
    ]

    # LeaveType physically stays in the hrms_leave_type table (now owned by the
    # master app's migration state, see master.0003_leavetype). The FK columns
    # on these attendance models are unaffected — only the migration state's
    # notion of which app the target model lives in changes.
    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='leavebalance',
                    name='leave_type',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='balances', to='master.leavetype'),
                ),
                migrations.AlterField(
                    model_name='leaverequest',
                    name='leave_type',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='master.leavetype'),
                ),
                migrations.AlterField(
                    model_name='leavepolicyrule',
                    name='leave_type',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='policy_rules', to='master.leavetype'),
                ),
                migrations.DeleteModel(name='LeaveType'),
            ],
            database_operations=[],
        ),
    ]
