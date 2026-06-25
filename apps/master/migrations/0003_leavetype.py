import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0002_holiday'),
    ]

    # LeaveType already exists as a real table (hrms_leave_type, owned by the
    # attendance app's migration state up to this point). This migration only
    # introduces it into master's migration *state* — the matching DeleteModel
    # (attendance state) + the real schema changes (drop created_by/updated_by/
    # is_deleted, add slug) happen in attendance's migrations that depend on
    # this one, so the state and the database stay in sync.
    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='LeaveType',
                    fields=[
                        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ('name', models.CharField(max_length=200, unique=True)),
                        ('slug', models.SlugField(blank=True, max_length=200, unique=True)),
                        ('is_active', models.BooleanField(default=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('code', models.CharField(max_length=20, unique=True)),
                        ('max_days', models.PositiveIntegerField(default=0, help_text='Max days allowed per year (0 = unlimited)')),
                        ('is_paid', models.BooleanField(default=True)),
                        ('color', models.CharField(default='#1677ff', max_length=20)),
                    ],
                    options={
                        'db_table': 'hrms_leave_type',
                        'ordering': ['name'],
                        'verbose_name': 'leave type',
                        'verbose_name_plural': 'leave types',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
