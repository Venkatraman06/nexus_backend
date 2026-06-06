import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.constants import EmployeeStatus
from packages.storages.dynamic_storage import DynamicS3Storage


class EmployeeManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def create_superuser(self, username, email, password=None, **extra):
        emp = self.model(
            username=username,
            email=email,
            is_staff=True,
            is_superuser=True,
            **extra,
        )
        emp.set_password(password)
        emp.save(using=self._db)
        return emp

    def generate_employee_code(self):
        """Auto-generate next HIT- prefixed code: HIT-001, HIT-002, ..."""
        codes = (
            self.model.objects.filter(employee_code__startswith="HIT-")
            .values_list("employee_code", flat=True)
        )
        nums = []
        for code in codes:
            try:
                nums.append(int(code[4:]))
            except (ValueError, IndexError):
                pass
        num = max(nums) + 1 if nums else 1
        return f"HIT-{num:03d}"


GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other")]


class Employee(AbstractBaseUser, PermissionsMixin):
    """
    Represents a company employee. Can be created manually or synced from Keycloak.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    keycloak_id = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100, blank=True, default="")

    # Master table FK references (preferred over char fields below)
    designation_ref = models.ForeignKey(
        "master.Designation", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employees",
    )
    department_ref = models.ForeignKey(
        "master.Department", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employees",
    )
    location = models.ForeignKey(
        "master.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employees",
    )
    grade = models.ForeignKey(
        "master.Grade", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employees",
    )
    employment_type = models.ForeignKey(
        "master.EmploymentType", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employees",
    )

    # Legacy char fields (kept for Keycloak-synced data)
    designation = models.CharField(max_length=200, blank=True, default="")
    department = models.CharField(max_length=200, blank=True, default="")

    joining_date = models.DateField(null=True, blank=True)
    retirement_date = models.DateField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, default="")
    employee_code = models.CharField(max_length=50, blank=True, default="", db_index=True)
    phone_number       = models.CharField(max_length=20, blank=True, default="")
    alternative_number = models.CharField(max_length=20, blank=True, default="")
    address            = models.TextField(blank=True, default="")
    bio                = models.TextField(blank=True, default="")
    company            = models.CharField(max_length=200, blank=True, default="")
    total_experience   = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    prior_experience   = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    manager            = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="direct_reports",
    )
    shift_applicable   = models.BooleanField(default=False)
    wfh_allowed = models.BooleanField(default=False)
    shift_category     = models.ForeignKey(
        "master.ShiftCategory", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employees",
    )
    custom_shift_start = models.TimeField(null=True, blank=True)
    custom_shift_end   = models.TimeField(null=True, blank=True)
    keycloak_group     = models.CharField(max_length=100, blank=True, default="")

    status = models.CharField(
        max_length=20, choices=EmployeeStatus.choices, default=EmployeeStatus.ACTIVE
    )
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_pmo = models.BooleanField(default=False, help_text="PMO role flag")
    is_manager = models.BooleanField(default=False)
    profile_picture = models.ImageField(
        upload_to="employees/profile/",
        storage=DynamicS3Storage,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EmployeeManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "hrms_employee"
        verbose_name = _("employee")
        verbose_name_plural = _("employees")
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.full_name or self.username

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser


class EmployeeCertificate(models.Model):
    """Stores professional certificates / credentials for an employee."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="certificates"
    )
    title = models.CharField(max_length=200)
    issuing_organization = models.CharField(max_length=200, blank=True, default="")
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    credential_id = models.CharField(max_length=200, blank=True, default="")
    file = models.FileField(
        upload_to="employees/certificates/",
        storage=DynamicS3Storage,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hrms_employee_certificate"
        ordering = ["-issue_date"]

    def __str__(self):
        return f"{self.employee} – {self.title}"



