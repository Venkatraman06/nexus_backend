from rest_framework.generics import ListAPIView
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from .models import (
    Designation, Department, Location, Grade, EmploymentType,
    ShiftCategory, RateCard, ClientCategory, BusinessType, BillingType,
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
)


class DropdownView(ListAPIView):
    """Base class for open dropdown lists (active items only, no pagination)."""
    pagination_class = None

    def get_queryset(self):
        return self.queryset.filter(is_active=True)


_HRMS_MASTER_PERMS = {
    "list": "pmt.master.hrms.view",
    "retrieve": "pmt.master.hrms.view",
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
