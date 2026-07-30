import datetime
from decimal import Decimal

from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.common.viewsets import BaseModelViewSet
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission

from .models import CompanyExpense, ExpenseStatus, ExpenseAttachment
from .serializers import (
    ExpenseListSerializer, ExpenseDetailSerializer, ExpenseCreateSerializer, ExpenseAttachmentSerializer,
)


class CompanyExpenseViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = {
        "list":             "pmt.crm.expense.view",
        "retrieve":         "pmt.crm.expense.view",
        "summary":          "pmt.crm.expense.view",
        "create":           "pmt.crm.expense.create",
        "update":           "pmt.crm.expense.update",
        "partial_update":   "pmt.crm.expense.update",
        "destroy":          "pmt.crm.expense.delete",
        "approve":          "pmt.crm.expense.approve",
        "reject":           "pmt.crm.expense.approve",
        "reimburse":        "pmt.crm.expense.approve",
    }

    queryset = CompanyExpense.objects.select_related(
        "paid_by", "approved_by", "project", "client"
    ).filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ExpenseCreateSerializer
        if self.action == "retrieve":
            return ExpenseDetailSerializer
        return ExpenseListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("category"):        qs = qs.filter(category=p["category"])
        if p.get("status"):          qs = qs.filter(status=p["status"])
        if p.get("paid_by"):         qs = qs.filter(paid_by_id=p["paid_by"])
        if p.get("department"):      qs = qs.filter(Q(paid_by__department_ref_id=p["department"]) | Q(paid_by__department=p["department"]))
        if p.get("department_ref"):  qs = qs.filter(paid_by__department_ref_id=p["department_ref"])
        if p.get("project"):         qs = qs.filter(project_id=p["project"])
        if p.get("client"):          qs = qs.filter(client_id=p["client"])
        if p.get("date_from"):       qs = qs.filter(date__gte=p["date_from"])
        if p.get("date_to"):         qs = qs.filter(date__lte=p["date_to"])
        if p.get("search"):
            q = p["search"]
            qs = qs.filter(
                Q(expense_number__icontains=q) |
                Q(description__icontains=q) |
                Q(reference_number__icontains=q) |
                Q(paid_by__first_name__icontains=q) |
                Q(paid_by__last_name__icontains=q)
            )
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_amount=Sum("amount"),
            total_count=Count("id"),
        )
        by_status = {
            row["status"]: {"count": row["cnt"], "amount": float(row["amt"] or 0)}
            for row in qs.values("status").annotate(
                cnt=Count("id"), amt=Sum("amount")
            )
        }
        serializer = ExpenseListSerializer(qs, many=True)
        return Response({
            "summary": {
                "total_amount": float(agg["total_amount"] or 0),
                "total_count":  agg["total_count"],
                "by_status":    by_status,
            },
            "results": serializer.data,
            "count":   qs.count(),
        })

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        expense = self.get_object()
        if expense.status != ExpenseStatus.DRAFT:
            return Response({"detail": "Only DRAFT expenses can be submitted."},
                            status=status.HTTP_400_BAD_REQUEST)
        expense.status = ExpenseStatus.SUBMITTED
        expense.save(update_fields=["status"])
        return Response(ExpenseDetailSerializer(expense).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        expense = self.get_object()
        if expense.status != ExpenseStatus.SUBMITTED:
            return Response({"detail": "Only SUBMITTED expenses can be approved."},
                            status=status.HTTP_400_BAD_REQUEST)
        expense.status = ExpenseStatus.APPROVED
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save(update_fields=["status", "approved_by", "approved_at"])
        return Response(ExpenseDetailSerializer(expense).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        expense = self.get_object()
        if expense.status != ExpenseStatus.SUBMITTED:
            return Response({"detail": "Only SUBMITTED expenses can be rejected."},
                            status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "")
        expense.status = ExpenseStatus.REJECTED
        expense.rejection_reason = reason
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save(update_fields=["status", "rejection_reason", "approved_by", "approved_at"])
        return Response(ExpenseDetailSerializer(expense).data)

    @action(detail=True, methods=["post"], url_path="reimburse")
    def reimburse(self, request, pk=None):
        expense = self.get_object()
        if expense.status != ExpenseStatus.APPROVED:
            return Response({"detail": "Only APPROVED expenses can be reimbursed."},
                            status=status.HTTP_400_BAD_REQUEST)
        expense.status = ExpenseStatus.REIMBURSED
        expense.save(update_fields=["status"])
        return Response(ExpenseDetailSerializer(expense).data)

    @action(detail=True, methods=["post"], url_path="attachments")
    def upload_attachment(self, request, pk=None):
        expense = self.get_object()
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        attachment = ExpenseAttachment.objects.create(
            expense=expense,
            file=file_obj,
            original_name=file_obj.name,
            file_size=file_obj.size,
            content_type=file_obj.content_type,
            uploaded_by=request.user
        )
        return Response(ExpenseAttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<attachment_id>[^/.]+)")
    def delete_attachment(self, request, pk=None, attachment_id=None):
        expense = self.get_object()
        try:
            attachment = expense.attachments.get(id=attachment_id)
            attachment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ExpenseAttachment.DoesNotExist:
            return Response({"detail": "Attachment not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.get_queryset()
        today = datetime.date.today()

        # Current month totals
        month_qs = qs.filter(date__year=today.year, date__month=today.month)
        month_total = month_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")

        # By category
        by_cat = list(
            qs.values("category").annotate(
                count=Count("id"), amount=Sum("amount")
            ).order_by("-amount")
        )

        # By department
        by_dept = list(
            qs.values(
                dept_id=models.F("paid_by__department_ref__id"),
                dept_name=models.F("paid_by__department_ref__name")
            ).annotate(
                count=Count("id"), amount=Sum("amount")
            ).order_by("-amount")
        )

        # Pending approval
        pending = qs.filter(status=ExpenseStatus.SUBMITTED).aggregate(
            count=Count("id"), amount=Sum("amount")
        )

        # Approved & Reimbursed
        approved = qs.filter(status__in=[ExpenseStatus.APPROVED, ExpenseStatus.REIMBURSED]).aggregate(
            count=Count("id"), amount=Sum("amount")
        )

        return Response({
            "total_all_time":    float(qs.aggregate(t=Sum("amount"))["t"] or 0),
            "total_this_month":  float(month_total),
            "pending_approval":  {
                "count":  pending["count"],
                "amount": float(pending["amount"] or 0),
            },
            "approved_reimbursed": {
                "count":  approved["count"],
                "amount": float(approved["amount"] or 0),
            },
            "by_category": [
                {**r, "amount": float(r["amount"] or 0)}
                for r in by_cat
            ],
            "by_department": [
                {
                    "department_id": str(r["dept_id"]) if r["dept_id"] else None,
                    "department_name": r["dept_name"] or "Unassigned",
                    "count": r["count"],
                    "amount": float(r["amount"] or 0),
                }
                for r in by_dept
            ]
        })


from .models import EmployeeReimbursement, ReimbursementStatus, ReimbursementAttachment, ReimbursementAuditLog
from .serializers import (
    EmployeeReimbursementListSerializer, EmployeeReimbursementDetailSerializer,
    EmployeeReimbursementCreateSerializer, ReimbursementAttachmentSerializer,
)


class EmployeeReimbursementViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated]

    queryset = EmployeeReimbursement.objects.select_related(
        "employee", "employee__department_ref", "project", "client",
        "reviewed_by", "paid_by", "linked_expense"
    ).filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return EmployeeReimbursementCreateSerializer
        if self.action == "retrieve":
            return EmployeeReimbursementDetailSerializer
        return EmployeeReimbursementListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        p = self.request.query_params

        # Non-HR/Finance/Admin users only see their own reimbursement claims
        group_str = ""
        if isinstance(user.keycloak_group, list):
            group_str = " ".join(str(g) for g in user.keycloak_group).lower()
        elif user.keycloak_group:
            group_str = str(user.keycloak_group).lower()

        is_hr_or_admin = (
            user.is_superuser
            or user.is_staff
            or any(g in group_str for g in ["admin", "hr", "ceo", "finance"])
        )
        if not is_hr_or_admin:
            qs = qs.filter(employee=user)

        # Filters
        if p.get("status"):       qs = qs.filter(status=p["status"])
        if p.get("category"):     qs = qs.filter(category=p["category"])
        if p.get("employee"):     qs = qs.filter(employee_id=p["employee"])
        if p.get("department"):   qs = qs.filter(Q(employee__department_ref_id=p["department"]) | Q(employee__department=p["department"]))
        if p.get("project"):      qs = qs.filter(project_id=p["project"])
        if p.get("client"):       qs = qs.filter(client_id=p["client"])
        if p.get("date_from"):    qs = qs.filter(expense_date__gte=p["date_from"])
        if p.get("date_to"):      qs = qs.filter(expense_date__lte=p["date_to"])
        if p.get("min_amount"):   qs = qs.filter(amount_claimed__gte=p["min_amount"])
        if p.get("max_amount"):   qs = qs.filter(amount_claimed__lte=p["max_amount"])
        if p.get("search"):
            q = p["search"]
            qs = qs.filter(
                Q(claim_number__icontains=q) |
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(employee__first_name__icontains=q) |
                Q(employee__last_name__icontains=q)
            )
        return qs

    def perform_create(self, serializer):
        reimbursement = serializer.save(
            employee=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
            status=ReimbursementStatus.DRAFT,
        )
        ReimbursementAuditLog.objects.create(
            reimbursement=reimbursement,
            from_status=ReimbursementStatus.DRAFT,
            to_status=ReimbursementStatus.DRAFT,
            performed_by=self.request.user,
            comments="Reimbursement claim created as Draft",
        )

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_amount=Sum("amount_claimed"),
            total_count=Count("id"),
        )
        by_status = {
            row["status"]: {"count": row["cnt"], "amount": float(row["amt"] or 0)}
            for row in qs.values("status").annotate(
                cnt=Count("id"), amt=Sum("amount_claimed")
            )
        }
        serializer = EmployeeReimbursementListSerializer(qs, many=True)
        return Response({
            "summary": {
                "total_amount": float(agg["total_amount"] or 0),
                "total_count":  agg["total_count"],
                "by_status":    by_status,
            },
            "results": serializer.data,
            "count":   qs.count(),
        })

    def _log_status_change(self, instance, from_status, to_status, user, comments=""):
        ReimbursementAuditLog.objects.create(
            reimbursement=instance,
            from_status=from_status,
            to_status=to_status,
            performed_by=user,
            comments=comments,
        )

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        claim = self.get_object()
        if claim.status not in (ReimbursementStatus.DRAFT, ReimbursementStatus.INFO_REQUESTED):
            return Response({"detail": "Only DRAFT or INFO_REQUESTED claims can be submitted."},
                            status=status.HTTP_400_BAD_REQUEST)
        old_status = claim.status
        claim.status = ReimbursementStatus.SUBMITTED
        claim.save(update_fields=["status"])
        self._log_status_change(claim, old_status, ReimbursementStatus.SUBMITTED, request.user, "Submitted for review")
        return Response(EmployeeReimbursementDetailSerializer(claim).data)

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        """Move to UNDER_HR_REVIEW or request additional info."""
        claim = self.get_object()
        action_type = request.data.get("action", "review") # 'review' or 'request_info'
        comments = request.data.get("comments", "")
        old_status = claim.status

        if action_type == "request_info":
            claim.status = ReimbursementStatus.INFO_REQUESTED
            claim.review_comments = comments
            claim.reviewed_by = request.user
            claim.reviewed_at = timezone.now()
            claim.save(update_fields=["status", "review_comments", "reviewed_by", "reviewed_at"])
            self._log_status_change(claim, old_status, ReimbursementStatus.INFO_REQUESTED, request.user, comments)
        else:
            claim.status = ReimbursementStatus.UNDER_HR_REVIEW
            claim.reviewed_by = request.user
            claim.reviewed_at = timezone.now()
            claim.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            self._log_status_change(claim, old_status, ReimbursementStatus.UNDER_HR_REVIEW, request.user, comments)

        return Response(EmployeeReimbursementDetailSerializer(claim).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        claim = self.get_object()
        if claim.status in (ReimbursementStatus.APPROVED, ReimbursementStatus.PAID, ReimbursementStatus.REJECTED):
            return Response({"detail": f"Claim is already {claim.status}."}, status=status.HTTP_400_BAD_REQUEST)

        comments = request.data.get("comments", "")
        old_status = claim.status
        claim.status = ReimbursementStatus.APPROVED
        claim.reviewed_by = request.user
        claim.reviewed_at = timezone.now()
        claim.review_comments = comments

        # Automatically create or link to Company Expense record on Approval
        if not claim.linked_expense:
            expense = CompanyExpense.objects.create(
                date=claim.expense_date,
                category=claim.category,
                description=f"[Reimbursement {claim.claim_number}] {claim.title}",
                amount=claim.amount_claimed,
                paid_by=claim.employee,
                project=claim.project,
                client=claim.client,
                payment_mode=claim.payment_method,
                reference_number=claim.claim_number,
                attachment=claim.attachment,
                status=ExpenseStatus.APPROVED,
                approved_by=request.user,
                approved_at=timezone.now(),
                notes=f"Auto-generated expense entry from approved reimbursement claim {claim.claim_number}.",
            )
            claim.linked_expense = expense

        claim.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comments", "linked_expense"])
        self._log_status_change(claim, old_status, ReimbursementStatus.APPROVED, request.user, comments)

        return Response(EmployeeReimbursementDetailSerializer(claim).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        claim = self.get_object()
        if claim.status in (ReimbursementStatus.APPROVED, ReimbursementStatus.PAID, ReimbursementStatus.REJECTED):
            return Response({"detail": f"Cannot reject a claim that is {claim.status}."}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get("comments") or request.data.get("reason", "")
        old_status = claim.status
        claim.status = ReimbursementStatus.REJECTED
        claim.reviewed_by = request.user
        claim.reviewed_at = timezone.now()
        claim.review_comments = reason
        claim.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comments"])

        self._log_status_change(claim, old_status, ReimbursementStatus.REJECTED, request.user, reason)
        return Response(EmployeeReimbursementDetailSerializer(claim).data)

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        claim = self.get_object()
        if claim.status not in (ReimbursementStatus.APPROVED, ReimbursementStatus.UNDER_HR_REVIEW):
            return Response({"detail": "Only APPROVED or UNDER_HR_REVIEW claims can be marked as paid."},
                            status=status.HTTP_400_BAD_REQUEST)

        comments = request.data.get("comments", "")
        old_status = claim.status
        claim.status = ReimbursementStatus.PAID
        claim.paid_by = request.user
        claim.paid_at = timezone.now()

        # Sync linked expense status to REIMBURSED if present
        if claim.linked_expense:
            claim.linked_expense.status = ExpenseStatus.REIMBURSED
            claim.linked_expense.save(update_fields=["status"])

        claim.save(update_fields=["status", "paid_by", "paid_at"])
        self._log_status_change(claim, old_status, ReimbursementStatus.PAID, request.user, comments)

        return Response(EmployeeReimbursementDetailSerializer(claim).data)

    @action(detail=True, methods=["post"], url_path="attachments")
    def upload_attachment(self, request, pk=None):
        claim = self.get_object()
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "No file supplied."}, status=status.HTTP_400_BAD_REQUEST)

        att = ReimbursementAttachment.objects.create(
            reimbursement=claim,
            file=file_obj,
            original_name=file_obj.name,
            file_size=file_obj.size,
            content_type=file_obj.content_type or "application/octet-stream",
            uploaded_by=request.user,
        )
        return Response(ReimbursementAttachmentSerializer(att).data, status=status.HTTP_201_CREATED)

