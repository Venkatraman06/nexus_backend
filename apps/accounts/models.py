import datetime
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.constants import EmployeeStatus
from packages.storages.dynamic_storage import DynamicS3Storage


class BaseEmployeeManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class EmployeeManager(BaseEmployeeManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False, is_system_account=False)

    def create_superuser(self, username, email, password=None, **extra):
        emp = self.model(
            username=username,
            email=email,
            is_staff=True,
            is_superuser=True,
            is_system_account=True,
            **extra,
        )
        emp.set_password(password)
        emp.save(using=self._db)
        return emp



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
    is_system_account = models.BooleanField(default=False, help_text="System-level admin account (e.g., CEO Admin)")
    is_pmo = models.BooleanField(default=False, help_text="PMO role flag")
    is_manager = models.BooleanField(default=False)
    profile_picture = models.ImageField(
        upload_to="employees/profile/",
        storage=DynamicS3Storage,
        null=True,
        blank=True,
    )
    totp_secret = models.CharField(max_length=64, blank=True, null=True, help_text="Base32 TOTP secret for Google/Microsoft Authenticator")
    totp_enabled = models.BooleanField(default=False, help_text="Is 2FA enabled for this employee")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EmployeeManager()
    base_objects = BaseEmployeeManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "hrms_employee"
        verbose_name = _("employee")
        verbose_name_plural = _("employees")
        ordering = ["employee_code"]

    def __str__(self):
        return self.full_name or self.username

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @staticmethod
    def get_designation_seniority(emp) -> int:
        """
        Lower score = higher designation seniority.
        Mapping:
        0: CEO / Founder / Chief Executive
        1: CTO / Chief Technology Officer
        2: Co-founder / Co-Founder
        3: Director / VP / Vice President / C-Level Executives (CFO, COO, CMO, etc.)
        4: General Manager / Senior Manager / Manager / Head of Department
        5: Assistant Manager / Team Lead / Architect / Tech Lead / Supervisor
        6: Senior Executive / Senior Specialist / Senior Employee / Principal
        7: Executive / Associate / Specialist / Staff
        8: Junior Associate / Assistant / Trainee / Intern
        """
        desig_name = (
            emp.designation_ref.name
            if getattr(emp, "designation_ref", None)
            else (getattr(emp, "designation", "") or "")
        ).lower().strip()

        if "ceo" in desig_name or "chief executive" in desig_name:
            return 0
        if "cto" in desig_name or "chief technology" in desig_name:
            return 1
        if "co-founder" in desig_name or "cofounder" in desig_name or "co founder" in desig_name:
            return 2
        if "founder" in desig_name or "president" in desig_name:
            return 0
        if "director" in desig_name or "vp" in desig_name or "vice president" in desig_name or desig_name.startswith("c") and "official" in desig_name:
            return 3
        if "general manager" in desig_name or "senior manager" in desig_name or "manager" in desig_name or "head" in desig_name:
            return 4
        if "lead" in desig_name or "architect" in desig_name or "supervisor" in desig_name or "assistant manager" in desig_name:
            return 5
        if "senior" in desig_name or "sr" in desig_name or "principal" in desig_name:
            return 6
        if "intern" in desig_name or "trainee" in desig_name or "junior" in desig_name or "jr" in desig_name:
            return 8
        return 7

    @classmethod
    def build_hierarchy_ordered_list(cls, queryset):
        """
        Builds a hierarchy-aware ordered list of employees based strictly on designation level seniority.
        CEO (0) -> CTO (1) -> Co-founder (2) -> Director/VP (3) -> Manager (4) -> Lead (5) -> Senior (6) -> Employee (7) -> Intern/Trainee (8)
        """
        employees = list(queryset)
        if not employees:
            return []

        all_emp_mgrs = dict(
            cls.objects.filter(is_deleted=False, is_active=True).values_list("id", "manager_id")
        )

        def get_absolute_level(emp_id):
            level = 0
            curr_id = emp_id
            visited_ancestors = set()
            while curr_id in all_emp_mgrs and all_emp_mgrs[curr_id] and all_emp_mgrs[curr_id] not in visited_ancestors:
                visited_ancestors.add(curr_id)
                curr_id = all_emp_mgrs[curr_id]
                level += 1
            return level

        for emp in employees:
            emp._hierarchy_level = get_absolute_level(emp.id)

        def sort_key(emp):
            s_score = cls.get_designation_seniority(emp)
            e_code = emp.employee_code or ""
            j_date = emp.joining_date if emp.joining_date else datetime.date.max
            return (s_score, e_code, j_date, emp.first_name, emp.last_name)

        employees.sort(key=sort_key)
        return employees

    def save(self, *args, **kwargs):
        if self.status == EmployeeStatus.ACTIVE:
            self.is_active = True
        elif self.status == EmployeeStatus.INACTIVE:
            self.is_active = False
        super().save(*args, **kwargs)

        # Sync back to Keycloak if keycloak_id is present and we're not inside keycloak sync itself
        if getattr(self, "_skip_keycloak_sync", False) is False and self.keycloak_id:
            import logging
            logger = logging.getLogger(__name__)
            try:
                from apps.accounts.auth_views import _kc_admin
                from apps.accounts.views import _assign_keycloak_group
                from packages.keycloak.permissions import invalidate_permissions_cache

                admin = _kc_admin()
                admin.update_user(
                    user_id=self.keycloak_id,
                    payload={
                        "username": self.username,
                        "email": self.email,
                        "firstName": self.first_name,
                        "lastName": self.last_name,
                        "enabled": self.is_active,
                    }
                )

                if self.keycloak_group:
                    _assign_keycloak_group(admin, self.keycloak_id, self.keycloak_group)

                invalidate_permissions_cache(self.keycloak_id)
            except Exception as exc:
                logger.warning("Keycloak user update failed for %s during save: %s", self.username, exc)

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



