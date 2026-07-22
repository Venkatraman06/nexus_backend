from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_leaverequest_is_acknowledged'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceMonthlyReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('year', models.PositiveIntegerField()),
                ('month', models.PositiveIntegerField()),
                ('status', models.CharField(
                    choices=[
                        ('PENDING',  'Pending PM Review'),
                        ('APPROVED', 'Approved by PM'),
                        ('REJECTED', 'Rejected by PM'),
                        ('SENT_CEO', 'Sent to CEO'),
                    ],
                    default='PENDING',
                    max_length=20,
                )),
                ('pm_remarks', models.TextField(blank=True, default='')),
                ('summary_data', models.JSONField(blank=True, default=dict)),
                ('submitted_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='submitted_attendance_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_attendance_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'hrms_attendance_monthly_report',
                'ordering': ['-year', '-month'],
                'unique_together': {('year', 'month')},
            },
        ),
    ]
