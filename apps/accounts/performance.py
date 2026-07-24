"""Build the per-employee ticket performance report (logged vs estimated hours)."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from apps.tickets.models import Ticket
from apps.workitems.models import WorkLog


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_month(d: date) -> date:
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1)
    return d.replace(month=d.month + 1)


def _flag_for(pct: float | None, is_done: bool) -> str | None:
    if not is_done or pct is None:
        return None
    if pct > 100:
        return "red"
    if pct < 90:
        return "green"
    return "normal"


def build_employee_performance(employee, period: str, from_date: date, to_date: date) -> dict:
    logs = (
        WorkLog.objects.filter(
            employee=employee,
            is_deleted=False,
            ticket__isnull=False,
            log_date__gte=from_date,
            log_date__lte=to_date,
        )
        .select_related("ticket", "ticket__workflow_state", "ticket__project")
    )

    ticket_logged: dict = defaultdict(Decimal)
    ticket_weeks: dict = defaultdict(set)
    week_logged: dict = defaultdict(Decimal)
    tickets_by_id: dict = {}

    for log in logs:
        ticket = log.ticket
        tickets_by_id[ticket.id] = ticket
        ticket_logged[ticket.id] += log.hours
        wk = _week_start(log.log_date)
        ticket_weeks[ticket.id].add(wk)
        week_logged[wk] += log.hours

    # Spread each ticket's estimate evenly across the weeks it was actually worked on,
    # so the timeline chart has a comparable "planned vs actual" line per bucket.
    week_estimated: dict = defaultdict(Decimal)
    for ticket_id, weeks in ticket_weeks.items():
        ticket = tickets_by_id[ticket_id]
        if not weeks:
            continue
        share = (ticket.original_estimate or Decimal("0")) / len(weeks)
        for wk in weeks:
            week_estimated[wk] += share

    # ── Ticket-level table / bars ────────────────────────────────────────
    tickets_rows = []
    for ticket_id, logged in ticket_logged.items():
        ticket = tickets_by_id[ticket_id]
        estimate = ticket.original_estimate or Decimal("0")
        is_done = bool(ticket.workflow_state and ticket.workflow_state.is_final)
        pct = round(float(logged) / float(estimate) * 100, 1) if estimate else None
        flag = _flag_for(pct, is_done)
        tickets_rows.append({
            "ticket_id": ticket.ticket_id,
            "ticket_uuid": str(ticket.id),
            "title": ticket.title,
            "project": ticket.project.code if ticket.project_id else "",
            "estimate": float(estimate),
            "total_estimate": float(estimate),
            "logged": float(logged),
            "pct": pct,
            "flag": flag,
            "status": ticket.workflow_state.name if ticket.workflow_state else "",
            "is_done": is_done,
            "completion_date": ticket.updated_at.date().isoformat() if is_done else None,
        })
    tickets_rows.sort(key=lambda r: r["logged"], reverse=True)

    summary = {
        "tickets_completed": sum(1 for r in tickets_rows if r["is_done"]),
        "tickets_in_progress": sum(1 for r in tickets_rows if not r["is_done"]),
        "green": sum(1 for r in tickets_rows if r["flag"] == "green"),
        "normal": sum(1 for r in tickets_rows if r["flag"] == "normal"),
        "red": sum(1 for r in tickets_rows if r["flag"] == "red"),
        "total_logged": round(sum(r["logged"] for r in tickets_rows), 1),
        "total_estimated": round(sum(r["estimate"] for r in tickets_rows), 1),
    }

    ticket_bars = [{
        "ticket_id": r["ticket_id"],
        "title": r["title"],
        "label": r["ticket_id"],
        "logged": r["logged"],
        "estimated": r["estimate"],
        "flag": r["flag"],
        "is_done": r["is_done"],
    } for r in tickets_rows[:12]]

    # ── Timeline / chart series ──────────────────────────────────────────
    timeline = []
    chart_series = []

    if period == "month":
        cursor = _month_start(from_date)
        end = _month_start(to_date)
        while cursor <= end:
            next_month = _add_month(cursor)
            weeks_in_month = {
                wk for wk in week_logged
                if cursor <= wk < next_month
            } | {
                wk for wk in week_estimated
                if cursor <= wk < next_month
            }
            active_weeks = len(weeks_in_month) or 1
            logged_total = sum(week_logged.get(wk, Decimal("0")) for wk in weeks_in_month)
            estimated_total = sum(week_estimated.get(wk, Decimal("0")) for wk in weeks_in_month)
            avg_logged = round(float(logged_total) / active_weeks, 1)
            avg_estimated = round(float(estimated_total) / active_weeks, 1)
            label = cursor.strftime("%b %Y")
            timeline.append({
                "key": cursor.isoformat(),
                "label": label,
                "logged_hours": avg_logged,
                "estimated_hours": avg_estimated,
                "flags": [],
            })
            chart_series.append({
                "period": label,
                "key": cursor.isoformat(),
                "logged": avg_logged,
                "estimated": avg_estimated,
                "green": 0,
                "red": 0,
                "monthly_avg_logged": avg_logged,
                "monthly_avg_estimated": avg_estimated,
            })
            cursor = next_month
    else:
        cursor = _week_start(from_date)
        end = _week_start(to_date)
        while cursor <= end:
            logged = float(week_logged.get(cursor, Decimal("0")))
            estimated = float(week_estimated.get(cursor, Decimal("0")))
            label = cursor.strftime("%d %b")
            flags = [{
                "ticket_id": r["ticket_id"],
                "title": r["title"],
                "flag": r["flag"] or "normal",
                "logged": r["logged"],
                "estimate": r["estimate"],
            } for r in tickets_rows
                if r["is_done"] and r["completion_date"]
                and _week_start(date.fromisoformat(r["completion_date"])) == cursor]
            timeline.append({
                "key": cursor.isoformat(),
                "label": label,
                "logged_hours": logged,
                "estimated_hours": estimated,
                "flags": flags,
            })
            chart_series.append({
                "period": label,
                "key": cursor.isoformat(),
                "logged": logged,
                "estimated": estimated,
                "green": sum(1 for f in flags if f["flag"] == "green"),
                "red": sum(1 for f in flags if f["flag"] == "red"),
            })
            cursor += timedelta(days=7)

    # ── Monthly average (per active week) — supplementary stat for week view ──
    monthly_avg_series = []
    month_cursor = _month_start(from_date)
    month_end = _month_start(to_date)
    while month_cursor <= month_end:
        next_month = _add_month(month_cursor)
        weeks_in_month = [wk for wk in week_logged if month_cursor <= wk < next_month]
        active_weeks = len(weeks_in_month) or 1
        logged_total = sum(week_logged.get(wk, Decimal("0")) for wk in weeks_in_month)
        estimated_total = sum(week_estimated.get(wk, Decimal("0")) for wk in weeks_in_month)
        monthly_avg_series.append({
            "month": f"{month_cursor.strftime('%b %Y')} (avg/wk)",
            "avg_logged": round(float(logged_total) / active_weeks, 1),
            "avg_estimated": round(float(estimated_total) / active_weeks, 1),
        })
        month_cursor = next_month

    return {
        "period": period,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "summary": summary,
        "timeline": timeline,
        "chart_series": chart_series,
        "monthly_avg_series": monthly_avg_series,
        "ticket_bars": ticket_bars,
        "tickets": tickets_rows,
    }
