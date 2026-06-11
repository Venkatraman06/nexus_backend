"""Executive dashboard aggregations scoped to financial year."""

from datetime import date
from decimal import Decimal

from django.db.models import Sum, Count, Q

from apps.accounts.models import Employee
from apps.common.constants import EmployeeStatus
from apps.expenses.models import CompanyExpense, ExpenseStatus
from apps.master.models import RateCard
from apps.payment.models import Invoice, Payment, PaymentAllocation
from apps.projects.models import Client, Project
from apps.workitems.models import WorkLog

from .fy_utils import (
    available_fy_years,
    current_fy_start,
    fy_date_range,
    fy_label,
    iter_fy_months,
)


HOURS_PER_DAY = Decimal("8")

PIPELINE_BUCKETS = (
    ("pipeline", "Enquiry / Follow-up", ("enquiry", "followup"), "#8B5CF6"),
    ("active", "Active business", ("kickoff", "ongoing"), "#10B981"),
    ("completed", "Completed", ("close",), "#059669"),
    ("cancelled", "Cancelled", ("cancelled",), "#EF4444"),
)


def _build_project_pipeline(projects_qs, fy_start: date, fy_end: date) -> dict:
    """Group projects by lifecycle bucket for enquiry → business conversion ratios."""
    slug_to_bucket: dict[str, str] = {}
    bucket_meta: dict[str, dict] = {}
    for key, label, slugs, color in PIPELINE_BUCKETS:
        bucket_meta[key] = {"key": key, "label": label, "color": color, "count": 0}
        for slug in slugs:
            slug_to_bucket[slug] = key

    fy_created = 0
    for p in projects_qs.select_related("workflow_state"):
        created = p.created_at.date() if p.created_at else None
        if created and fy_start <= created <= fy_end:
            fy_created += 1

        slug = p.workflow_state.slug if p.workflow_state else ""
        bucket_key = slug_to_bucket.get(slug)
        if bucket_key:
            bucket_meta[bucket_key]["count"] += 1

    total = sum(b["count"] for b in bucket_meta.values())
    converted = bucket_meta["active"]["count"] + bucket_meta["completed"]["count"]
    decided = bucket_meta["completed"]["count"] + bucket_meta["cancelled"]["count"]

    breakdown = []
    for key, label, _slugs, color in PIPELINE_BUCKETS:
        count = bucket_meta[key]["count"]
        breakdown.append({
            "key": key,
            "label": label,
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0.0,
            "color": color,
        })

    return {
        "total": total,
        "fy_new": fy_created,
        "pipeline": bucket_meta["pipeline"]["count"],
        "active": bucket_meta["active"]["count"],
        "completed": bucket_meta["completed"]["count"],
        "cancelled": bucket_meta["cancelled"]["count"],
        "conversion_pct": round(converted / total * 100, 1) if total else 0.0,
        "completion_pct": round(bucket_meta["completed"]["count"] / total * 100, 1) if total else 0.0,
        "win_pct": round(bucket_meta["completed"]["count"] / decided * 100, 1) if decided else 0.0,
        "breakdown": breakdown,
    }


def _dec(v) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def _rate_cache() -> dict[tuple, float]:
    cache: dict[tuple, float] = {}
    for rc in RateCard.objects.filter(is_active=True).select_related(
        "designation_ref", "department_ref"
    ):
        cache[(rc.designation_ref_id, rc.department_ref_id)] = float(rc.hr_daily_rate)
    return cache


def _employee_hourly_cost(employee, rates: dict) -> float:
    if not employee:
        return 0.0
    key = (employee.designation_ref_id, employee.department_ref_id)
    daily = rates.get(key, 0.0)
    return daily / float(HOURS_PER_DAY) if daily else 0.0


def _project_employee_cost(project_id, fy_start: date, fy_end: date, rates: dict) -> float:
    logs = (
        WorkLog.objects.filter(
            ticket__project_id=project_id,
            is_deleted=False,
            log_date__gte=fy_start,
            log_date__lte=fy_end,
        )
        .select_related("employee")
    )
    total = 0.0
    for log in logs:
        hourly = _employee_hourly_cost(log.employee, rates)
        total += float(log.hours or 0) * hourly
    return round(total, 2)


def _project_logged_hours(project_id, fy_start: date, fy_end: date) -> float:
    val = WorkLog.objects.filter(
        ticket__project_id=project_id,
        is_deleted=False,
        log_date__gte=fy_start,
        log_date__lte=fy_end,
    ).aggregate(t=Sum("hours"))["t"]
    return round(float(val or 0), 1)


def _project_expense_cost(project_id, fy_start: date, fy_end: date) -> float:
    val = CompanyExpense.objects.filter(
        project_id=project_id,
        is_deleted=False,
        status__in=[ExpenseStatus.APPROVED, ExpenseStatus.REIMBURSED],
        date__gte=fy_start,
        date__lte=fy_end,
    ).aggregate(t=Sum("amount"))["t"]
    return round(float(val or 0), 2)


def build_executive_dashboard(fy_start_year: int, today: date | None = None) -> dict:
    today = today or date.today()
    fy_start, fy_end = fy_date_range(fy_start_year, today)
    rates = _rate_cache()

    employees = Employee.objects.filter(is_deleted=False)
    employee_stats = {
        "total": employees.count(),
        "active": employees.filter(is_active=True, status=EmployeeStatus.ACTIVE).count(),
    }

    clients = Client.objects.filter(is_deleted=False)
    vendor_stats = {
        "total": clients.count(),
        "active": clients.filter(is_active=True).count(),
    }

    projects_qs = Project.objects.filter(is_deleted=False).select_related("client")
    project_stats = {
        "total": projects_qs.count(),
        "active": projects_qs.filter(is_active=True).count(),
    }

    invoices_fy = Invoice.objects.filter(
        is_deleted=False,
        is_cancelled=False,
        invoice_date__gte=fy_start,
        invoice_date__lte=fy_end,
    )
    invoiced_total = _dec(invoices_fy.aggregate(t=Sum("invoice_amount"))["t"])

    payments_fy = Payment.objects.filter(
        is_deleted=False,
        payment_date__gte=fy_start,
        payment_date__lte=fy_end,
    )
    received_total = _dec(payments_fy.aggregate(t=Sum("payment_amount"))["t"])

    expenses_fy = CompanyExpense.objects.filter(
        is_deleted=False,
        status__in=[ExpenseStatus.APPROVED, ExpenseStatus.REIMBURSED],
        date__gte=fy_start,
        date__lte=fy_end,
    )
    expense_total = _dec(expenses_fy.aggregate(t=Sum("amount"))["t"])

    budget_total = _dec(
        projects_qs.filter(is_active=True).aggregate(t=Sum("budget"))["t"]
    )

    finance_stats = {
        "budget_total": float(budget_total),
        "invoiced": float(invoiced_total),
        "received": float(received_total),
        "pending": float(max(Decimal("0"), invoiced_total - received_total)),
        "expenses": float(expense_total),
    }

    # Client geo map + FY invoiced per client
    client_invoiced: dict[str, float] = {}
    for row in (
        invoices_fy.values("client_id")
        .annotate(total=Sum("invoice_amount"))
    ):
        client_invoiced[str(row["client_id"])] = float(row["total"] or 0)

    client_projects = {
        str(row["client_id"]): row["cnt"]
        for row in projects_qs.filter(client_id__isnull=False)
        .values("client_id")
        .annotate(cnt=Count("id"))
    }

    clients_map = []
    for c in clients.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        is_active=True,
    ):
        clients_map.append({
            "id": str(c.id),
            "name": c.name,
            "code": c.code,
            "latitude": float(c.latitude),
            "longitude": float(c.longitude),
            "address": c.formatted_address or c.address,
            "project_count": client_projects.get(str(c.id), 0),
            "invoiced_fy": client_invoiced.get(str(c.id), 0.0),
        })

    # Monthly invoice vs payment within FY
    payment_monthly = []
    billing_monthly = []
    for y, m, label in iter_fy_months(fy_start_year, today):
        inv = _dec(
            invoices_fy.filter(invoice_date__year=y, invoice_date__month=m)
            .aggregate(t=Sum("invoice_amount"))["t"]
        )
        pay = _dec(
            payments_fy.filter(payment_date__year=y, payment_date__month=m)
            .aggregate(t=Sum("payment_amount"))["t"]
        )
        payment_monthly.append({
            "year": y,
            "month": m,
            "label": label,
            "invoiced": float(inv),
            "received": float(pay),
        })

        billable = _dec(
            WorkLog.objects.filter(
                is_deleted=False,
                is_billable=True,
                log_date__year=y,
                log_date__month=m,
            ).aggregate(t=Sum("hours"))["t"]
        )
        non_billable = _dec(
            WorkLog.objects.filter(
                is_deleted=False,
                is_billable=False,
                log_date__year=y,
                log_date__month=m,
            ).aggregate(t=Sum("hours"))["t"]
        )
        billing_monthly.append({
            "year": y,
            "month": m,
            "label": label,
            "billable_hours": float(billable),
            "non_billable_hours": float(non_billable),
        })

    # Project portfolio with margin
    project_rows = []
    for p in projects_qs.filter(is_active=True).order_by("code"):
        pid = str(p.id)
        logged = _project_logged_hours(p.id, fy_start, fy_end)
        emp_cost = _project_employee_cost(p.id, fy_start, fy_end, rates)
        exp_cost = _project_expense_cost(p.id, fy_start, fy_end)
        total_cost = round(emp_cost + exp_cost, 2)

        rev_invoiced = float(
            invoices_fy.filter(project_id=p.id).aggregate(t=Sum("invoice_amount"))["t"] or 0
        )
        rev_received = float(
            PaymentAllocation.objects.filter(
                invoice__project_id=p.id,
                invoice__is_deleted=False,
                invoice__is_cancelled=False,
                payment__is_deleted=False,
                payment__payment_date__gte=fy_start,
                payment__payment_date__lte=fy_end,
            ).aggregate(t=Sum("allocated_amount"))["t"] or 0
        )

        gross_margin = round(rev_invoiced - total_cost, 2)
        margin_pct = round((gross_margin / rev_invoiced * 100), 1) if rev_invoiced else None

        project_rows.append({
            "id": pid,
            "code": p.code,
            "name": p.name,
            "client_name": p.client.name if p.client else None,
            "budget": float(p.budget or 0),
            "estimated_hours": float(p.estimated_hours or 0),
            "logged_hours_fy": logged,
            "revenue_invoiced": rev_invoiced,
            "revenue_received": rev_received,
            "employee_cost": emp_cost,
            "expense_cost": exp_cost,
            "total_cost": total_cost,
            "gross_margin": gross_margin,
            "gross_margin_pct": margin_pct,
        })

    return {
        "fy": {
            "start_year": fy_start_year,
            "label": fy_label(fy_start_year),
            "start_date": str(fy_start),
            "end_date": str(fy_end),
        },
        "available_fy_years": available_fy_years(today),
        "employees": employee_stats,
        "vendors": vendor_stats,
        "projects": project_stats,
        "finance": finance_stats,
        "clients_map": clients_map,
        "payment_monthly": payment_monthly,
        "billing_monthly": billing_monthly,
        "project_portfolio": project_rows,
        "project_pipeline": _build_project_pipeline(projects_qs, fy_start, fy_end),
    }


def build_project_executive_detail(project_id, fy_start_year: int, today: date | None = None) -> dict:
    today = today or date.today()
    fy_start, fy_end = fy_date_range(fy_start_year, today)
    rates = _rate_cache()

    project = Project.objects.select_related("client", "manager").get(
        pk=project_id, is_deleted=False,
    )

    logged = _project_logged_hours(project.id, fy_start, fy_end)
    emp_cost = _project_employee_cost(project.id, fy_start, fy_end, rates)
    exp_cost = _project_expense_cost(project.id, fy_start, fy_end)
    total_cost = round(emp_cost + exp_cost, 2)

    invoices = Invoice.objects.filter(
        project=project,
        is_deleted=False,
        is_cancelled=False,
        invoice_date__gte=fy_start,
        invoice_date__lte=fy_end,
    )
    rev_invoiced = float(invoices.aggregate(t=Sum("invoice_amount"))["t"] or 0)
    rev_received = float(
        PaymentAllocation.objects.filter(
            invoice__project=project,
            invoice__is_deleted=False,
            invoice__is_cancelled=False,
            payment__is_deleted=False,
            payment__payment_date__gte=fy_start,
            payment__payment_date__lte=fy_end,
        ).aggregate(t=Sum("allocated_amount"))["t"] or 0
    )

    gross_margin = round(rev_invoiced - total_cost, 2)
    margin_pct = round((gross_margin / rev_invoiced * 100), 1) if rev_invoiced else None

    billable_h = float(
        WorkLog.objects.filter(
            ticket__project=project,
            is_deleted=False,
            is_billable=True,
            log_date__gte=fy_start,
            log_date__lte=fy_end,
        ).aggregate(t=Sum("hours"))["t"] or 0
    )
    non_billable_h = float(
        WorkLog.objects.filter(
            ticket__project=project,
            is_deleted=False,
            is_billable=False,
            log_date__gte=fy_start,
            log_date__lte=fy_end,
        ).aggregate(t=Sum("hours"))["t"] or 0
    )

    return {
        "project": {
            "id": str(project.id),
            "code": project.code,
            "name": project.name,
            "client_name": project.client.name if project.client else None,
            "manager_name": project.manager.full_name if project.manager else None,
            "budget": float(project.budget or 0),
            "estimated_hours": float(project.estimated_hours or 0),
        },
        "fy": {
            "start_year": fy_start_year,
            "label": fy_label(fy_start_year),
            "start_date": str(fy_start),
            "end_date": str(fy_end),
        },
        "hours": {
            "logged_fy": logged,
            "billable_fy": billable_h,
            "non_billable_fy": non_billable_h,
        },
        "financials": {
            "revenue_invoiced": rev_invoiced,
            "revenue_received": rev_received,
            "employee_cost": emp_cost,
            "expense_cost": exp_cost,
            "total_cost": total_cost,
            "gross_margin": gross_margin,
            "gross_margin_pct": margin_pct,
        },
    }
