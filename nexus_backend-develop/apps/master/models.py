import uuid

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class MasterBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True
        ordering = ["name"]


class Designation(MasterBase):
    class Meta(MasterBase.Meta):
        db_table = "master_employee_designation"
        verbose_name = _("designation")
        verbose_name_plural = _("designations")


class Department(MasterBase):
    class Meta(MasterBase.Meta):
        db_table = "master_employee_department"
        verbose_name = _("department")
        verbose_name_plural = _("departments")


class Location(MasterBase):
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="India")

    class Meta(MasterBase.Meta):
        db_table = "master_employee_location"
        verbose_name = _("location")
        verbose_name_plural = _("locations")


class Grade(MasterBase):
    class Meta(MasterBase.Meta):
        db_table = "master_employee_grade"
        verbose_name = _("grade")
        verbose_name_plural = _("grades")


class EmploymentType(MasterBase):
    class Meta(MasterBase.Meta):
        db_table = "master_employee_employment_type"
        verbose_name = _("employment type")
        verbose_name_plural = _("employment types")


class ShiftCategory(MasterBase):
    """Predefined shift timings. Duration must be 9 hours (enforced in serializer)."""
    start_time = models.TimeField()
    end_time   = models.TimeField()

    class Meta(MasterBase.Meta):
        db_table = "master_employee_shift_category"
        verbose_name = _("shift category")
        verbose_name_plural = _("shift categories")


class ClientCategory(MasterBase):
    class Meta(MasterBase.Meta):
        db_table = "master_client_category"
        verbose_name = _("client category")
        verbose_name_plural = _("client categories")


class BusinessType(MasterBase):
    """Configurable project business type (e.g. Project, Training, POC). Prefix is used for code auto-generation."""
    prefix = models.CharField(
        max_length=10, blank=True, default="",
        help_text="Short uppercase prefix used for auto-generating project codes, e.g. PRJ, TRN, SVC"
    )

    class Meta(MasterBase.Meta):
        db_table = "master_project_business_type"
        verbose_name = _("business type")
        verbose_name_plural = _("business types")


class BillingType(MasterBase):
    class Meta(MasterBase.Meta):
        db_table = "master_project_billing_type"
        verbose_name = _("billing type")
        verbose_name_plural = _("billing types")


class RateCard(models.Model):
    """
    Daily billing / HR cost rates per designation × department combination.

    hr_daily_rate       — what the company pays the employee (per working day)
    client_billing_rate — what the company charges the client (per working day)

    Monthly CTC = hr_daily_rate × payable_working_days
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    designation_ref = models.ForeignKey(
        "Designation", on_delete=models.CASCADE, related_name="rate_cards",
    )
    department_ref = models.ForeignKey(
        "Department", on_delete=models.CASCADE, related_name="rate_cards",
    )
    hr_daily_rate       = models.DecimalField(max_digits=10, decimal_places=2,
                                              help_text="Daily cost to company (₹)")
    client_billing_rate = models.DecimalField(max_digits=10, decimal_places=2,
                                              help_text="Daily rate billed to client (₹)")
    currency   = models.CharField(max_length=10, default="INR")
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "master_employee_rate_card"
        unique_together = ("designation_ref", "department_ref")
        ordering = ["designation_ref__name", "department_ref__name"]
        verbose_name = _("rate card")
        verbose_name_plural = _("rate cards")

    def __str__(self):
        return f"{self.designation_ref} / {self.department_ref} — ₹{self.hr_daily_rate}/day"
