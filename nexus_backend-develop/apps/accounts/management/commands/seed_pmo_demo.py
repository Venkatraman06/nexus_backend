"""
Seed linked PMO demo data: Hackers Infotech billing & internal projects,
allocations, tickets, work logs, timesheets, leaves, intern payroll, and
follow-up calendar demos.

Requires: seed_workflow, migrate_seed_data, seed_crm_finance (for billing clients).

Usage:
    python manage.py seed_pmo_demo
    python manage.py seed_pmo_demo --reset
    python manage.py seed_pmo_demo --dry-run
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from packages.workflow.models import State

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.common.constants import TimesheetStatus, WorkLogCategory
from apps.tickets.models import Ticket, TicketComment, TicketHistory, TicketPriority, TicketType

from .seed_pmo_erp_data import (
    ALL_ALLOCATIONS,
    BILLING_PROJECT_OVERRIDES,
    ERP_TICKETS,
    LEAVE_REQUESTS,
    NON_BILLING_PROJECTS,
    OTHER_TICKETS,
    OTHER_WORK_LOGS,
    PAYROLL_MAY_2026,
    PIPELINE_LEADS,
    TICKET_COMMENTS,
    TICKET_HISTORY,
    TRAINING_TICKETS,
    TRAINING_WORK_LOGS,
    ERP_WORK_LOGS,
)


SEED_PREFIX = "SEED-PMO"


def _week_bounds(anchor: datetime.date) -> tuple[datetime.date, datetime.date]:
    days_since_sunday = (anchor.weekday() + 1) % 7
    sunday = anchor - datetime.timedelta(days=days_since_sunday)
    return sunday, sunday + datetime.timedelta(days=6)


class Command(BaseCommand):
    help = "Seed pipeline projects, allocations, tickets, and timesheets"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--reset", action="store_true", help="Remove seeded PMO demo records")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        reset = options["reset"]

        if reset and not dry:
            self._reset()

        with transaction.atomic():
            emp = self._load_employees(dry)
            if not emp and not dry:
                self.stdout.write(self.style.ERROR(
                    "No employees found. Run migrate_seed_data first."
                ))
                return

            bt = self._ensure_business_types(dry)
            client_map = self._ensure_clients(dry)
            project_map = self._seed_projects(dry, emp, bt, client_map)
            self._seed_allocations(dry, emp, project_map)
            ticket_map = self._seed_tickets(dry, emp, project_map)
            self._seed_comments_and_history(dry, emp, ticket_map)
            self._seed_timesheets(dry, emp, ticket_map)
            self._approve_timesheets(dry, emp)
            self._seed_leaves(dry, emp)
            self._seed_payroll(dry, emp)
            self._seed_followups(dry, emp)

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("\nPMO demo seeding complete."))

    def _log(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def _reset(self):
        from apps.allocation.models import Allocation
        from apps.projects.models import Project
        from apps.workitems.models import WorkLog

        from django.db.models import Q

        billing_codes = [p["code"] for p in BILLING_PROJECT_OVERRIDES]
        internal_codes = [p["code"] for p in NON_BILLING_PROJECTS]
        pipeline_codes = [p["code"] for p in PIPELINE_LEADS]
        codes = billing_codes + internal_codes + pipeline_codes
        projects = Project.objects.filter(Q(code__in=codes) | Q(code__startswith="INT-260"))
        WorkLog.objects.filter(remarks=SEED_PREFIX).delete()
        TicketComment.objects.filter(body__startswith="[SEED]").delete()
        Ticket.objects.filter(project__in=projects).delete()
        Allocation.objects.filter(project__in=projects).delete()
        projects.filter(code__in=internal_codes + pipeline_codes).delete()

        from apps.followups.models import FollowUp
        FollowUp.objects.filter(title__startswith=f"[{SEED_PREFIX}]").delete()

        self._log("  Reset: removed seeded PMO projects and related data")

    def _load_employees(self, dry):
        if dry:
            return {u: u for u in (
                "HIT-001", "HIT-002", "HIT-003", "HIT-004", "HIT-005",
                "HIT-006", "HIT-007", "HIT-008", "HIT-009", "HIT-010",
                "HIT-011", "HIT-012",
            )}
        from apps.accounts.models import Employee
        usernames = [
            "HIT-001", "HIT-002", "HIT-003", "HIT-004", "HIT-005",
            "HIT-006", "HIT-007", "HIT-008", "HIT-009", "HIT-010",
            "HIT-011", "HIT-012",
        ]
        return {u: Employee.objects.get(username=u) for u in usernames}

    def _project_ct(self):
        return ContentType.objects.get(app_label="projects", model="project")

    def _ticket_ct(self):
        return ContentType.objects.get(app_label="tickets", model="ticket")

    def _state(self, ct, slug):
        return State.objects.get(content_type=ct, slug=slug)

    def _ensure_business_types(self, dry):
        if dry:
            return {"PRJ": None, "INT": None, "TRN": None}
        from apps.master.models import BusinessType, BillingType
        BillingType.objects.get_or_create(name="Fixed Price", defaults={"is_active": True})
        BillingType.objects.get_or_create(name="Internal", defaults={"is_active": True})
        types = {}
        for name, prefix in (("Project", "PRJ"), ("Internal", "INT"), ("Training", "TRN")):
            bt, _ = BusinessType.objects.get_or_create(
                name=name, defaults={"prefix": prefix, "is_active": True},
            )
            types[prefix] = bt
        return types

    def _ensure_clients(self, dry):
        from apps.master.models import ClientCategory
        from apps.projects.models import Client

        if dry:
            return {
                "HIT-PWR": "x", "HIT-SSB": "x", "HIT-KNC": "x",
                "HIT-YMA": "x", "HIT-INT": "x",
            }

        cat, _ = ClientCategory.objects.get_or_create(name="Internal", defaults={"is_active": True})
        client, created = Client.objects.get_or_create(
            name="Hackers InfoTech (Internal)",
            defaults={
                "code": "HIT-INT",
                "contact_person": "Chandraprakash Sankar",
                "contact_email": "chandraprakash@hackersinfotech.com",
                "phone": "+91 422 000 0000",
                "address": "Coimbatore, Tamil Nadu",
                "formatted_address": "Coimbatore, Tamil Nadu",
                "latitude": Decimal("11.0168"),
                "longitude": Decimal("76.9558"),
                "category": cat,
                "is_active": True,
            },
        )
        self._log(f"  {'Created' if created else 'Exists '} internal client: {client.name}")

        client_map = {"HIT-INT": client}
        for code in ("HIT-PWR", "HIT-SSB", "HIT-KNC", "HIT-YMA"):
            try:
                client_map[code] = Client.objects.get(code=code)
            except Client.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  [WARN] Client {code} not found — run seed_crm_finance"
                ))
        return client_map

    def _seed_projects(self, dry, emp, bt, client_map):
        from apps.master.models import BillingType
        from apps.projects.models import Client, Project

        today = datetime.date.today()
        project_ct = self._project_ct()
        project_map = {}

        specs = BILLING_PROJECT_OVERRIDES + NON_BILLING_PROJECTS + PIPELINE_LEADS
        if dry:
            return {s["code"]: s for s in specs}

        billing_fixed = BillingType.objects.get(name="Fixed Price")
        billing_internal = BillingType.objects.filter(name="Internal").first() or billing_fixed

        for cfg in specs:
            client = client_map.get(cfg["client_code"])
            if client is None and cfg["client_code"] != "HIT-PWR":
                # Billing projects may already exist from CRM with client linked
                try:
                    from apps.projects.models import Project as P
                    existing = P.objects.get(code=cfg["code"])
                    client = existing.client
                except Exception:
                    pass
            if client is None:
                try:
                    client = Client.objects.get(code=cfg["client_code"])
                    client_map[cfg["client_code"]] = client
                except Client.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"  [WARN] Skipping {cfg['code']} — client {cfg['client_code']} missing"
                    ))
                    continue

            prefix = cfg.get("business_prefix", "TRN" if cfg["code"].startswith("TRN-") else "PRJ")
            if cfg["code"].startswith("INT-"):
                prefix = "INT"
            business_type = bt.get(prefix)
            billing = billing_internal if prefix in ("INT",) else billing_fixed
            if cfg["code"].startswith("TRN-"):
                billing = billing_fixed
            wf = self._state(project_ct, cfg["workflow_slug"])

            defaults = {
                "name": cfg["name"],
                "description": cfg.get("description", ""),
                "client": client,
                "business_type": business_type,
                "billing_type": billing,
                "estimated_hours": Decimal(str(cfg["estimated_hours"])),
                "budget": Decimal(str(cfg.get("budget", 0))),
                "start_date": cfg.get("start_date", today - datetime.timedelta(days=30)),
                "end_date": cfg.get("end_date", today + datetime.timedelta(days=180)),
                "workflow_state": wf,
                "manager": emp.get(cfg.get("manager", "HIT-002")),
                "is_active": True,
            }
            project, created = Project.objects.get_or_create(code=cfg["code"], defaults=defaults)
            if not created:
                for k, v in defaults.items():
                    if v is not None:
                        setattr(project, k, v)
                project.save()
            project_map[cfg["code"]] = project
            self._log(
                f"  {'Created' if created else 'Updated'} project: "
                f"{project.code} [{cfg['workflow_slug']}]"
            )

        return project_map

    def _seed_allocations(self, dry, emp, project_map):
        from django.core.exceptions import ValidationError

        from apps.allocation.models import Allocation

        created = skipped = 0
        # Seed earlier-start allocations first so overlap validation stays predictable
        sorted_cfgs = sorted(ALL_ALLOCATIONS, key=lambda c: (c["start_date"], c["username"]))
        for cfg in sorted_cfgs:
            if dry:
                created += 1
                continue
            project = project_map.get(cfg["project_code"])
            employee = emp.get(cfg["username"])
            if not project or not employee:
                skipped += 1
                continue
            pct = Decimal(str(cfg["pct"]))
            defaults = {
                "allocation_percentage": pct,
                "end_date": cfg.get("end_date"),
                "notes": f"{SEED_PREFIX} allocation",
            }
            try:
                _, c = Allocation.objects.get_or_create(
                    employee=employee,
                    project=project,
                    start_date=cfg["start_date"],
                    defaults=defaults,
                )
                if c:
                    created += 1
            except ValidationError as exc:
                self.stdout.write(self.style.WARNING(
                    f"  [WARN] Skipped allocation {cfg['username']} → {cfg['project_code']}: {exc.messages[0]}"
                ))
                skipped += 1
        self._log(f"  Allocations: {created} created, {skipped} skipped")

    def _all_ticket_specs(self):
        return ERP_TICKETS + TRAINING_TICKETS + OTHER_TICKETS

    def _upsert_ticket(self, cfg, emp, project_map, ticket_map, ticket_ct):
        project = project_map.get(cfg["project_code"])
        if not project:
            return None, False

        parent = None
        if cfg.get("parent_key"):
            parent = ticket_map.get(cfg["parent_key"])
            if parent is None:
                return None, False

        wf = self._state(ticket_ct, cfg["workflow_slug"])
        defaults = {
            "title": cfg["title"],
            "description": cfg.get("description", ""),
            "type": cfg.get("type", TicketType.TASK),
            "workflow_state": wf,
            "priority": cfg.get("priority", TicketPriority.MEDIUM),
            "assignee": emp.get(cfg["assignee"]),
            "reporter": emp.get(cfg.get("reporter", "HIT-002")),
            "due_date": cfg.get("due_date"),
            "original_estimate": Decimal(str(cfg.get("estimate", 8))),
            "approved": cfg.get("approved", True),
            "parent": parent,
        }
        ticket, c = Ticket.objects.get_or_create(
            project=project,
            title=cfg["title"],
            defaults=defaults,
        )
        if not c:
            for k, v in defaults.items():
                setattr(ticket, k, v)
            ticket.save()
        return ticket, c

    def _seed_tickets(self, dry, emp, project_map):
        ticket_ct = self._ticket_ct()
        ticket_map = {}
        created = 0
        specs = self._all_ticket_specs()

        if dry:
            return {s["key"]: s for s in specs}

        # Parents before children (epics → stories → tasks)
        remaining = list(specs)
        for _ in range(len(specs) + 1):
            if not remaining:
                break
            next_remaining = []
            for cfg in remaining:
                if cfg.get("parent_key") and cfg["parent_key"] not in ticket_map:
                    next_remaining.append(cfg)
                    continue
                ticket, c = self._upsert_ticket(cfg, emp, project_map, ticket_map, ticket_ct)
                if ticket:
                    ticket_map[cfg["key"]] = ticket
                    if c:
                        created += 1
            remaining = next_remaining

        if remaining:
            self.stdout.write(self.style.WARNING(
                f"  [WARN] {len(remaining)} ticket(s) skipped — parent not resolved"
            ))

        self._log(f"  Tickets: {created} created, {len(ticket_map)} total")
        return ticket_map

    def _seed_comments_and_history(self, dry, emp, ticket_map):
        comments_created = history_created = 0

        if dry:
            for key in TICKET_COMMENTS:
                comments_created += len(TICKET_COMMENTS[key])
            for key in TICKET_HISTORY:
                history_created += len(TICKET_HISTORY[key])
            self._log(f"  Comments: {comments_created} | History: {history_created} entries (dry-run)")
            return

        for ticket_key, rows in TICKET_COMMENTS.items():
            ticket = ticket_map.get(ticket_key)
            if not ticket:
                continue
            for author_username, body, _days in rows:
                full_body = f"[SEED] {body}"
                if TicketComment.objects.filter(ticket=ticket, body=full_body).exists():
                    continue
                author = emp.get(author_username)
                TicketComment.objects.create(
                    ticket=ticket,
                    author=author,
                    body=full_body,
                )
                comments_created += 1

        for ticket_key, entries in TICKET_HISTORY.items():
            ticket = ticket_map.get(ticket_key)
            if not ticket:
                continue
            for entry in entries:
                changed_by = emp.get(entry["by"])
                at = parse_datetime(entry["at"])
                if at and timezone.is_naive(at):
                    at = timezone.make_aware(at)
                if TicketHistory.objects.filter(ticket=ticket, action=entry["action"], changes=entry.get("changes", {})).exists():
                    continue
                hist = TicketHistory.objects.create(
                    ticket=ticket,
                    action=entry["action"],
                    changes=entry.get("changes", {}),
                    changed_by=changed_by,
                )
                if at:
                    TicketHistory.objects.filter(pk=hist.pk).update(changed_at=at)
                history_created += 1

        seeded_keys = {t["key"] for t in ERP_TICKETS + TRAINING_TICKETS + OTHER_TICKETS}
        for ticket_key, ticket in ticket_map.items():
            if ticket_key not in seeded_keys:
                continue
            if TicketHistory.objects.filter(ticket=ticket, action="create").exists():
                continue
            assignee = ticket.assignee
            TicketHistory.objects.create(
                ticket=ticket,
                action="create",
                changed_by=assignee or ticket.reporter,
                changes={
                    "Title": {"old": None, "new": ticket.title},
                    "Status": {"old": None, "new": ticket.workflow_state.name if ticket.workflow_state else None},
                    "Assignee": {"old": None, "new": assignee.full_name if assignee else None},
                },
            )
            history_created += 1

        self._log(f"  Comments: {comments_created} created | History: {history_created} entries")

    def _approve_timesheets(self, dry, emp):
        from apps.timesheets.models import WeeklyTimesheet, TimesheetReviewLog

        manager = emp.get("HIT-002")
        if not manager and not dry:
            return

        approved = 0
        cutoff = datetime.date(2026, 6, 30)
        if dry:
            self._log("  Timesheets: approve submitted weeks through Jun 2026 (dry-run)")
            return

        qs = WeeklyTimesheet.objects.filter(
            week_start__lte=cutoff,
            total_hours__gt=0,
            is_deleted=False,
        ).exclude(status=TimesheetStatus.APPROVED)

        now = timezone.now()
        for sheet in qs:
            sheet.status = TimesheetStatus.APPROVED
            sheet.submitted_at = sheet.submitted_at or now
            sheet.reviewed_at = now
            sheet.reviewed_by = manager
            sheet.review_comment = "Approved — demo seed (Karthicksankar)"
            sheet.save(update_fields=[
                "status", "submitted_at", "reviewed_at", "reviewed_by", "review_comment", "updated_at",
            ])
            TimesheetReviewLog.objects.get_or_create(
                weekly_timesheet=sheet,
                action="APPROVE",
                performed_by=manager,
                defaults={"comment": sheet.review_comment},
            )
            approved += 1
        self._log(f"  Timesheets: {approved} weeks approved by manager")

    def _seed_leaves(self, dry, emp):
        from apps.attendance.models import LeaveRequest, LeaveRequestStatus, LeaveType

        hr = emp.get("HIT-004")
        created = 0
        if dry:
            self._log(f"  Leaves: {len(LEAVE_REQUESTS)} requests (dry-run)")
            return

        for cfg in LEAVE_REQUESTS:
            employee = emp.get(cfg["username"])
            if not employee:
                continue
            lt, _ = LeaveType.objects.get_or_create(
                code=cfg["leave_code"],
                defaults={
                    "name": {"CL": "Casual Leave", "SL": "Sick Leave"}.get(cfg["leave_code"], cfg["leave_code"]),
                    "max_days": 12,
                    "is_paid": True,
                },
            )
            start = datetime.date.fromisoformat(cfg["start"])
            end = datetime.date.fromisoformat(cfg["end"])
            status = getattr(LeaveRequestStatus, cfg["status"], LeaveRequestStatus.PENDING)
            if LeaveRequest.objects.filter(
                employee=employee, start_date=start, end_date=end, is_deleted=False,
            ).exists():
                continue
            LeaveRequest.objects.create(
                employee=employee,
                leave_type=lt,
                start_date=start,
                end_date=end,
                status=status,
                reason=cfg.get("reason", "Demo leave"),
                reviewer=hr if status == LeaveRequestStatus.APPROVED else None,
                reviewer_remarks="Approved by HR" if status == LeaveRequestStatus.APPROVED else "",
            )
            created += 1
        self._log(f"  Leaves: {created} requests seeded (HR reviewer: HIT-004)")

    def _seed_payroll(self, dry, emp):
        from apps.payroll.models import Payroll, PayrollStatus, PaymentMode

        created = 0
        if dry:
            self._log(f"  Payroll: {len(PAYROLL_MAY_2026)} May 2026 intern payslips (dry-run)")
            return

        for cfg in PAYROLL_MAY_2026:
            employee = emp.get(cfg["username"])
            if not employee:
                continue
            status = getattr(PayrollStatus, cfg["status"], PayrollStatus.DRAFT)
            basic = Decimal(str(cfg["basic"]))
            pf = (basic * Decimal("0.12")).quantize(Decimal("0.01"))
            _, c = Payroll.objects.get_or_create(
                employee=employee,
                month=5,
                year=2026,
                defaults={
                    "basic_salary": basic,
                    "hra": Decimal(str(cfg["hra"])),
                    "allowances": Decimal(str(cfg["allowances"])),
                    "pf": pf,
                    "working_days": 22,
                    "present_days": cfg["present"],
                    "leave_days": cfg["leave"],
                    "status": status,
                    "payment_mode": PaymentMode.BANK_TRANSFER,
                    "bank_name": "Indian Bank",
                    "account_number": f"XXXX{employee.username[-3:]}",
                },
            )
            if c:
                created += 1
        self._log(f"  Payroll: {created} May 2026 intern payslips")

    def _seed_timesheets(self, dry, emp, ticket_map):
        from apps.timesheets.models import WeeklyTimesheet
        from apps.workitems.models import WorkLog

        today = datetime.date.today()
        logs_created = sheets_created = 0

        for cfg in WORK_LOGS:
            if dry:
                logs_created += 1
                continue

            employee = emp.get(cfg["username"])
            ticket = ticket_map.get(cfg["ticket_key"])
            if not employee or not ticket:
                continue

            log_date = cfg["date"]
            if isinstance(log_date, str):
                log_date = datetime.date.fromisoformat(log_date)

            week_start, week_end = _week_bounds(log_date)
            sheet, sc = WeeklyTimesheet.objects.get_or_create(
                employee=employee,
                week_start=week_start,
                defaults={
                    "week_end": week_end,
                    "status": cfg.get("sheet_status", TimesheetStatus.DRAFT),
                    "expected_hours": Decimal("40"),
                },
            )
            if sc:
                sheets_created += 1

            _, lc = WorkLog.objects.get_or_create(
                employee=employee,
                ticket=ticket,
                log_date=log_date,
                defaults={
                    "hours": Decimal(str(cfg["hours"])),
                    "description": cfg.get("description", "Demo work log"),
                    "category": cfg.get("category", WorkLogCategory.BILLABLE),
                    "weekly_timesheet": sheet,
                    "remarks": SEED_PREFIX,
                },
            )
            if lc:
                logs_created += 1
                sheet.total_hours = (
                    WorkLog.objects.filter(weekly_timesheet=sheet, is_deleted=False)
                    .aggregate(total=Sum("hours"))["total"] or Decimal("0")
                )
                sheet.save(update_fields=["total_hours"])

        self._log(f"  Work logs: {logs_created} created | Weekly sheets: {sheets_created} created")

    def _seed_followups(self, dry, emp):
        from apps.followups.models import FollowUp
        from apps.followups.workflow import ensure_followup_workflow

        specs = build_followup_demo_specs()
        if dry:
            self._log(f"  Follow-ups: {len(specs)} demo records (dry-run)")
            return

        ensure_followup_workflow()
        followup_ct = ContentType.objects.get(app_label="followups", model="followup")

        created = updated = skipped = 0
        for cfg in specs:
            assignee = emp.get(cfg["assignee"])
            reporter = emp.get(cfg.get("reporter", cfg["assignee"]))
            if not assignee or not reporter:
                skipped += 1
                continue

            wf = self._state(followup_ct, cfg.get("workflow_slug", "planning"))
            defaults = {
                "type": cfg["type"],
                "priority": cfg["priority"],
                "description": cfg.get("description", ""),
                "comments": cfg.get("comments", SEED_PREFIX),
                "assignee": assignee,
                "reporter": reporter,
                "due_date": cfg["due_date"],
                "start_time": cfg.get("start_time"),
                "end_time": cfg.get("end_time"),
                "workflow_state": wf,
                "created_by": reporter,
                "updated_by": reporter,
            }
            obj, c = FollowUp.objects.update_or_create(
                title=cfg["title"],
                defaults=defaults,
            )
            if c:
                created += 1
            else:
                updated += 1

        self._log(
            f"  Follow-ups: {created} created, {updated} updated, {skipped} skipped "
            f"(Chandraprakash, Karthick, Dharshika, Madhan)"
        )


WORK_LOGS = ERP_WORK_LOGS + TRAINING_WORK_LOGS + OTHER_WORK_LOGS

# ── Follow-up calendar demo (Chandraprakash, Karthick, Dharshika, Madhan) ───

FOLLOWUP_DEMO_USERS = ("HIT-001", "HIT-002", "HIT-009", "HIT-008")

FOLLOWUP_TOPICS = [
    ("Powerloop ERP sprint review", "MEETING", "IMPORTANT"),
    ("SSB IMS handover call", "CALL", "HIGH"),
    ("KPR Arts cyber security training prep", "MEETING", "IMPORTANT"),
    ("Nexus tool architecture walkthrough", "MEETING", "HIGH"),
    ("Client invoice follow-up — Powerloop", "EMAIL", "HIGH"),
    ("Weekly PMO stand-up", "MEETING", "MEDIUM"),
    ("ERP UAT defect triage", "CALL", "HIGH"),
    ("Intern progress check-in", "CALL", "MEDIUM"),
    ("Full-stack code review session", "MEETING", "MEDIUM"),
    ("Security lab exercise debrief", "WHATSAPP", "LOW"),
    ("Site visit — Powerloop plant floor", "SITE_VISIT", "IMPORTANT"),
    ("YMA pipeline discovery call", "CALL", "MEDIUM"),
    ("Training deck review", "EMAIL", "MEDIUM"),
    ("Sprint planning — inventory module", "MEETING", "HIGH"),
    ("Stakeholder demo rehearsal", "MEETING", "IMPORTANT"),
    ("WhatsApp client status update", "WHATSAPP", "LOW"),
    ("QA sign-off discussion", "CALL", "MEDIUM"),
    ("Timesheet approval reminder", "EMAIL", "LOW"),
    ("Cyber lab setup verification", "SITE_VISIT", "MEDIUM"),
    ("API integration checkpoint", "MEETING", "HIGH"),
    ("Budget review with management", "MEETING", "IMPORTANT"),
    ("Intern onboarding follow-up", "CALL", "MEDIUM"),
    ("Release notes review", "EMAIL", "LOW"),
    ("Post-training feedback call", "CALL", "MEDIUM"),
    ("New UI mockup review", "MEETING", "HIGH"),
    ("Database migration dry run", "MEETING", "HIGH"),
    ("Client escalation — priority bug", "CALL", "IMPORTANT"),
    ("Vendor payment confirmation", "EMAIL", "MEDIUM"),
    ("Team retrospective", "MEETING", "MEDIUM"),
    ("OWASP training recap", "MEETING", "MEDIUM"),
]

FOLLOWUP_TIME_SLOTS = [
    None,
    (9, 0, 10, 0),
    (10, 30, 11, 30),
    (11, 0, 12, 0),
    (14, 0, 15, 0),
    (15, 30, 16, 30),
    (16, 0, 17, 0),
    (17, 30, 18, 30),
]

FOLLOWUP_WORKFLOW_ROTATION = (
    "planning", "planning", "inprogress", "inprogress", "completed", "planning",
)


def build_followup_demo_specs() -> list[dict]:
    """Build ~90 follow-ups spread across May–Aug 2026 for calendar demos."""
    specs: list[dict] = []
    start = datetime.date(2026, 5, 20)
    end = datetime.date(2026, 8, 15)
    day = start
    topic_idx = 0
    user_idx = 0
    slot_idx = 0
    state_idx = 0
    seq = 1

    reporters = {
        "HIT-001": "HIT-002",
        "HIT-002": "HIT-001",
        "HIT-008": "HIT-003",
        "HIT-009": "HIT-005",
    }

    while day <= end:
        for _ in range(2):
            assignee = FOLLOWUP_DEMO_USERS[user_idx % len(FOLLOWUP_DEMO_USERS)]
            user_idx += 1
            topic, ftype, priority = FOLLOWUP_TOPICS[topic_idx % len(FOLLOWUP_TOPICS)]
            topic_idx += 1
            slot = FOLLOWUP_TIME_SLOTS[slot_idx % len(FOLLOWUP_TIME_SLOTS)]
            slot_idx += 1
            state = FOLLOWUP_WORKFLOW_ROTATION[state_idx % len(FOLLOWUP_WORKFLOW_ROTATION)]
            state_idx += 1

            reporter = reporters.get(assignee, "HIT-002")
            if assignee == "HIT-001":
                reporter = "HIT-002" if seq % 2 else "HIT-009"
            elif assignee == "HIT-002":
                reporter = "HIT-001" if seq % 2 else "HIT-008"

            cfg = {
                "title": f"[{SEED_PREFIX}] {topic} #{seq:03d}",
                "type": ftype,
                "priority": priority,
                "description": (
                    f"Demo follow-up for calendar testing — {topic.lower()} "
                    f"scheduled on {day.isoformat()}."
                ),
                "comments": SEED_PREFIX,
                "assignee": assignee,
                "reporter": reporter,
                "due_date": day,
                "workflow_slug": state,
            }
            if slot:
                cfg["start_time"] = datetime.time(slot[0], slot[1])
                cfg["end_time"] = datetime.time(slot[2], slot[3])
            specs.append(cfg)
            seq += 1

        day += datetime.timedelta(days=1)

    extras = [
        {
            "title": f"[{SEED_PREFIX}] New UI design review",
            "type": "MEETING",
            "priority": "IMPORTANT",
            "description": "Review pending follow-up UI and calendar layout with Dharshika.",
            "assignee": "HIT-009",
            "reporter": "HIT-002",
            "due_date": datetime.date(2026, 6, 11),
            "start_time": datetime.time(10, 0),
            "end_time": datetime.time(11, 0),
            "workflow_slug": "planning",
        },
        {
            "title": f"[{SEED_PREFIX}] Meet Karthick — scope alignment",
            "type": "MEETING",
            "priority": "HIGH",
            "description": "Timed calendar block for week view demo.",
            "assignee": "HIT-002",
            "reporter": "HIT-001",
            "due_date": datetime.date(2026, 6, 10),
            "start_time": datetime.time(13, 30),
            "end_time": datetime.time(14, 30),
            "workflow_slug": "inprogress",
        },
        {
            "title": f"[{SEED_PREFIX}] KPR Arts Cyber Security Training — Day 1",
            "type": "MEETING",
            "priority": "IMPORTANT",
            "description": "Multi-day training block — all-day entries on calendar.",
            "assignee": "HIT-001",
            "reporter": "HIT-002",
            "due_date": datetime.date(2026, 6, 7),
            "workflow_slug": "inprogress",
        },
        {
            "title": f"[{SEED_PREFIX}] KPR Arts Cyber Security Training — Day 2",
            "type": "MEETING",
            "priority": "IMPORTANT",
            "description": "Multi-day training block — day 2.",
            "assignee": "HIT-001",
            "reporter": "HIT-002",
            "due_date": datetime.date(2026, 6, 8),
            "workflow_slug": "inprogress",
        },
        {
            "title": f"[{SEED_PREFIX}] KPR Arts Cyber Security Training — Day 3",
            "type": "MEETING",
            "priority": "IMPORTANT",
            "description": "Multi-day training block — day 3.",
            "assignee": "HIT-001",
            "reporter": "HIT-002",
            "due_date": datetime.date(2026, 6, 9),
            "workflow_slug": "inprogress",
        },
        {
            "title": f"[{SEED_PREFIX}] Madhan — security lab report",
            "type": "CALL",
            "priority": "MEDIUM",
            "description": "Intern deliverable follow-up.",
            "assignee": "HIT-008",
            "reporter": "HIT-003",
            "due_date": datetime.date(2026, 6, 12),
            "start_time": datetime.time(9, 30),
            "end_time": datetime.time(10, 0),
            "workflow_slug": "planning",
        },
        {
            "title": f"[{SEED_PREFIX}] Chandraprakash — board review",
            "type": "MEETING",
            "priority": "IMPORTANT",
            "description": "Executive review of Q2 delivery.",
            "assignee": "HIT-001",
            "reporter": "HIT-002",
            "due_date": datetime.date(2026, 6, 15),
            "start_time": datetime.time(11, 0),
            "end_time": datetime.time(12, 30),
            "workflow_slug": "planning",
        },
    ]
    specs.extend(extras)
    return specs
