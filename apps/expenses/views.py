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

from .models import CompanyExpense, ExpenseStatus
from .serializers import (
    ExpenseListSerializer, ExpenseDetailSerializer, ExpenseCreateSerializer,
)


class CompanyExpenseViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.crm.expense.view"

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
        if p.get("category"):    qs = qs.filter(category=p["category"])
        if p.get("status"):      qs = qs.filter(status=p["status"])
        if p.get("paid_by"):     qs = qs.filter(paid_by_id=p["paid_by"])
        if p.get("project"):     qs = qs.filter(project_id=p["project"])
        if p.get("client"):      qs = qs.filter(client_id=p["client"])
        if p.get("date_from"):   qs = qs.filter(date__gte=p["date_from"])
        if p.get("date_to"):     qs = qs.filter(date__lte=p["date_to"])
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

        # Pending approval
        pending = qs.filter(status=ExpenseStatus.SUBMITTED).aggregate(
            count=Count("id"), amount=Sum("amount")
        )

        return Response({
            "total_all_time":    float(qs.aggregate(t=Sum("amount"))["t"] or 0),
            "total_this_month":  float(month_total),
            "pending_approval":  {
                "count":  pending["count"],
                "amount": float(pending["amount"] or 0),
            },
            "by_category": [
                {**r, "amount": float(r["amount"] or 0)}
                for r in by_cat
            ],
        })
