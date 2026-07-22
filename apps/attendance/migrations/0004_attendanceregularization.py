from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_attendancemonthlyreport'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceRegularizationRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_attendanceregularizationrequest_created', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_attendanceregularizationrequest_updated', to=settings.AUTH_USER_MODEL)),
                ('date', models.DateField()),
                ('reason', models.CharField(
                    choices=[
                        ('FORGOT_CHECKIN',  'Forgot to Check-In'),
                        ('FORGOT_CHECKOUT', 'Forgot to Check-Out'),
                        ('SYSTEM_ERROR',    'System / Technical Error'),
                        ('WFH_MISSED',      'WFH Not Marked'),
                        ('OTHER',           'Other'),
                    ],
                    default='FORGOT_CHECKIN',
                    max_length=30,
                )),
                ('requested_status', models.CharField(
                    choices=[
                        ('PRESENT',  'Present'),
                        ('ABSENT',   'Absent'),
                        ('HALF_DAY', 'Half Day'),
                        ('WFH',      'Work From Home'),
                        ('ON_LEAVE', 'On Leave'),
                        ('HOLIDAY',  'Holiday'),
                        ('WEEKEND',  'Weekend'),
                    ],
                    default='PRESENT',
                    max_length=20,
                )),
                ('check_in',  models.TimeField(blank=True, null=True)),
                ('check_out', models.TimeField(blank=True, null=True)),
                ('remarks',          models.TextField(blank=True, default='')),
                ('status', models.CharField(
                    choices=[
                        ('PENDING',  'Pending'),
                        ('APPROVED', 'Approved'),
                        ('REJECTED', 'Rejected'),
                    ],
                    default='PENDING',
                    max_length=20,
                )),
                ('reviewer_remarks', models.TextField(blank=True, default='')),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='regularization_requests',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='regularization_reviews',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'hrms_attendance_regularization',
                'ordering': ['-created_at'],
            },
        ),
    ]
