from decimal import Decimal
from rest_framework import serializers

from .models import (
    Milestone, Invoice, Payment, PaymentAllocation,
    InvoiceType, InvoiceStatus, MilestoneStatus, PaymentMode,
)


def _dec(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


# ─────────────────────────────────────────────────────────────────────────────
# Milestone
# ─────────────────────────────────────────────────────────────────────────────

class MilestoneListSerializer(serializers.ModelSerializer):
    project_name  = serializers.CharField(source="project.name", read_only=True)
    project_code  = serializers.CharField(source="project.code", read_only=True)
    status_label  = serializers.CharField(source="get_status_display", read_only=True)
    invoice_count = serializers.SerializerMethodField()

    class Meta:
        model = Milestone
        fields = [
            "id", "project", "project_name", "project_code",
            "milestone_name", "percentage", "amount",
            "due_date", "sequence", "status", "status_label",
            "invoice_count", "created_at",
        ]

    def get_invoice_count(self, obj):
        return obj.invoices.filter(is_deleted=False).count()


class MilestoneDetailSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Milestone
        fields = [
            "id", "project", "project_name", "project_code",
            "milestone_name", "description", "percentage", "amount",
            "due_date", "sequence", "status", "status_label",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MilestoneCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = [
            "project", "milestone_name", "description",
            "percentage", "amount", "due_date", "sequence",
        ]

    def validate(self, data):
        from apps.projects.models import Project
        from .budget_service import (
            milestone_percentage_for_amount,
            validate_milestone_amount,
        )

        project = data.get("project") or getattr(self.instance, "project", None)
        if not project:
            raise serializers.ValidationError({"project": "Project is required."})

        if isinstance(project, str):
            project = Project.objects.get(pk=project)

        amount = data.get("amount", getattr(self.instance, "amount", None))
        if amount is None:
            raise serializers.ValidationError({"amount": "Amount is required."})

        if self.instance and self.instance.status in (MilestoneStatus.INVOICED, MilestoneStatus.PAID):
            if _dec(amount) != _dec(self.instance.amount):
                raise serializers.ValidationError(
                    {"amount": "Cannot change amount after milestone is invoiced or paid."}
                )

        budget = _dec(project.budget)
        if budget <= 0:
            raise serializers.ValidationError(
                {"project": "Set a project budget before adding billing milestones."}
            )

        try:
            validate_milestone_amount(
                project,
                amount,
                exclude_milestone_id=getattr(self.instance, "pk", None),
            )
        except ValueError as exc:
            raise serializers.ValidationError({"amount": str(exc)}) from exc

        data["percentage"] = milestone_percentage_for_amount(project, amount)
        return data


# ─────────────────────────────────────────────────────────────────────────────
# PaymentAllocation (inline)
# ─────────────────────────────────────────────────────────────────────────────

class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    payment_reference = serializers.CharField(source="payment.payment_reference", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = [
            "id", "payment", "payment_reference",
            "invoice", "invoice_number",
            "allocated_amount", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PaymentAllocationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAllocation
        fields = ["payment", "invoice", "allocated_amount", "notes"]

    def validate(self, data):
        invoice = data["invoice"]
        amount  = data["allocated_amount"]
        # Allow slight over-payment rounding (1 paisa tolerance)
        if amount <= 0:
            raise serializers.ValidationError("Allocated amount must be positive.")
        if amount > invoice.pending_amount + Decimal("0.01"):
            raise serializers.ValidationError(
                f"Allocated amount ₹{amount} exceeds invoice pending amount ₹{invoice.pending_amount}."
            )
        payment = data["payment"]
        if amount > payment.unallocated_amount + Decimal("0.01"):
            raise serializers.ValidationError(
                f"Allocated amount ₹{amount} exceeds payment unallocated amount ₹{payment.unallocated_amount}."
            )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Invoice
# ─────────────────────────────────────────────────────────────────────────────

class InvoiceListSerializer(serializers.ModelSerializer):
    client_name      = serializers.CharField(source="client.name", read_only=True)
    project_name     = serializers.CharField(source="project.name", read_only=True)
    project_code     = serializers.CharField(source="project.code", read_only=True)
    milestone_name   = serializers.CharField(source="milestone.milestone_name", read_only=True)
    invoice_type_label = serializers.CharField(source="get_invoice_type_display", read_only=True)
    received_amount  = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    pending_amount   = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    status           = serializers.CharField(read_only=True)
    days_overdue     = serializers.IntegerField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "invoice_type", "invoice_type_label",
            "invoice_date", "due_date",
            "client", "client_name",
            "project", "project_name", "project_code",
            "milestone", "milestone_name",
            "invoice_amount", "tax_percentage", "tax_amount", "total_amount",
            "received_amount", "pending_amount",
            "status", "days_overdue", "is_cancelled",
            "created_at",
        ]


class InvoiceDetailSerializer(serializers.ModelSerializer):
    client_name        = serializers.CharField(source="client.name", read_only=True)
    project_name       = serializers.CharField(source="project.name", read_only=True)
    project_code       = serializers.CharField(source="project.code", read_only=True)
    milestone_name     = serializers.CharField(source="milestone.milestone_name", read_only=True)
    invoice_type_label = serializers.CharField(source="get_invoice_type_display", read_only=True)
    received_amount    = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    pending_amount     = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    status             = serializers.CharField(read_only=True)
    days_overdue       = serializers.IntegerField(read_only=True)
    allocations        = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "invoice_type", "invoice_type_label",
            "invoice_date", "due_date",
            "client", "client_name",
            "project", "project_name", "project_code",
            "milestone", "milestone_name",
            "invoice_amount", "tax_percentage", "tax_amount", "total_amount",
            "received_amount", "pending_amount",
            "status", "days_overdue",
            "notes", "attachment", "is_cancelled",
            "allocations",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "invoice_number", "tax_amount", "total_amount", "created_at", "updated_at"]


class InvoiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            "invoice_type", "invoice_date", "client", "project",
            "milestone", "invoice_amount", "tax_percentage",
            "due_date", "notes", "attachment",
        ]

    def validate(self, data):
        amount = data.get("invoice_amount", 0)
        if amount <= 0:
            raise serializers.ValidationError({"invoice_amount": "Invoice amount must be positive."})

        project = data.get("project") or getattr(self.instance, "project", None)
        if project:
            from .budget_service import validate_invoice_amount
            try:
                validate_invoice_amount(
                    project,
                    amount,
                    exclude_invoice_id=getattr(self.instance, "pk", None),
                )
            except ValueError as exc:
                raise serializers.ValidationError({"invoice_amount": str(exc)}) from exc

        milestone = data.get("milestone")
        if milestone and project and milestone.project_id != project.id:
            raise serializers.ValidationError(
                {"milestone": "Milestone does not belong to the selected project."}
            )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Payment
# ─────────────────────────────────────────────────────────────────────────────

class PaymentListSerializer(serializers.ModelSerializer):
    client_name       = serializers.CharField(source="client.name", read_only=True)
    project_name      = serializers.CharField(source="project.name", read_only=True)
    project_code      = serializers.CharField(source="project.code", read_only=True)
    payment_mode_label = serializers.CharField(source="get_payment_mode_display", read_only=True)
    allocated_amount  = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    unallocated_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "payment_reference", "payment_date",
            "client", "client_name",
            "project", "project_name", "project_code",
            "payment_amount", "payment_mode", "payment_mode_label",
            "bank_reference",
            "allocated_amount", "unallocated_amount",
            "created_at",
        ]


class PaymentDetailSerializer(serializers.ModelSerializer):
    client_name        = serializers.CharField(source="client.name", read_only=True)
    project_name       = serializers.CharField(source="project.name", read_only=True)
    project_code       = serializers.CharField(source="project.code", read_only=True)
    payment_mode_label = serializers.CharField(source="get_payment_mode_display", read_only=True)
    allocated_amount   = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    unallocated_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    allocations        = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "payment_reference", "payment_date",
            "client", "client_name",
            "project", "project_name", "project_code",
            "payment_amount", "payment_mode", "payment_mode_label",
            "bank_reference", "remarks", "attachment",
            "allocated_amount", "unallocated_amount",
            "allocations",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "payment_reference", "created_at", "updated_at"]


class PaymentCreateSerializer(serializers.ModelSerializer):
    allocations = PaymentAllocationCreateSerializer(many=True, required=False)

    class Meta:
        model = Payment
        fields = [
            "client", "project", "payment_date", "payment_amount",
            "payment_mode", "bank_reference", "remarks", "attachment",
            "allocations",
        ]

    def validate(self, data):
        amount = data.get("payment_amount", 0)
        if amount <= 0:
            raise serializers.ValidationError({"payment_amount": "Payment amount must be positive."})
        return data

    def create(self, validated_data):
        from django.db import transaction
        allocations_data = validated_data.pop("allocations", [])
        with transaction.atomic():
            payment = Payment.objects.create(**validated_data)
            for alloc in allocations_data:
                PaymentAllocation.objects.create(
                    payment=payment,
                    invoice=alloc["invoice"],
                    allocated_amount=alloc["allocated_amount"],
                    notes=alloc.get("notes", ""),
                    created_by=payment.created_by,
                    updated_by=payment.updated_by,
                )
            # Auto-update milestone statuses
            for alloc in payment.allocations.all():
                invoice = alloc.invoice
                if invoice.milestone and invoice.status == "PAID":
                    invoice.milestone.status = MilestoneStatus.PAID
                    invoice.milestone.save(update_fields=["status"])
        return payment
