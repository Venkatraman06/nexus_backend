"""Project budget vs milestones, invoices, and payments — single source of truth."""

from decimal import Decimal
from uuid import UUID

from django.db.models import Sum

from apps.projects.models import Project

from .models import Invoice, Milestone, PaymentAllocation


def _dec(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def project_budget_summary(
    project: Project,
    *,
    exclude_milestone_id: UUID | str | None = None,
    exclude_invoice_id: UUID | str | None = None,
) -> dict:
    """
    Budget layers (no double-counting):
      - budget: contract ceiling from Project.budget
      - milestone_planned: sum of milestone amounts (billing plan)
      - invoiced: sum of pre-tax invoice amounts (actual billing)
      - received: payments allocated to project invoices (cash collected)
    """
    budget = _dec(project.budget)

    milestones_qs = Milestone.objects.filter(project=project, is_deleted=False)
    if exclude_milestone_id:
        milestones_qs = milestones_qs.exclude(pk=exclude_milestone_id)
    milestone_planned = _dec(
        milestones_qs.aggregate(t=Sum("amount"))["t"]
    )

    invoices_qs = Invoice.objects.filter(
        project=project, is_deleted=False, is_cancelled=False,
    )
    if exclude_invoice_id:
        invoices_qs = invoices_qs.exclude(pk=exclude_invoice_id)
    invoiced = _dec(invoices_qs.aggregate(t=Sum("invoice_amount"))["t"])

    received = _dec(
        PaymentAllocation.objects.filter(
            invoice__project=project,
            invoice__is_deleted=False,
            invoice__is_cancelled=False,
            payment__is_deleted=False,
        ).aggregate(t=Sum("allocated_amount"))["t"]
    )

    return {
        "budget": float(budget),
        "milestone_planned": float(milestone_planned),
        "milestone_remaining": float(max(Decimal("0"), budget - milestone_planned)),
        "invoiced": float(invoiced),
        "invoice_remaining": float(max(Decimal("0"), budget - invoiced)),
        "received": float(received),
        "outstanding_receivable": float(max(Decimal("0"), invoiced - received)),
    }


def validate_milestone_amount(
    project: Project,
    amount,
    *,
    exclude_milestone_id: UUID | str | None = None,
) -> None:
    amount = _dec(amount)
    if amount < 0:
        raise ValueError("Milestone amount cannot be negative.")
    summary = project_budget_summary(project, exclude_milestone_id=exclude_milestone_id)
    remaining = _dec(summary["milestone_remaining"])
    if amount > remaining:
        raise ValueError(
            f"Milestone amount ₹{amount:,.2f} exceeds remaining planned budget "
            f"₹{remaining:,.2f} (project budget ₹{_dec(project.budget):,.2f})."
        )


def validate_invoice_amount(
    project: Project,
    amount,
    *,
    exclude_invoice_id: UUID | str | None = None,
) -> None:
    amount = _dec(amount)
    if amount <= 0:
        raise ValueError("Invoice amount must be positive.")
    summary = project_budget_summary(project, exclude_invoice_id=exclude_invoice_id)
    remaining = _dec(summary["invoice_remaining"])
    if amount > remaining:
        raise ValueError(
            f"Invoice amount ₹{amount:,.2f} exceeds remaining billable budget "
            f"₹{remaining:,.2f} (project budget ₹{_dec(project.budget):,.2f})."
        )


def milestone_percentage_for_amount(project: Project, amount) -> Decimal:
    budget = _dec(project.budget)
    if budget <= 0:
        return Decimal("0")
    return (_dec(amount) / budget * 100).quantize(Decimal("0.01"))
