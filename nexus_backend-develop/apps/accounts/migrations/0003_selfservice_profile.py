# Generated manually for Ticket 2: Employee Self Service Profile

import uuid
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from packages.storages.dynamic_storage import DynamicS3Storage


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_employee_wfh_allowed'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeEmergencyContact',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, default='', max_length=150)),
                ('phone', models.CharField(blank=True, default='', max_length=20)),
                ('relationship', models.CharField(blank=True, default='', max_length=50)),
                ('employee', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='emergency_contact', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'hrms_employee_emergency_contact',
            },
        ),
        migrations.CreateModel(
            name='EmployeeDocument',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('document_type', models.CharField(choices=[('IDENTITY_CARD', 'Identity Card'), ('PAN_CARD', 'PAN Card'), ('PASSPORT', 'Passport'), ('CERTIFICATE', 'Certificate')], default='CERTIFICATE', max_length=20)),
                ('title', models.CharField(max_length=255)),
                ('file', models.FileField(storage=DynamicS3Storage, upload_to='employee-documents/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_documents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'hrms_employee_document',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
