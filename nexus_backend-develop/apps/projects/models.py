import uuid
import datetime

from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel
from packages.workflow.field import StateField


class Client(BaseModel):
    name             = models.CharField(max_length=200, unique=True)
    code             = models.CharField(max_length=50, blank=True, default="")
    industry         = models.CharField(max_length=100, blank=True, default="")
    contact_email    = models.EmailField(blank=True, default="")
    contact_person   = models.CharField(max_length=100, blank=True, default="")
    phone            = models.CharField(max_length=30, blank=True, default="")
    address          = models.TextField(blank=True, default="")
    pan_number       = models.CharField(max_length=10, blank=True, default="", db_index=True)
    gst_number       = models.CharField(max_length=15, blank=True, default="", db_index=True)
    category         = models.ForeignKey(
        "master.ClientCategory",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="clients",
    )
    latitude         = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude        = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    formatted_address = models.CharField(max_length=500, blank=True, default="")
    is_active        = models.BooleanField(default=True)

    class Meta:
        db_table = "project_client"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Project(BaseModel):
    name = models.CharField(max_length=300)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default="")
    client = models.ForeignKey(
        Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects"
    )
    business_type = models.ForeignKey(
        "master.BusinessType",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="projects",
    )
    billing_type = models.ForeignKey(
        "master.BillingType",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="projects",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    budget = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Total contract value (INR). Milestones and invoices cannot exceed this.",
    )
    manager = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_projects",
    )
    workflow_state = StateField(related_name="projects")

    class Meta:
        db_table = "project_project"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @classmethod
    def generate_code(cls, business_type=None) -> str:
        """Return the next available project code, e.g. PRJ-260001."""
        prefix = "PRJ"
        if business_type and getattr(business_type, "prefix", ""):
            prefix = business_type.prefix.upper()
        yy = datetime.date.today().strftime("%y")
        pattern = f"{prefix}-{yy}"
        count = cls.objects.filter(code__startswith=pattern).count() + 1
        code = f"{pattern}{count:04d}"
        while cls.objects.filter(code=code).exists():
            count += 1
            code = f"{pattern}{count:04d}"
        return code

    @property
    def logged_hours(self):
        from django.db.models import Sum
        from apps.workitems.models import WorkLog
        return WorkLog.objects.filter(
            ticket__project=self, is_deleted=False
        ).aggregate(total=Sum("hours"))["total"] or 0

    @property
    def remaining_hours(self):
        return max(0, float(self.estimated_hours) - float(self.logged_hours))


class ProjectHistory(models.Model):
    """Immutable audit record of every project create / update."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=20, default="update")   # "create" | "update"
    changes = models.JSONField(default=dict)
    # changes format: {"Field Label": {"old": "old value", "new": "new value"}, ...}
    changed_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="project_history_entries",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_history"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.project.code} [{self.action}] at {self.changed_at:%Y-%m-%d %H:%M}"
