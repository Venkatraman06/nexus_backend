from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.viewsets import BaseModelViewSet
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
import logging

from .models import Employee, EmployeeCertificate
from .serializers import (
    EmployeeListSerializer, EmployeeDetailSerializer,
    EmployeeUpdateSerializer, EmployeeCreateSerializer,
)
from .services import KeycloakSyncService
from .group_config import resolve_group_flags

logger = logging.getLogger(__name__)

KEYCLOAK_DEFAULT_GROUPS = ["hr", "des-admin", "admin", "officer", "employee", "finance team"]

from apps.common.permissions_catalog import get_all_pmt_permission_names_safe


def _assign_keycloak_group(admin, keycloak_user_id: str, group_name: str):
    """Add a Keycloak user to a group by name. Silently skips if group not found."""
    try:
        groups = admin.get_groups()
        target = next((g for g in groups if g["name"].lower() == group_name.lower()), None)
        if target:
            admin.group_user_add(keycloak_user_id, target["id"])
    except Exception as exc:
        logger.warning("_assign_keycloak_group failed (%s → %s): %s", keycloak_user_id, group_name, exc)


class KeycloakGroupsView(APIView):
    """Return available Keycloak groups for the employee group dropdown."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from apps.accounts.auth_views import _kc_admin
            admin = _kc_admin()
            groups = admin.get_groups()
            names = sorted(g["name"] for g in groups if g.get("name"))
            if not names:
                names = KEYCLOAK_DEFAULT_GROUPS
        except Exception as exc:
            logger.warning("Could not fetch Keycloak groups: %s", exc)
            names = KEYCLOAK_DEFAULT_GROUPS
        return Response({"groups": names})


class EmployeeViewSet(BaseModelViewSet):
    queryset = Employee.objects.filter(is_deleted=False).select_related(
        "designation_ref", "department_ref", "location", "grade", "employment_type"
    )
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    search_fields = ["first_name", "last_name", "email", "username", "employee_code"]
    ordering_fields = ["first_name", "last_name", "created_at", "status", "employee_code"]
    ordering = ["first_name"]
    filterset_fields = ["status", "is_pmo", "is_manager", "shift_applicable", "keycloak_group"]

    PERMISSION_MAP = {
        "list":           "pmt.hrms.employee.view",
        "retrieve":       "pmt.hrms.employee.view",
        "create":         "pmt.hrms.employee.create",
        "update":         "pmt.hrms.employee.update",
        "partial_update": "pmt.hrms.employee.update",
        "destroy":        "pmt.hrms.employee.delete",
    }

    def get_serializer_class(self):
        if self.action == "create":
            return EmployeeCreateSerializer
        if self.action == "retrieve":
            return EmployeeDetailSerializer
        if self.action in ["update", "partial_update"]:
            return EmployeeUpdateSerializer
        return EmployeeListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Auto-generate employee code
        employee_code = Employee.objects.generate_employee_code()

        # Derive username from employee_code if not provided
        username = data.get("username") or employee_code.lower()

        # Try to create Keycloak user (non-blocking)
        keycloak_id = None
        try:
            from apps.accounts.auth_views import _kc_admin
            admin = _kc_admin()
            first = data.get("first_name", "")
            last = data.get("last_name", "")
            email = data.get("email", "")
            new_id = admin.create_user({
                "username": username,
                "email": email,
                "firstName": first,
                "lastName": last,
                "enabled": True,
                "credentials": [{"type": "password", "value": employee_code, "temporary": True}],
            })
            keycloak_id = new_id

            # Assign to Keycloak group if provided
            group_name = data.get("keycloak_group", "")
            if group_name and keycloak_id:
                _assign_keycloak_group(admin, keycloak_id, group_name)
        except Exception as exc:
            logger.warning("Keycloak user creation failed for %s: %s", username, exc)

        # Derive is_pmo / is_manager from keycloak_group via config
        group_flags = resolve_group_flags(data.get("keycloak_group", ""))

        emp = Employee.objects.create(
            username=username,
            employee_code=employee_code,
            keycloak_id=keycloak_id,
            **group_flags,
            **{k: v for k, v in data.items() if k not in ("username",)},
        )

        # Send welcome / onboarding email with set-password link
        if keycloak_id and emp.email:
            try:
                from django.conf import settings
                from apps.accounts.password_reset_service import create_onboard_token
                from apps.accounts.email_service import send_welcome_onboard_email

                token = create_onboard_token(str(emp.id), keycloak_id)
                reset_link = f"{settings.FRONTEND_APP_URL}/set-password?token={token}"
                send_welcome_onboard_email(
                    to=emp.email,
                    full_name=emp.full_name or username,
                    username=username,
                    reset_link=reset_link,
                )
            except Exception as exc:
                logger.warning("Onboarding email failed for %s: %s", username, exc)

        from apps.notifications.constants import EventType, ReferenceType
        from apps.notifications.publisher import publish_event
        publish_event(
            EventType.EMPLOYEE_ONBOARDED,
            ReferenceType.EMPLOYEE,
            str(emp.id),
            payload={
                "employee_name": emp.full_name or username,
                "employee_code": employee_code,
                "designation": emp.designation_ref.name if emp.designation_ref_id else "",
            },
            actor_id=str(request.user.id),
            async_delivery=True,
        )

        out = EmployeeDetailSerializer(emp, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        # If keycloak_group is being changed, inject derived flags into the request data
        group_name = request.data.get("keycloak_group")
        if group_name is not None:
            data = request.data.copy()
            data.update(resolve_group_flags(group_name))
            request._full_data = data

        response = super().partial_update(request, *args, **kwargs)

        # Sync group membership in Keycloak (non-blocking)
        if group_name:
            instance = self.get_object()
            if instance.keycloak_id:
                try:
                    from apps.accounts.auth_views import _kc_admin
                    _assign_keycloak_group(_kc_admin(), instance.keycloak_id, group_name)
                except Exception as exc:
                    logger.warning("Keycloak group update failed for %s: %s", instance.username, exc)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        # Exclude system/admin accounts that have no employee code
        qs = super().get_queryset().exclude(employee_code="")
        if self.request.query_params.get("dropdown"):
            return qs.filter(is_active=True)
        return qs


class EmployeeSimpleDropdownView(APIView):
    """Return a minimal employee list for dropdowns. Requires authentication only."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Employee.objects
            .filter(is_active=True, is_deleted=False)
            .exclude(employee_code="")
            .select_related("designation_ref")
            .order_by("first_name")
        )
        data = [
            {
                "id": str(e.id),
                "keycloak_id": str(e.keycloak_id) if e.keycloak_id else None,
                "email": e.email,
                "full_name": e.full_name,
                "employee_code": e.employee_code,
                "designation_name": e.designation_ref.name if e.designation_ref else e.designation or None,
            }
            for e in qs
        ]
        return Response(data)


@extend_schema(tags=["auth"], responses={200: OpenApiResponse(description="Keycloak employee sync result")})
class EmployeeSyncView(APIView):
    """Sync employees from Keycloak. Requires pmt.hrms.employee.sync permission."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]

    PERMISSION_MAP = {"post": "pmt.hrms.employee.sync"}

    def has_permission(self, request, view):
        perms: list = getattr(request, "user_permissions", [])
        return (
            request.user.is_staff
            or "pmt.hrms.employee.sync" in perms
        )

    def post(self, request):
        try:
            result = KeycloakSyncService().sync_all()
            return Response({"message": "Sync completed.", "result": result})
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeCertificateViewSet(BaseModelViewSet):
    queryset = EmployeeCertificate.objects.select_related("employee")
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["employee"]
    ordering = ["-created_at"]

    PERMISSION_MAP = {
        "list":           "pmt.hrms.employee.view",
        "retrieve":       "pmt.hrms.employee.view",
        "create":         "pmt.hrms.employee.update",
        "update":         "pmt.hrms.employee.update",
        "partial_update": "pmt.hrms.employee.update",
        "destroy":        "pmt.hrms.employee.update",
    }

    def get_queryset(self):
        # EmployeeCertificate has no is_deleted field — skip the base filter
        return EmployeeCertificate.objects.select_related("employee")

    def get_serializer_class(self):
        from .serializers import EmployeeCertificateSerializer
        return EmployeeCertificateSerializer


class MeView(APIView):
    """
    GET  /users/me/  — current user profile + permissions
    PATCH /users/me/ — update first_name, last_name, phone_number, bio, profile_picture
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        me = request.user

        # Build profile
        desig_name = ""
        dept_name  = ""
        try:
            desig_name = me.designation_ref.name if me.designation_ref_id else (me.designation or "")
            dept_name  = me.department_ref.name  if me.department_ref_id  else (me.department  or "")
        except Exception:
            pass

        profile_pic_url = None
        try:
            profile_pic_url = me.profile_picture.url if me.profile_picture else None
        except Exception:
            pass

        # Resolve permissions
        is_superuser = getattr(me, "is_superuser", False)
        is_staff     = getattr(me, "is_staff",     False)
        is_pmo       = getattr(me, "is_pmo",       False)

        all_pmt = get_all_pmt_permission_names_safe()
        all_pmt_set = set(all_pmt)

        if is_superuser or is_staff:
            effective_perms = list(all_pmt)
        else:
            kc_perms: list = getattr(request, "user_permissions", [])
            effective_perms = [p for p in kc_perms if p in all_pmt_set]
            # Every authenticated employee always gets their personal dashboard
            if "pmt.dashboard.own.view" not in effective_perms:
                effective_perms.append("pmt.dashboard.own.view")

        return Response({
            "id":               str(me.id),
            "username":         me.username,
            "email":            me.email,
            "full_name":        me.full_name,
            "employee_code":    me.employee_code,
            "designation":      desig_name,
            "department":       dept_name,
            "grade":            me.grade.name if me.grade_id else "",
            "keycloak_group":   me.keycloak_group,
            "joining_date":     str(me.joining_date) if me.joining_date else None,
            "profile_picture_url": profile_pic_url,
            "is_pmo":           is_pmo,
            "is_manager":       getattr(me, "is_manager", False),
            "is_staff":         is_staff,
            "is_superuser":     is_superuser,
            "permissions":      effective_perms,
            "phone_number":     getattr(me, "phone_number", "") or "",
            "bio":              getattr(me, "bio", "") or "",
            "last_login":       me.last_login.isoformat() if me.last_login else None,
        })

    @extend_schema(tags=["users"])
    def patch(self, request):
        from apps.common.validators import validate_phone
        from rest_framework.exceptions import ValidationError

        me = request.user
        allowed = {"first_name", "last_name", "phone_number", "bio", "profile_picture"}
        update_fields = []
        for field in allowed:
            if field in request.data:
                value = request.data[field]
                if field == "phone_number":
                    try:
                        value = validate_phone(value, "Phone number")
                    except ValidationError as exc:
                        return Response(exc.detail, status=400)
                setattr(me, field, value)
                update_fields.append(field)
        if "profile_picture" in request.FILES:
            me.profile_picture = request.FILES["profile_picture"]
            if "profile_picture" not in update_fields:
                update_fields.append("profile_picture")
        if update_fields:
            me.save(update_fields=update_fields)
        profile_pic_url = None
        try:
            profile_pic_url = me.profile_picture.url if me.profile_picture else None
        except Exception:
            pass
        return Response({
            "detail": "Profile updated.",
            "full_name": me.full_name,
            "profile_picture_url": profile_pic_url,
        })


class OrgTreeView(APIView):
    """
    GET /employees/org-tree/
    Returns flat list of all active employees with manager_id for building
    the org chart on the frontend.
    GET /employees/org-tree/?root=<employee_id>
    Returns subtree rooted at given employee.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        root_id = request.query_params.get("root")
        qs = Employee.objects.filter(
            is_active=True, is_deleted=False
        ).select_related(
            "manager", "designation_ref", "department_ref"
        ).only(
            "id", "first_name", "last_name", "employee_code",
            "manager_id", "designation_ref_id", "department_ref_id",
            "designation", "department", "profile_picture",
        )

        def pic_url(emp):
            try:
                return emp.profile_picture.url if emp.profile_picture else None
            except Exception:
                return None

        nodes = [
            {
                "id":           str(e.id),
                "name":         e.full_name,
                "employee_code": e.employee_code,
                "designation":  e.designation_ref.name if e.designation_ref_id else (e.designation or ""),
                "department":   e.department_ref.name  if e.department_ref_id  else (e.department  or ""),
                "manager_id":   str(e.manager_id) if e.manager_id else None,
                "avatar":       pic_url(e),
            }
            for e in qs
        ]

        parent_node = None

        if root_id:
            # Build downward subtree from root_id
            id_set = {root_id}
            changed = True
            while changed:
                changed = False
                for n in nodes:
                    if n["manager_id"] in id_set and n["id"] not in id_set:
                        id_set.add(n["id"])
                        changed = True
            subtree = [n for n in nodes if n["id"] in id_set]

            # Also resolve the immediate parent for focused/context view
            root_node = next((n for n in nodes if n["id"] == root_id), None)
            if root_node and root_node["manager_id"]:
                parent_node = next(
                    (n for n in nodes if n["id"] == root_node["manager_id"]), None
                )

            nodes = subtree

        return Response({"nodes": nodes, "parent": parent_node})


class EmployeeSearchView(APIView):
    """
    GET /employees/search/?q=<query>
    Returns up to 10 employees matching name, code, or email.
    Used by the global search bar for the employee preview popup.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .serializers import EmployeeSearchSerializer
        from django.db.models import Q

        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response([])

        qs = (
            Employee.objects
            .filter(is_deleted=False)
            .select_related(
                "designation_ref", "department_ref", "location",
                "grade", "employment_type", "shift_category", "manager",
            )
            .filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q)  |
                Q(employee_code__icontains=q) |
                Q(email__icontains=q)
            )[:10]
        )
        return Response(EmployeeSearchSerializer(qs, many=True).data)





