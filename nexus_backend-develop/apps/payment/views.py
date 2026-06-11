import datetime
from decimal import Decimal

from django.db.models import Sum, Count, Q, F, ExpressionWrapper, DecimalField
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.common.viewsets import BaseModelViewSet
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission

from .models import (
    Milestone, Invoice, Payment, PaymentAllocation,
    InvoiceStatus, MilestoneStatus,
)
from .serializers import (
    MilestoneListSerializer, MilestoneDetailSerializer, MilestoneCreateSerializer,
    InvoiceListSerializer, InvoiceDetailSerializer, InvoiceCreateSerializer,
    PaymentListSerializer, PaymentDetailSerializer, PaymentCreateSerializer,
    PaymentAllocationCreateSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Milestone
# ─────────────────────────────────────────────────────────────────────────────

class MilestoneViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.payment.invoice.view"
    queryset = Milestone.objects.select_related("project").filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MilestoneCreateSerializer
        if self.action == "retrieve":
            return MilestoneDetailSerializer
        return MilestoneListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get("project")
        stat    = self.request.query_params.get("status")
        if project: qs = qs.filter(project_id=project)
        if stat:    qs = qs.filter(status=stat)
        return qs

    @action(detail=False, methods=["get"], url_path="budget-summary")
    def budget_summary(self, request):
        from apps.projects.models import Project
        from apps.payment.budget_service import project_budget_summary

        project_id = request.query_params.get("project")
        if not project_id:
            return Response(
                {"detail": "project query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project = Project.objects.filter(pk=project_id, is_deleted=False).first()
        if not project:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(project_budget_summary(project))

    @action(detail=True, methods=["post"], url_path="generate-invoice")
    def generate_invoice(self, request, pk=None):
        """Create an invoice from this milestone."""
        from apps.payment.budget_service import validate_invoice_amount

        milestone = self.get_object()
        if milestone.status == MilestoneStatus.PAID:
            return Response(
                {"detail": "Milestone is already paid."}, status=status.HTTP_400_BAD_REQUEST
            )
        if milestone.invoices.filter(is_deleted=False, is_cancelled=False).exists():
            return Response(
                {"detail": "An active invoice already exists for this milestone."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project = milestone.project
        if not project.client_id:
            return Response(
                {"detail": "Link a client to the project before generating an invoice."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_invoice_amount(project, milestone.amount)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        invoice = Invoice.objects.create(
            invoice_type="MILESTONE",
            invoice_date=datetime.date.today(),
            client=milestone.project.client,
            project=milestone.project,
            milestone=milestone,
            invoice_amount=milestone.amount,
            created_by=request.user,
            updated_by=request.user,
        )
        milestone.status = MilestoneStatus.INVOICED
        milestone.save(update_fields=["status"])
        return Response(
            {"detail": "Invoice created.", "invoice_number": invoice.invoice_number},
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Invoice
# ─────────────────────────────────────────────────────────────────────────────

class InvoiceViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.payment.invoice.view"
    queryset = Invoice.objects.select_related(
        "client", "project", "milestone"
    ).filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return InvoiceCreateSerializer
        if self.action == "retrieve":
            return InvoiceDetailSerializer
        return InvoiceListSerializer

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("allocations__payment")
        client   = self.request.query_params.get("client")
        project  = self.request.query_params.get("project")
        inv_type = self.request.query_params.get("invoice_type")
        search   = self.request.query_params.get("search")
        if client:   qs = qs.filter(client_id=client)
        if project:  qs = qs.filter(project_id=project)
        if inv_type: qs = qs.filter(invoice_type=inv_type)
        if search:   qs = qs.filter(
            Q(invoice_number__icontains=search) | Q(client__name__icontains=search)
        )
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        # Status filter requires Python-level computation (dynamic property)
        status_filter = request.query_params.get("status")
        invoices = list(qs)
        if status_filter:
            invoices = [inv for inv in invoices if inv.status == status_filter]
        serializer = InvoiceListSerializer(invoices, many=True)
        return Response({"results": serializer.data, "count": len(invoices)})

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_invoice(self, request, pk=None):
        invoice = self.get_object()
        if invoice.is_cancelled:
            return Response({"detail": "Already cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        invoice.is_cancelled = True
        invoice.save(update_fields=["is_cancelled"])
        return Response({"detail": "Invoice cancelled."})

    @action(detail=False, methods=["get"], url_path="receivable-summary")
    def receivable_summary(self, request):
        invoices = list(self.get_queryset())
        total_invoiced  = sum(inv.total_amount for inv in invoices)
        total_received  = sum(inv.received_amount for inv in invoices)
        total_pending   = sum(inv.pending_amount for inv in invoices)
        overdue_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.OVERDUE]
        overdue_amount  = sum(inv.pending_amount for inv in overdue_invoices)
        partial_count   = sum(1 for inv in invoices if inv.status == InvoiceStatus.PARTIAL)
        collection_pct  = (
            float(total_received / total_invoiced * 100) if total_invoiced else 0
        )
        return Response({
            "total_invoiced":   float(total_invoiced),
            "total_received":   float(total_received),
            "total_pending":    float(total_pending),
            "overdue_amount":   float(overdue_amount),
            "overdue_count":    len(overdue_invoices),
            "partial_count":    partial_count,
            "collection_pct":   round(collection_pct, 2),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Payment
# ─────────────────────────────────────────────────────────────────────────────

class PaymentViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.payment.payment.view"
    queryset = Payment.objects.select_related("client", "project").filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PaymentCreateSerializer
        if self.action == "retrieve":
            return PaymentDetailSerializer
        return PaymentListSerializer

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("allocations__invoice")
        client  = self.request.query_params.get("client")
        project = self.request.query_params.get("project")
        mode    = self.request.query_params.get("payment_mode")
        search  = self.request.query_params.get("search")
        date_from = self.request.query_params.get("date_from")
        date_to   = self.request.query_params.get("date_to")
        if client:    qs = qs.filter(client_id=client)
        if project:   qs = qs.filter(project_id=project)
        if mode:      qs = qs.filter(payment_mode=mode)
        if date_from: qs = qs.filter(payment_date__gte=date_from)
        if date_to:   qs = qs.filter(payment_date__lte=date_to)
        if search:    qs = qs.filter(
            Q(payment_reference__icontains=search)
            | Q(client__name__icontains=search)
            | Q(bank_reference__icontains=search)
        )
        return qs

    @action(detail=True, methods=["post"], url_path="allocate")
    def allocate(self, request, pk=None):
        """Allocate this payment against one or more invoices."""
        payment = self.get_object()
        serializer = PaymentAllocationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alloc = serializer.save(
            payment=payment,
            created_by=request.user,
            updated_by=request.user,
        )
        # Auto-update milestone if invoice is now PAID
        invoice = alloc.invoice
        if invoice.milestone and invoice.status == InvoiceStatus.PAID:
            invoice.milestone.status = MilestoneStatus.PAID
            invoice.milestone.save(update_fields=["status"])
        return Response(
            {"detail": "Allocation recorded.", "allocated_amount": float(alloc.allocated_amount)},
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# PaymentAllocation standalone CRUD
# ─────────────────────────────────────────────────────────────────────────────

class PaymentAllocationViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.payment.payment.view"
    queryset = PaymentAllocation.objects.select_related(
        "payment__client", "invoice"
    ).filter(is_deleted=False)
    serializer_class = PaymentAllocationCreateSerializer


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Metrics
# ─────────────────────────────────────────────────────────────────────────────

class PaymentDashboardView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.payment.dashboard.view"

    @extend_schema(tags=["payment-dashboard"])
    def get(self, request):
        invoices = list(
            Invoice.objects.filter(is_deleted=False, is_cancelled=False)
            .prefetch_related("allocations__payment")
        )
        payments = Payment.objects.filter(is_deleted=False)

        total_invoiced  = sum(inv.total_amount for inv in invoices)
        total_received  = payments.aggregate(t=Sum("payment_amount"))["t"] or Decimal("0")
        total_pending   = total_invoiced - total_received
        overdue_invs    = [inv for inv in invoices if inv.status == InvoiceStatus.OVERDUE]
        overdue_amount  = sum(inv.pending_amount for inv in overdue_invs)
        partial_count   = sum(1 for inv in invoices if inv.status == InvoiceStatus.PARTIAL)
        collection_pct  = float(total_received / total_invoiced * 100) if total_invoiced else 0

        # Monthly collection (last 12 months)
        today = datetime.date.today()
        monthly = []
        for i in range(11, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            agg = payments.filter(payment_date__year=y, payment_date__month=m).aggregate(
                t=Sum("payment_amount")
            )["t"] or 0
            inv_agg = Invoice.objects.filter(
                is_deleted=False, is_cancelled=False,
                invoice_date__year=y, invoice_date__month=m,
            ).aggregate(t=Sum("total_amount"))["t"] or 0
            monthly.append({
                "month": f"{y}-{m:02d}",
                "label": datetime.date(y, m, 1).strftime("%b %Y"),
                "collected": float(agg),
                "invoiced":  float(inv_agg),
            })

        return Response({
            "kpi": {
                "total_receivable": float(total_pending),
                "total_received":   float(total_received),
                "total_invoiced":   float(total_invoiced),
                "partial_count":    partial_count,
                "overdue_amount":   float(overdue_amount),
                "overdue_count":    len(overdue_invs),
                "collection_pct":   round(collection_pct, 2),
            },
            "monthly_trend": monthly,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Client Receivable Summary
# ─────────────────────────────────────────────────────────────────────────────

class ClientReceivableView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.payment.dashboard.view"

    @extend_schema(tags=["payment-reports"])
    def get(self, request):
        today = datetime.date.today()
        invoices = list(
            Invoice.objects.filter(is_deleted=False, is_cancelled=False)
            .select_related("client")
            .prefetch_related("allocations__payment")
        )

        client_map: dict = {}
        for inv in invoices:
            cid  = str(inv.client_id)
            name = inv.client.name
            if cid not in client_map:
                client_map[cid] = {
                    "client_id":     cid,
                    "client_name":   name,
                    "total_invoiced": Decimal("0"),
                    "total_received": Decimal("0"),
                    "overdue_amount": Decimal("0"),
                    "invoice_count":  0,
                    "collection_days": [],
                }
            d = client_map[cid]
            d["total_invoiced"]  += inv.total_amount
            d["total_received"]  += inv.received_amount
            d["invoice_count"]   += 1
            if inv.status == InvoiceStatus.OVERDUE:
                d["overdue_amount"] += inv.pending_amount
            # Collect days for fully paid invoices
            if inv.status == InvoiceStatus.PAID and inv.invoice_date:
                last_payment = inv.allocations.filter(
                    payment__is_deleted=False
                ).order_by("-payment__payment_date").first()
                if last_payment:
                    days = (last_payment.payment.payment_date - inv.invoice_date).days
                    d["collection_days"].append(max(0, days))

        result = []
        for d in client_map.values():
            avg_days = (
                round(sum(d["collection_days"]) / len(d["collection_days"]))
                if d["collection_days"] else None
            )
            result.append({
                "client_id":         d["client_id"],
                "client_name":       d["client_name"],
                "total_invoiced":    float(d["total_invoiced"]),
                "total_received":    float(d["total_received"]),
                "total_pending":     float(d["total_invoiced"] - d["total_received"]),
                "overdue_amount":    float(d["overdue_amount"]),
                "invoice_count":     d["invoice_count"],
                "collection_pct":    round(
                    float(d["total_received"] / d["total_invoiced"] * 100), 2
                ) if d["total_invoiced"] else 0,
                "avg_collection_days": avg_days,
            })

        result.sort(key=lambda x: x["total_pending"], reverse=True)
        return Response({"results": result, "count": len(result)})


# ─────────────────────────────────────────────────────────────────────────────
# Project Receivable Summary
# ─────────────────────────────────────────────────────────────────────────────

class ProjectReceivableView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.payment.dashboard.view"

    @extend_schema(tags=["payment-reports"])
    def get(self, request):
        invoices = list(
            Invoice.objects.filter(is_deleted=False, is_cancelled=False, project__isnull=False)
            .select_related("project__client")
            .prefetch_related("allocations__payment")
        )

        project_map: dict = {}
        for inv in invoices:
            pid  = str(inv.project_id)
            proj = inv.project
            if pid not in project_map:
                project_map[pid] = {
                    "project_id":    pid,
                    "project_name":  proj.name,
                    "project_code":  proj.code,
                    "client_name":   proj.client.name if proj.client else "",
                    "total_invoiced": Decimal("0"),
                    "total_received": Decimal("0"),
                    "overdue_amount": Decimal("0"),
                    "invoice_count":  0,
                }
            d = project_map[pid]
            d["total_invoiced"]  += inv.total_amount
            d["total_received"]  += inv.received_amount
            d["invoice_count"]   += 1
            if inv.status == InvoiceStatus.OVERDUE:
                d["overdue_amount"] += inv.pending_amount

        result = []
        for d in project_map.values():
            result.append({
                "project_id":    d["project_id"],
                "project_name":  d["project_name"],
                "project_code":  d["project_code"],
                "client_name":   d["client_name"],
                "total_invoiced": float(d["total_invoiced"]),
                "total_received": float(d["total_received"]),
                "total_pending":  float(d["total_invoiced"] - d["total_received"]),
                "overdue_amount": float(d["overdue_amount"]),
                "invoice_count":  d["invoice_count"],
                "collection_pct": round(
                    float(d["total_received"] / d["total_invoiced"] * 100), 2
                ) if d["total_invoiced"] else 0,
            })

        result.sort(key=lambda x: x["total_pending"], reverse=True)
        return Response({"results": result, "count": len(result)})
