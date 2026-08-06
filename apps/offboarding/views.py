from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from .models import (
    OffboardingRecord, OffboardingPreference, ClearanceItem,
    ExitInterview, OffboardingDocument, OffboardingWorkflowStage,
)
from .serializers import (
    OffboardingRecordSerializer, OffboardingRecordListSerializer,
    OffboardingPreferenceSerializer, ClearanceItemSerializer,
    ExitInterviewSerializer, OffboardingDocumentSerializer,
    OffboardingWorkflowStageSerializer,
)

OFFBOARDING_VIEW   = "pmt.hrms.offboarding.view"
OFFBOARDING_CREATE = "pmt.hrms.offboarding.create"
OFFBOARDING_UPDATE = "pmt.hrms.offboarding.update"
OFFBOARDING_DELETE = "pmt.hrms.offboarding.delete"


def _has_perm(request, perm: str) -> bool:
    if request.user.is_staff or getattr(request.user, "is_superuser", False):
        return True
    # Check Keycloak/JWT injected permissions list
    user_perms = getattr(request, "user_permissions", [])
    if perm in user_perms:
        return True
    # Also check the user model permissions for Django-based auth
    try:
        if request.user.has_perm(perm):
            return True
    except Exception:
        pass
    return False


def _require_create(request):
    return _has_perm(request, OFFBOARDING_CREATE)


# ── Offboarding Records ────────────────────────────────────────────────────────

class OffboardingRecordListCreateView(APIView):
    # Only require authentication — permission check is done manually inside
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["offboarding"])
    def get(self, request):
        qs = OffboardingRecord.objects.filter(is_deleted=False).select_related("employee", "initiated_by")

        has_view_perm = _has_perm(request, OFFBOARDING_VIEW)

        if has_view_perm:
            # HR/admin: can filter by status and employee
            status_filter = request.query_params.get("status")
            if status_filter:
                qs = qs.filter(status=status_filter)
            employee_id = request.query_params.get("employee")
            if employee_id:
                qs = qs.filter(employee_id=employee_id)
        else:
            # Regular employee: only their own records
            qs = qs.filter(employee=request.user)
            employee_id = request.query_params.get("employee")
            if employee_id:
                qs = qs.filter(employee_id=employee_id)

        return Response(OffboardingRecordListSerializer(qs, many=True).data)

    @extend_schema(tags=["offboarding"])
    def post(self, request):
        # Any authenticated employee can submit their own resignation
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

        # If employee field not provided, default to the requesting user
        if not data.get("employee"):
            data["employee"] = str(request.user.id)

        # Prevent employees from submitting on behalf of others (unless HR/admin)
        if not _has_perm(request, OFFBOARDING_CREATE):
            data["employee"] = str(request.user.id)

        serializer = OffboardingRecordSerializer(data=data)
        if serializer.is_valid():
            serializer.save(
                initiated_by=request.user,
                created_by=request.user,
                updated_by=request.user,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OffboardingRecordDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_object(self, pk):
        try:
            return OffboardingRecord.objects.select_related("employee", "initiated_by").get(
                pk=pk, is_deleted=False
            )
        except OffboardingRecord.DoesNotExist:
            return None

    @extend_schema(tags=["offboarding"])
    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        # Allow HR or the employee themselves
        if not _has_perm(request, OFFBOARDING_VIEW) and obj.employee_id != request.user.id:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        return Response(OffboardingRecordSerializer(obj).data)

    @extend_schema(tags=["offboarding"])
    def patch(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        # Only HR/admin can update status; employee can update their own basic fields
        if not _has_perm(request, OFFBOARDING_CREATE) and obj.employee_id != request.user.id:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        serializer = OffboardingRecordSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["offboarding"])
    def delete(self, request, pk):
        if not _has_perm(request, OFFBOARDING_DELETE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Preference (one per offboarding) ──────────────────────────────────────────

class OffboardingPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["offboarding"])
    def get(self, request, offboarding_id):
        try:
            record = OffboardingRecord.objects.get(pk=offboarding_id, is_deleted=False)
        except OffboardingRecord.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _has_perm(request, OFFBOARDING_VIEW) and record.employee_id != request.user.id:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            obj = OffboardingPreference.objects.get(offboarding_id=offboarding_id, is_deleted=False)
        except OffboardingPreference.DoesNotExist:
            return Response(None)
        return Response(OffboardingPreferenceSerializer(obj).data)

    @extend_schema(tags=["offboarding"])
    def put(self, request, offboarding_id):
        try:
            record = OffboardingRecord.objects.get(pk=offboarding_id, is_deleted=False)
        except OffboardingRecord.DoesNotExist:
            return Response({"detail": "Offboarding record not found."}, status=status.HTTP_404_NOT_FOUND)

        is_owner = record.employee_id == request.user.id
        if not (_require_create(request) or is_owner):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        obj = OffboardingPreference.objects.filter(offboarding=record, is_deleted=False).first()
        serializer = OffboardingPreferenceSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            if obj:
                serializer.save(updated_by=request.user)
            else:
                serializer.save(offboarding=record, created_by=request.user, updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Clearance Items ────────────────────────────────────────────────────────────

class ClearanceItemListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = OFFBOARDING_VIEW

    @extend_schema(tags=["offboarding"])
    def get(self, request, offboarding_id):
        qs = ClearanceItem.objects.filter(offboarding_id=offboarding_id, is_deleted=False)
        return Response(ClearanceItemSerializer(qs, many=True).data)

    @extend_schema(tags=["offboarding"])
    def post(self, request, offboarding_id):
        if not _require_create(request):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        data = request.data.copy()
        data["offboarding"] = offboarding_id
        serializer = ClearanceItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClearanceItemDetailView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = OFFBOARDING_VIEW

    def _get_object(self, pk):
        try:
            return ClearanceItem.objects.get(pk=pk, is_deleted=False)
        except ClearanceItem.DoesNotExist:
            return None

    @extend_schema(tags=["offboarding"])
    def patch(self, request, pk):
        if not _require_create(request):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        if data.get("is_cleared") and not obj.cleared_by_id:
            data["cleared_by"] = request.user.id
        serializer = ClearanceItemSerializer(obj, data=data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["offboarding"])
    def delete(self, request, pk):
        if not _has_perm(request, OFFBOARDING_DELETE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Exit Interview (one per offboarding) ──────────────────────────────────────

class ExitInterviewView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = OFFBOARDING_VIEW

    @extend_schema(tags=["offboarding"])
    def get(self, request, offboarding_id):
        try:
            obj = ExitInterview.objects.get(offboarding_id=offboarding_id, is_deleted=False)
        except ExitInterview.DoesNotExist:
            return Response(None)
        return Response(ExitInterviewSerializer(obj).data)

    @extend_schema(tags=["offboarding"])
    def put(self, request, offboarding_id):
        if not _require_create(request):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            record = OffboardingRecord.objects.get(pk=offboarding_id, is_deleted=False)
        except OffboardingRecord.DoesNotExist:
            return Response({"detail": "Offboarding record not found."}, status=status.HTTP_404_NOT_FOUND)

        obj = ExitInterview.objects.filter(offboarding=record, is_deleted=False).first()
        serializer = ExitInterviewSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            if obj:
                serializer.save(updated_by=request.user)
            else:
                serializer.save(offboarding=record, created_by=request.user, updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Documents ──────────────────────────────────────────────────────────────────

class OffboardingDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = OFFBOARDING_VIEW
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(tags=["offboarding"])
    def get(self, request, offboarding_id):
        qs = OffboardingDocument.objects.filter(offboarding_id=offboarding_id, is_deleted=False)
        return Response(OffboardingDocumentSerializer(qs, many=True).data)

    @extend_schema(tags=["offboarding"])
    def post(self, request, offboarding_id):
        if not _require_create(request):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        data = request.data.copy()
        data["offboarding"] = offboarding_id
        serializer = OffboardingDocumentSerializer(data=data)
        if serializer.is_valid():
            serializer.save(uploaded_by=request.user, created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OffboardingDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = OFFBOARDING_VIEW

    @extend_schema(tags=["offboarding"])
    def delete(self, request, pk):
        if not _has_perm(request, OFFBOARDING_DELETE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            obj = OffboardingDocument.objects.get(pk=pk, is_deleted=False)
        except OffboardingDocument.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Workflow Stages ────────────────────────────────────────────────────────────

class OffboardingWorkflowStageListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = OFFBOARDING_VIEW

    @extend_schema(tags=["offboarding"])
    def get(self, request, offboarding_id):
        qs = OffboardingWorkflowStage.objects.filter(offboarding_id=offboarding_id, is_deleted=False)
        return Response(OffboardingWorkflowStageSerializer(qs, many=True).data)

    @extend_schema(tags=["offboarding"])
    def post(self, request, offboarding_id):
        if not _require_create(request):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        data = request.data.copy()
        data["offboarding"] = offboarding_id
        serializer = OffboardingWorkflowStageSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OffboardingWorkflowStageDetailView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = OFFBOARDING_VIEW

    def _get_object(self, pk):
        try:
            return OffboardingWorkflowStage.objects.get(pk=pk, is_deleted=False)
        except OffboardingWorkflowStage.DoesNotExist:
            return None

    @extend_schema(tags=["offboarding"])
    def patch(self, request, pk):
        if not _require_create(request):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = OffboardingWorkflowStageSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["offboarding"])
    def delete(self, request, pk):
        if not _has_perm(request, OFFBOARDING_DELETE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Clearance Owner Notifications ──────────────────────────────────────────────

class ClearanceOwnerNotifyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["offboarding"])
    def post(self, request):
        if not _has_perm(request, OFFBOARDING_VIEW):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        owner_id = request.data.get('owner_id')
        if not owner_id:
            return Response({"detail": "owner_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data

        # Attempt to dispatch via the DomainEvent publisher first
        try:
            from apps.notifications.events import DomainEvent
            from apps.notifications.publisher import publish_event

            event = DomainEvent(
                event_type='offboarding.clearance_assigned',
                reference_type='clearance',
                reference_id=str(data.get('offboarding_id', '')),
                payload={
                    'clearance_title': data.get('clearance_title', ''),
                    'employee_name': data.get('employee_name', ''),
                    'items': data.get('items', []),
                    'owner_id': str(owner_id),
                },
                actor_id=str(request.user.id),
                recipient_ids=[str(owner_id)],
                action_url='/employees/offboarding',
            )
            publish_event(event)
            return Response({'detail': 'Notification sent.'}, status=status.HTTP_200_OK)
        except Exception:
            pass

        # Fallback: create the Notification record directly
        try:
            from apps.notifications.models import Notification
            from apps.notifications.constants import NotificationChannel

            Notification.objects.create(
                recipient_id=owner_id,
                actor=request.user,
                event_type='offboarding.clearance_assigned',
                title=f'Clearance Task: {data.get("clearance_title", "")}',
                message=(
                    f'You have been assigned as owner for clearance of '
                    f'{data.get("employee_name", "")}. Please complete the checklist.'
                ),
                reference_type='clearance',
                reference_id=str(data.get('offboarding_id', '')),
                channel=NotificationChannel.IN_APP,
                severity='info',
                action_url='/employees/offboarding',
                metadata={
                    'clearance_title': data.get('clearance_title', ''),
                    'employee_name': data.get('employee_name', ''),
                    'items': data.get('items', []),
                    'offboarding_id': str(data.get('offboarding_id', '')),
                },
            )
            return Response({'detail': 'Notification sent.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Clearance Report (owner reports completion to HR) ──────────────────────────

class ClearanceReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["offboarding"])
    def post(self, request):
        offboarding_id = request.data.get('offboarding_id')
        clearance_title = request.data.get('clearance_title', '')
        employee_name = request.data.get('employee_name', '')
        description = request.data.get('description', '')
        checked_items = request.data.get('checked_items', [])

        if not offboarding_id:
            return Response({"detail": "offboarding_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            record = OffboardingRecord.objects.get(pk=offboarding_id, is_deleted=False)
        except OffboardingRecord.DoesNotExist:
            return Response({"detail": "Offboarding record not found."}, status=status.HTTP_404_NOT_FOUND)

        # Build report message
        items_text = "\n".join([f"✓ {item}" for item in checked_items]) if checked_items else ""
        full_message = f"Clearance report from {request.user} for {employee_name}.\n\n"
        if items_text:
            full_message += f"Completed items:\n{items_text}\n\n"
        if description:
            full_message += f"Notes: {description}"

        # Notify all HR users (is_staff) and the record initiator
        try:
            from apps.notifications.models import Notification
            from apps.notifications.constants import NotificationChannel
            from django.contrib.auth import get_user_model

            User = get_user_model()
            # Target HR staff users
            hr_users = list(User.objects.filter(is_staff=True, is_active=True).values_list('id', flat=True))
            # Also notify record initiator if set
            if record.initiated_by_id and record.initiated_by_id not in hr_users:
                hr_users.append(record.initiated_by_id)

            for uid in hr_users:
                Notification.objects.create(
                    recipient_id=uid,
                    actor=request.user,
                    event_type='offboarding.clearance_report',
                    title=f'Clearance Report: {clearance_title} — {employee_name}',
                    message=full_message.strip(),
                    reference_type='offboarding',
                    reference_id=str(offboarding_id),
                    channel=NotificationChannel.IN_APP,
                    severity='info',
                    action_url='/employees/offboarding',
                    metadata={
                        'clearance_title': clearance_title,
                        'employee_name': employee_name,
                        'offboarding_id': str(offboarding_id),
                        'checked_items': checked_items,
                        'description': description,
                    },
                )
            return Response({'detail': 'Report sent to HR.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)