from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from django.db.models import Count

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from .models import HRComplianceDocument, PolicyDocument, PolicyDocumentAcknowledgment
from .serializers import HRComplianceDocumentSerializer, PolicyDocumentSerializer, PolicyAcknowledgmentSerializer

HR_COMPLIANCE_VIEW   = "pmt.hrms.compliance.view"
HR_COMPLIANCE_CREATE = "pmt.hrms.compliance.create"
HR_COMPLIANCE_UPDATE = "pmt.hrms.compliance.update"
HR_COMPLIANCE_DELETE = "pmt.hrms.compliance.delete"
POLICY_VIEW          = "pmt.policy.view"
POLICY_CREATE        = "pmt.policy.create"
POLICY_UPDATE        = "pmt.policy.update"
POLICY_DELETE        = "pmt.policy.delete"


def _has_perm(request, perm: str) -> bool:
    if request.user.is_staff or getattr(request.user, "is_superuser", False):
        return True
    return perm in getattr(request, "user_permissions", [])


# ── HR Compliance Documents ────────────────────────────────────────────────────

class HRComplianceListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = HR_COMPLIANCE_VIEW
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(tags=["hr-compliance"])
    def get(self, request):
        if _has_perm(request, HR_COMPLIANCE_CREATE):
            # HR / admin: see all, optionally filter by employee
            qs = HRComplianceDocument.objects.filter(is_deleted=False).select_related("employee")
            employee_id = request.query_params.get("employee")
            if employee_id:
                qs = qs.filter(employee_id=employee_id)
        else:
            # Employees: only their own documents
            qs = HRComplianceDocument.objects.filter(
                is_deleted=False, employee=request.user
            ).select_related("employee")

        doc_type = request.query_params.get("document_type")
        if doc_type:
            qs = qs.filter(document_type=doc_type)

        return Response(HRComplianceDocumentSerializer(qs, many=True).data)

    @extend_schema(tags=["hr-compliance"])
    def post(self, request):
        if not _has_perm(request, HR_COMPLIANCE_CREATE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = HRComplianceDocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HRComplianceDetailView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = HR_COMPLIANCE_VIEW
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_object(self, pk, request):
        try:
            obj = HRComplianceDocument.objects.get(pk=pk, is_deleted=False)
        except HRComplianceDocument.DoesNotExist:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if not _has_perm(request, HR_COMPLIANCE_CREATE) and obj.employee_id != request.user.id:
            return None, Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        return obj, None

    @extend_schema(tags=["hr-compliance"])
    def get(self, request, pk):
        obj, err = self._get_object(pk, request)
        if err:
            return err
        return Response(HRComplianceDocumentSerializer(obj).data)

    @extend_schema(tags=["hr-compliance"])
    def patch(self, request, pk):
        if not _has_perm(request, HR_COMPLIANCE_CREATE):
            # Employees can only acknowledge their own documents
            try:
                obj = HRComplianceDocument.objects.get(pk=pk, is_deleted=False, employee=request.user)
            except HRComplianceDocument.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            allowed_fields = {"is_acknowledged", "acknowledged_date"}
            data = {k: v for k, v in request.data.items() if k in allowed_fields}
            serializer = HRComplianceDocumentSerializer(obj, data=data, partial=True)
            if serializer.is_valid():
                serializer.save(updated_by=request.user)
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj, err = self._get_object(pk, request)
        if err:
            return err
        serializer = HRComplianceDocumentSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["hr-compliance"])
    def delete(self, request, pk):
        if not _has_perm(request, HR_COMPLIANCE_CREATE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj, err = self._get_object(pk, request)
        if err:
            return err
        obj.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Policy Documents ───────────────────────────────────────────────────────────

class PolicyDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = POLICY_VIEW
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(tags=["policy-documents"])
    def get(self, request):
        if _has_perm(request, POLICY_CREATE):
            qs = PolicyDocument.objects.filter(is_deleted=False)
        else:
            qs = PolicyDocument.objects.filter(is_deleted=False, is_published=True)

        # Annotate each policy with acknowledgment info for the current user
        user = request.user
        ack_policy_ids = set(
            PolicyDocumentAcknowledgment.objects.filter(employee=user)
            .values_list("policy_id", flat=True)
        )
        ack_counts = {
            a["policy_id"]: a["count"]
            for a in PolicyDocumentAcknowledgment.objects.filter(
                policy__in=qs
            ).values("policy_id").annotate(count=Count("id"))
        }
        data = PolicyDocumentSerializer(qs, many=True).data
        for item in data:
            pid = item["id"]
            item["is_acknowledged_by_me"] = str(pid) in {str(i) for i in ack_policy_ids}
            item["acknowledgment_count"] = ack_counts.get(pid, 0)
        return Response(data)

    @extend_schema(tags=["policy-documents"])
    def post(self, request):
        if not _has_perm(request, POLICY_CREATE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PolicyDocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PolicyDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = POLICY_VIEW
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_object(self, pk):
        try:
            return PolicyDocument.objects.get(pk=pk, is_deleted=False)
        except PolicyDocument.DoesNotExist:
            return None

    @extend_schema(tags=["policy-documents"])
    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _has_perm(request, POLICY_CREATE) and not obj.is_published:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PolicyDocumentSerializer(obj).data)

    @extend_schema(tags=["policy-documents"])
    def patch(self, request, pk):
        if not _has_perm(request, POLICY_CREATE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PolicyDocumentSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(tags=["policy-documents"])
    def delete(self, request, pk):
        if not _has_perm(request, POLICY_CREATE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Policy Acknowledgment Endpoints ─────────────────────────────────────────────

class PolicyAcknowledgeView(APIView):
    """POST: any authenticated employee acknowledges a policy document."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["policy-documents"])
    def post(self, request, pk):
        try:
            obj = PolicyDocument.objects.get(pk=pk, is_deleted=False, is_published=True)
        except PolicyDocument.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        _, created = PolicyDocumentAcknowledgment.objects.get_or_create(
            policy=obj,
            employee=request.user,
            defaults={"created_by": request.user, "updated_by": request.user},
        )
        return Response(
            {"acknowledged": True, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PolicyAcknowledgmentsListView(APIView):
    """GET: HR admin sees who acknowledged a policy document."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = POLICY_CREATE

    @extend_schema(tags=["policy-documents"])
    def get(self, request, pk):
        if not _has_perm(request, POLICY_CREATE):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            obj = PolicyDocument.objects.get(pk=pk, is_deleted=False)
        except PolicyDocument.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        acks = PolicyDocumentAcknowledgment.objects.filter(
            policy=obj
        ).select_related("employee")
        return Response(PolicyAcknowledgmentSerializer(acks, many=True).data)
