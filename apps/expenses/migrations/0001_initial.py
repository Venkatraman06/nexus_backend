import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("projects", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyExpense",
            fields=[
                ("id",              models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active",       models.BooleanField(default=True)),
                ("is_deleted",      models.BooleanField(default=False)),
                ("created_at",      models.DateTimeField(auto_now_add=True)),
                ("updated_at",      models.DateTimeField(auto_now=True)),
                ("expense_number",  models.CharField(blank=True, max_length=50, unique=True)),
                ("date",            models.DateField()),
                ("category",        models.CharField(
                    choices=[
                        ("TRAVEL",    "Travel & Transport"),
                        ("MEALS",     "Meals & Entertainment"),
                        ("OFFICE",    "Office Supplies"),
                        ("SOFTWARE",  "Software & Subscriptions"),
                        ("MARKETING", "Marketing & Advertising"),
                        ("UTILITIES", "Utilities & Internet"),
                        ("EQUIPMENT", "Equipment & Hardware"),
                        ("RENT",      "Rent & Facilities"),
                        ("OTHER",     "Other"),
                    ],
                    default="OTHER",
                    max_length=20,
                )),
                ("description",     models.CharField(max_length=500)),
                ("amount",          models.DecimalField(decimal_places=2, max_digits=12)),
                ("payment_mode",    models.CharField(
                    choices=[
                        ("CASH",           "Cash"),
                        ("CORPORATE_CARD", "Corporate Card"),
                        ("PERSONAL_CARD",  "Personal Card"),
                        ("UPI",            "UPI"),
                        ("BANK_TRANSFER",  "Bank Transfer"),
                        ("CHEQUE",         "Cheque"),
                    ],
                    default="CASH",
                    max_length=20,
                )),
                ("reference_number", models.CharField(blank=True, default="", max_length=100)),
                ("attachment",       models.FileField(blank=True, null=True, upload_to="expenses/receipts/")),
                ("status",           models.CharField(
                    choices=[
                        ("DRAFT",      "Draft"),
                        ("SUBMITTED",  "Submitted"),
                        ("APPROVED",   "Approved"),
                        ("REJECTED",   "Rejected"),
                        ("REIMBURSED", "Reimbursed"),
                    ],
                    default="DRAFT",
                    max_length=20,
                )),
                ("approved_at",      models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, default="")),
                ("notes",            models.TextField(blank=True, default="")),
                ("approved_by",      models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="approved_expenses",
                    to="accounts.employee",
                )),
                ("paid_by",          models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="expenses",
                    to="accounts.employee",
                )),
                ("project",          models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="expenses",
                    to="projects.project",
                )),
                ("client",           models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="expenses",
                    to="projects.client",
                )),
                ("created_by",       models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="expenses_companyexpense_created",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("updated_by",       models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="expenses_companyexpense_updated",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "crm_expense",
                "ordering": ["-date", "-created_at"],
            },
        ),
    ]
