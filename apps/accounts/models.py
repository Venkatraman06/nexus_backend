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
        Lower score = higher seniority.
        Default mapping: CEO (0) -> Director (1) -> Manager (2) -> Lead (3) -> Senior (4) -> Employee (5) -> Intern (6)
        """
        desig_name = (
            emp.designation_ref.name
            if getattr(emp, "designation_ref", None)
            else (getattr(emp, "designation", "") or "")
        ).lower()

        if "ceo" in desig_name or "founder" in desig_name or "president" in desig_name:
            return 0
        if "director" in desig_name or "vp" in desig_name or "vice president" in desig_name or "c-level" in desig_name:
            return 1
        if "general manager" in desig_name or "senior manager" in desig_name or "manager" in desig_name or "head" in desig_name:
            return 2
        if "lead" in desig_name or "architect" in desig_name or "supervisor" in desig_name:
            return 3
        if "senior" in desig_name or "sr" in desig_name or "principal" in desig_name:
            return 4
        if "intern" in desig_name or "trainee" in desig_name:
            return 6
        return 5

    @classmethod
    def build_hierarchy_ordered_list(cls, queryset):
        """
        Builds a hierarchy-aware ordered list of employee dicts or objects from a queryset.
        - Managers before direct reports
        - Hierarchy root sorting based on designation seniority, joining_date, employee_code
        - Preserves hierarchy level / tree depth for UI indentation
        - Cycle detection & duplicate prevention
        """
        employees = list(queryset)
        if not employees:
            return []

        emp_map = {str(e.id): e for e in employees}
        children_map = {}
        top_roots = []

        for e in employees:
            mgr_id = str(e.manager_id) if e.manager_id else None
            # If manager is in the current dataset, add as child of manager
            if mgr_id and mgr_id in emp_map:
                children_map.setdefault(mgr_id, []).append(e)
            else:
                top_roots.append(e)

        # Sort nodes by seniority key
        def sort_key(emp):
            s_score = cls.get_designation_seniority(emp)
            j_date = emp.joining_date if emp.joining_date else datetime.date.max
            e_code = emp.employee_code or ""
            return (s_score, j_date, e_code, emp.first_name, emp.last_name)

        top_roots.sort(key=sort_key)
        for mgr_id in children_map:
            children_map[mgr_id].sort(key=sort_key)

        result = []
        visited = set()

        def dfs(emp, level):
            emp_id = str(emp.id)
            if emp_id in visited:
                return
            visited.add(emp_id)
            emp._hierarchy_level = level
            result.append(emp)

            for child in children_map.get(emp_id, []):
                dfs(child, level + 1)

        for root in top_roots:
            dfs(root, 0)

        # Handle any orphaned nodes (cycles, etc.) that were not visited
        remaining = [e for e in employees if str(e.id) not in visited]
        if remaining:
            remaining.sort(key=sort_key)
            for r in remaining:
                dfs(r, 0)

        return result

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



