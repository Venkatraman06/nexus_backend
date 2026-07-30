from rest_framework.generics import ListAPIView
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from .models import (
    Designation, Department, Location, Grade, EmploymentType,
    ShiftCategory, RateCard, ClientCategory, BusinessType, BillingType,
    FollowupTypeMaster,
)
from .serializers import (
    DesignationSerializer, DesignationDropdownSerializer,
    DepartmentSerializer, DepartmentDropdownSerializer,
    LocationSerializer, LocationDropdownSerializer,
    GradeSerializer, GradeDropdownSerializer,
    EmploymentTypeSerializer, EmploymentTypeDropdownSerializer,
    ShiftCategorySerializer, ShiftCategoryDropdownSerializer,
    RateCardSerializer,
    ClientCategorySerializer, ClientCategoryDropdownSerializer,
    BusinessTypeSerializer, BusinessTypeDropdownSerializer,
    BillingTypeSerializer, BillingTypeDropdownSerializer,
    FollowupTypeMasterSerializer, FollowupTypeDropdownSerializer,
)


class DropdownView(ListAPIView):
    """Base class for open dropdown lists (active items only, no pagination)."""
    pagination_class = None

    def get_queryset(self):
        return self.queryset.filter(is_active=True)


_HRMS_MASTER_PERMS = {
    "list":           "pmt.hrms.attendance.view",  # ← allow HR to list
    "retrieve":       "pmt.hrms.attendance.view",
    "create": "pmt.master.hrms.create",
    "update": "pmt.master.hrms.update",
    "partial_update": "pmt.master.hrms.update",
    "destroy": "pmt.master.hrms.delete",
}

_CLIENT_MASTER_PERMS = {
    "list": "pmt.master.client.view",
    "retrieve": "pmt.master.client.view",
    "create": "pmt.master.client.create",
    "update": "pmt.master.client.update",
    "partial_update": "pmt.master.client.update",
    "destroy": "pmt.master.client.delete",
}

_PROJECT_MASTER_PERMS = {
    "list": "pmt.master.project.view",
    "retrieve": "pmt.master.project.view",
    "create": "pmt.master.project.create",
    "update": "pmt.master.project.update",
    "partial_update": "pmt.master.project.update",
    "destroy": "pmt.master.project.delete",
}


class DesignationViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _HRMS_MASTER_PERMS
    serializer_class = DesignationSerializer
    queryset = Designation.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class DepartmentViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _HRMS_MASTER_PERMS
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class LocationViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _HRMS_MASTER_PERMS
    serializer_class = LocationSerializer
    queryset = Location.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name", "city", "state"]


class GradeViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _HRMS_MASTER_PERMS
    serializer_class = GradeSerializer
    queryset = Grade.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class EmploymentTypeViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _HRMS_MASTER_PERMS
    serializer_class = EmploymentTypeSerializer
    queryset = EmploymentType.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class ShiftCategoryViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _HRMS_MASTER_PERMS
    serializer_class = ShiftCategorySerializer
    queryset = ShiftCategory.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name"]


# ── Dropdown views ──────────────────────────────────────────────────────────────

class DesignationDropdownView(DropdownView):
    queryset = Designation.objects.all()
    serializer_class = DesignationDropdownSerializer


class DepartmentDropdownView(DropdownView):
    queryset = Department.objects.all()
    serializer_class = DepartmentDropdownSerializer


class LocationDropdownView(DropdownView):
    queryset = Location.objects.all()
    serializer_class = LocationDropdownSerializer


class GradeDropdownView(DropdownView):
    queryset = Grade.objects.all()
    serializer_class = GradeDropdownSerializer


class EmploymentTypeDropdownView(DropdownView):
    queryset = EmploymentType.objects.all()
    serializer_class = EmploymentTypeDropdownSerializer


class ShiftCategoryDropdownView(DropdownView):
    queryset = ShiftCategory.objects.all()
    serializer_class = ShiftCategoryDropdownSerializer


class ClientCategoryViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _CLIENT_MASTER_PERMS
    serializer_class = ClientCategorySerializer
    queryset = ClientCategory.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class ClientCategoryDropdownView(DropdownView):
    queryset = ClientCategory.objects.all()
    serializer_class = ClientCategoryDropdownSerializer


class RateCardViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _HRMS_MASTER_PERMS
    serializer_class = RateCardSerializer
    queryset = RateCard.objects.select_related("designation_ref", "department_ref").all()
    filterset_fields = ["is_active", "designation_ref", "department_ref"]
    search_fields    = ["designation_ref__name", "department_ref__name"]


class BusinessTypeViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _PROJECT_MASTER_PERMS
    serializer_class = BusinessTypeSerializer
    queryset = BusinessType.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name", "prefix"]


class BusinessTypeDropdownView(DropdownView):
    queryset = BusinessType.objects.all()
    serializer_class = BusinessTypeDropdownSerializer


class BillingTypeViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _PROJECT_MASTER_PERMS
    serializer_class = BillingTypeSerializer
    queryset = BillingType.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class BillingTypeDropdownView(DropdownView):
    queryset = BillingType.objects.all()
    serializer_class = BillingTypeDropdownSerializer


_FOLLOWUP_MASTER_PERMS = {
    "list":           None,
    "retrieve":       None,
    "create":         None,
    "update":         "pmt.master.project.update",
    "partial_update": "pmt.master.project.update",
    "destroy":        "pmt.master.project.delete",
}


class FollowupTypeViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = _FOLLOWUP_MASTER_PERMS
    serializer_class = FollowupTypeMasterSerializer
    queryset = FollowupTypeMaster.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class FollowupTypeDropdownView(DropdownView):
    queryset = FollowupTypeMaster.objects.all()
    serializer_class = FollowupTypeDropdownSerializer
from .models import LeaveType
from apps.attendance.models import LeaveBalance
from apps.attendance.models import LeavePolicyRule
from .serializers import LeaveTypeSerializer, LeavePolicyRuleSerializer
from apps.accounts.models import Employee
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import LeaveTypeSerializer, LeavePolicyRuleSerializer


class LeaveTypeViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP     = _HRMS_MASTER_PERMS
    serializer_class   = LeaveTypeSerializer
    queryset           = LeaveType.objects.all()
    filterset_fields   = ["is_paid", "is_active"]
    search_fields      = ["name", "code"]


class LeavePolicyRuleViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP     = _HRMS_MASTER_PERMS
    serializer_class   = LeavePolicyRuleSerializer
    queryset           = LeavePolicyRule.objects.select_related("leave_type").all()
    filterset_fields   = ["effective_from", "leave_type"]

    @action(detail=True, methods=["post"], url_path="allocate")
    def allocate(self, request, pk=None):
        rule = self.get_object()
        year = int(request.data.get("year", rule.effective_from))
        employees = Employee.objects.filter(is_active=True, is_deleted=False)
        created = updated = 0
        for emp in employees:
            obj, was_created = LeaveBalance.objects.get_or_create(
                employee=emp, leave_type=rule.leave_type, year=year,
                defaults={"total_days": rule.total_days, "used_days": 0},
            )
            if was_created:
                created += 1
            else:
                updated += 1
        return Response({"year": year, "created": created, "updated": updated, "total_employees": employees.count()})


class LeaveBalanceAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        year        = request.data.get("year")
        assignments = request.data.get("assignments", [])
        if not year or not assignments:
            return Response({"detail": "year and assignments are required."}, status=status.HTTP_400_BAD_REQUEST)
        results = []
        for a in assignments:
            try:
                emp  = Employee.objects.get(id=a["employee_id"], is_deleted=False)
                lt   = LeaveType.objects.get(id=a["leave_type_id"])
                obj, created = LeaveBalance.objects.update_or_create(
                    employee=emp, leave_type=lt, year=int(year),
                    defaults={"total_days": a["total_days"]},
                )
                results.append({"employee_name": emp.full_name, "leave_type": lt.name, "created": created})
            except Exception as e:
                results.append({"error": str(e), "data": a})
        return Response({"assigned": len(results), "results": results})


from .models import Holiday
from .serializers import HolidaySerializer


class CreateMyLeaveTypeView(APIView):
    """
    Self-service: an employee can create a custom leave type and auto-assign
    it to themselves with a default balance of `max_days` days.
    POST /master/leave/my-types/  { name, code, max_days, is_paid, color }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from decimal import Decimal
        from datetime import date
        from django.db import transaction

        data = request.data
        name     = data.get("name", "").strip()
        code     = data.get("code", "").strip().upper()
        max_days = int(data.get("max_days", 0) or 0)
        is_paid  = bool(data.get("is_paid", True))
        color    = data.get("color", "#1677ff").strip()

        if not name or not code:
            return Response({"detail": "Name and code are required."}, status=status.HTTP_400_BAD_REQUEST)

        if len(code) > 20:
            return Response({"detail": "Code must be 20 characters or fewer."}, status=status.HTTP_400_BAD_REQUEST)

        if LeaveType.objects.filter(code=code).exists():
            return Response({"detail": f"A leave type with code '{code}' already exists."}, status=status.HTTP_400_BAD_REQUEST)

        if LeaveType.objects.filter(name__iexact=name).exists():
            return Response({"detail": f"A leave type named '{name}' already exists."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            lt = LeaveType.objects.create(
                name=name,
                code=code,
                max_days=max_days,
                is_paid=is_paid,
                color=color,
                is_active=True,
            )

            # Create a policy rule for the current year
            year = date.today().year
            total = max_days if max_days > 0 else 10  # default 10 if unlimited
            LeavePolicyRule.objects.create(
                leave_type=lt,
                total_days=Decimal(str(total)),
                carry_forward=False,
                carry_forward_limit=0,
                applicable_to="ALL",
                effective_from=year,
                effective_to=year,
                loss_of_pay_after=0,
                auto_allocate=True,
                notes=f"Self-created by {request.user.full_name}",
            )

            # Auto-assign balance to the current user
            LeaveBalance.objects.get_or_create(
                employee=request.user,
                leave_type=lt,
                year=year,
                defaults={"total_days": Decimal(str(total)), "used_days": 0},
            )

        return Response(
            LeaveTypeSerializer(lt).data,
            status=status.HTTP_201_CREATED,
        )


class HolidayViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP     = _HRMS_MASTER_PERMS
    serializer_class   = HolidaySerializer
    queryset           = Holiday.objects.all()
    filterset_fields   = ["year", "holiday_type", "is_active"]
    search_fields      = ["name"]


class WFHRequestAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.attendance.models import WFHRequest  # adjust import if needed
        status_filter = request.query_params.get("status")
        qs = WFHRequest.objects.filter(is_deleted=False).select_related("employee")
        if status_filter:
            qs = qs.filter(status=status_filter)
        pending_count = WFHRequest.objects.filter(is_deleted=False, status="PENDING").count()
        data = [
            {
                "id":             str(r.id),
                "employee_name":  r.employee.full_name,
                "employee_code":  r.employee.employee_code,
                "department":     r.employee.department_ref.name if r.employee.department_ref_id else "",
                "requested_date": str(r.requested_date),
                "reason":         r.reason,
                "status":         r.status,
                "rejection_note": getattr(r, "rejection_note", ""),
                "created_at":     str(r.created_at),
            }
            for r in qs.order_by("-created_at")
        ]
        return Response({"results": data, "pending_count": pending_count})


from .models import ReimbursementConfig
from .serializers import ReimbursementConfigSerializer

from apps.common.viewsets import BaseModelViewSet

class ReimbursementConfigViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = ReimbursementConfigSerializer
    queryset           = ReimbursementConfig.objects.select_related("reviewer", "approver").all()
    filterset_fields   = ["is_active"]
    search_fields      = ["name"]

    def get_queryset(self):
        return self.queryset

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)