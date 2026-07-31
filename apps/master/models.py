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


class FollowupTypeMaster(MasterBase):
    color = models.CharField(max_length=50, blank=True, default="#6366F1")

    class Meta(MasterBase.Meta):
        db_table = "master_followup_type"
        verbose_name = _("followup type")
        verbose_name_plural = _("followup types")


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

class Holiday(MasterBase):
    """Holiday master. `name` is intentionally not globally unique (e.g. 'New Year'
    recurs every year on a different date) — uniqueness is enforced per (date, name)."""
    name        = models.CharField(max_length=200)
    date        = models.DateField()
    year        = models.PositiveIntegerField()
    holiday_type = models.CharField(max_length=20, choices=[
        ("GOVERNMENT", "Government Holiday"),
        ("COMPANY",    "Company Holiday"),
    ], default="GOVERNMENT")
    description = models.TextField(blank=True, default="")

    class Meta(MasterBase.Meta):
        db_table = "master_holiday"
        ordering = ["date"]
        unique_together = ("date", "name")
        verbose_name = _("holiday")
        verbose_name_plural = _("holidays")

    def save(self, *args, **kwargs):
        if self.date:
            if isinstance(self.date, str):
                from datetime import datetime
                try:
                    self.date = datetime.strptime(self.date, "%Y-%m-%d").date()
                except ValueError:
                    pass
            self.year = self.date.year
        if not self.slug:
            base = slugify(self.name)
            self.slug = f"{base}-{self.date.isoformat()}" if self.date else base
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.date})"


class LeaveType(MasterBase):
    code     = models.CharField(max_length=20, unique=True)
    max_days = models.DecimalField(max_digits=5, decimal_places=1, default=0, help_text="Max days allowed per year (0 = unlimited)")
    is_paid  = models.BooleanField(default=True)
    color    = models.CharField(max_length=20, default="#1677ff")

    class Meta(MasterBase.Meta):
        db_table = "hrms_leave_type"
        verbose_name = _("leave type")
        verbose_name_plural = _("leave types")


class ReimbursementConfig(models.Model):
    """
    Singleton master configuration for the reimbursement approval workflow.

    Design rationale
    ----------------
    The business rule is: exactly ONE employee is the designated approver for all
    reimbursement requests across the organisation at any point in time.  The old
    implementation modelled this as a regular list, which allowed multiple rows and
    created ambiguity about which row was authoritative.

    This redesign enforces the singleton constraint at the database level via a
    partial unique index on `is_singleton=True`, making it physically impossible
    to insert a second configuration row.  `get_active()` is the single read
    access-point, and `set_approver()` is the single write access-point — both
    owned exclusively by this model class (Single Responsibility Principle).

    Future multi-level approval support: add an `ApprovalLevel` child model with
    a FK to this config and a `level` integer, keeping the singleton config as the
    root without breaking this interface.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The singleton sentinel — only one row may have is_singleton=True (enforced
    # by the unique_together below), and we always operate on that row.
    is_singleton = models.BooleanField(
        default=True,
        editable=False,
        help_text="Internal sentinel. Always True. Prevents duplicate config rows.",
    )

    approver = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.PROTECT,
        related_name="reimbursement_approval_config",
        help_text="The single employee responsible for approving all reimbursement claims.",
    )

    configured_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reimbursement_configs_created",
        help_text="The admin who last updated this configuration.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "master_reimbursement_config"
        # Enforces the singleton constraint at DB level — only one row where
        # is_singleton=True can exist.  Any attempt to INSERT a second row with
        # is_singleton=True will raise an IntegrityError.
        constraints = [
            models.UniqueConstraint(
                fields=["is_singleton"],
                name="unique_reimbursement_singleton",
                condition=models.Q(is_singleton=True),
            )
        ]
        verbose_name = _("reimbursement config")
        verbose_name_plural = _("reimbursement config")

    def __str__(self):
        return f"Reimbursement Config → Approver: {self.approver}"

    def save(self, *args, **kwargs):
        """Force is_singleton=True on every save — cannot be overridden."""
        self.is_singleton = True
        super().save(*args, **kwargs)

    # ── Class-level access points (Single Responsibility) ────────────────────

    @classmethod
    def get_active(cls):
        """
        Returns the singleton config, or None if not yet configured.
        This is the *only* place other modules should read the approver.
        """
        return cls.objects.select_related("approver", "configured_by").filter(is_singleton=True).first()

    @classmethod
    def set_approver(cls, approver_employee, configured_by_employee=None):
        """
        Upsert the singleton configuration.  Always updates the single row;
        never creates duplicates.  Atomic to prevent race conditions.

        Returns the config instance.
        """
        from django.db import transaction
        with transaction.atomic():
            config, _created = cls.objects.select_for_update().get_or_create(
                is_singleton=True,
                defaults={
                    "approver": approver_employee,
                    "configured_by": configured_by_employee,
                },
            )
            if not _created:
                config.approver = approver_employee
                config.configured_by = configured_by_employee
                config.save(update_fields=["approver", "configured_by", "updated_at"])
        return config