"""Hackers Infotech realistic demo data for seed_pmo_demo (Mar–Jul 2026)."""
import datetime

from apps.common.constants import WorkLogCategory
from apps.tickets.models import TicketPriority, TicketType

# ── Billing projects (also created in seed_crm_finance — overrides here) ─────

BILLING_PROJECT_OVERRIDES = [
    {
        "code": "PRJ-260101",
        "name": "ERP Tool",
        "client_code": "HIT-PWR",
        "workflow_slug": "ongoing",
        "manager": "HIT-002",
        "estimated_hours": 1800,
        "budget": 1_800_000,
        "description": "Textile ERP for Powerloop — inventory, production, finance",
        "start_date": datetime.date(2026, 3, 3),
        "end_date": datetime.date(2026, 12, 31),
    },
    {
        "code": "PRJ-260102",
        "name": "Inventory Management System",
        "client_code": "HIT-SSB",
        "workflow_slug": "close",
        "manager": "HIT-002",
        "estimated_hours": 1200,
        "budget": 950_000,
        "description": "Battery warehouse IMS — delivered Apr 2026",
        "start_date": datetime.date(2026, 3, 10),
        "end_date": datetime.date(2026, 4, 30),
    },
    {
        "code": "PRJ-260103",
        "name": "Nexus Tool",
        "client_code": "HIT-PWR",
        "workflow_slug": "kickoff",
        "manager": "HIT-002",
        "estimated_hours": 640,
        "budget": 420_000,
        "description": "Workflow automation toolkit — team learning pilot",
        "start_date": datetime.date(2026, 6, 1),
        "end_date": datetime.date(2026, 9, 30),
    },
    {
        "code": "TRN-260101",
        "name": "Cyber Security Training",
        "client_code": "HIT-KNC",
        "business_prefix": "TRN",
        "workflow_slug": "close",
        "manager": "HIT-001",
        "estimated_hours": 24,
        "budget": 150_000,
        "description": "3-day cyber security workshop at Kongu Nadu College",
        "start_date": datetime.date(2026, 3, 17),
        "end_date": datetime.date(2026, 3, 19),
    },
    {
        "code": "PRJ-260104",
        "name": "VAPT & QA",
        "client_code": "HIT-YMA",
        "workflow_slug": "ongoing",
        "manager": "HIT-003",
        "estimated_hours": 480,
        "budget": 680_000,
        "description": "VAPT assessment and QA automation for YM Automation",
        "start_date": datetime.date(2026, 4, 7),
        "end_date": datetime.date(2026, 8, 31),
    },
]

# ── Non-billing internal projects ───────────────────────────────────────────

NON_BILLING_PROJECTS = [
    {
        "code": "INT-260201",
        "name": "ASM",
        "client_code": "HIT-INT",
        "business_prefix": "INT",
        "workflow_slug": "ongoing",
        "manager": "HIT-003",
        "estimated_hours": 400,
        "budget": 0,
        "description": "Attack surface mapping internal tool",
        "start_date": datetime.date(2026, 3, 1),
        "end_date": datetime.date(2026, 7, 31),
    },
    {
        "code": "INT-260202",
        "name": "QA Generate",
        "client_code": "HIT-INT",
        "business_prefix": "INT",
        "workflow_slug": "ongoing",
        "manager": "HIT-006",
        "estimated_hours": 320,
        "budget": 0,
        "description": "Test case generation assistant for QA team",
        "start_date": datetime.date(2026, 3, 15),
        "end_date": datetime.date(2026, 7, 31),
    },
    {
        "code": "INT-260203",
        "name": "VAPT Tool Automation",
        "client_code": "HIT-INT",
        "business_prefix": "INT",
        "workflow_slug": "ongoing",
        "manager": "HIT-003",
        "estimated_hours": 560,
        "budget": 0,
        "description": "Automated scan orchestration for VAPT engagements",
        "start_date": datetime.date(2026, 4, 1),
        "end_date": datetime.date(2026, 8, 31),
    },
]

# Pre-sales pipeline (enquiry → follow-up → won/lost)
PIPELINE_LEADS = [
    {
        "code": "PRJ-260201",
        "name": "Hospital Management System",
        "client_code": "HIT-PWR",
        "workflow_slug": "enquiry",
        "manager": "HIT-002",
        "estimated_hours": 960,
        "budget": 720_000,
        "description": "Inbound enquiry — OPD & billing module for regional hospital chain",
        "start_date": datetime.date(2026, 5, 12),
        "end_date": datetime.date(2026, 12, 31),
    },
    {
        "code": "PRJ-260202",
        "name": "E-commerce Platform",
        "client_code": "HIT-YMA",
        "workflow_slug": "followup",
        "manager": "HIT-002",
        "estimated_hours": 640,
        "budget": 480_000,
        "description": "Qualified lead — proposal sent, awaiting PO",
        "start_date": datetime.date(2026, 4, 20),
        "end_date": datetime.date(2026, 10, 31),
    },
    {
        "code": "PRJ-260203",
        "name": "Legacy ERP Migration",
        "client_code": "HIT-SSB",
        "workflow_slug": "cancelled",
        "manager": "HIT-002",
        "estimated_hours": 400,
        "budget": 350_000,
        "description": "Dropped — client deferred budget to next FY",
        "start_date": datetime.date(2026, 3, 1),
        "end_date": datetime.date(2026, 6, 30),
    },
    {
        "code": "PRJ-260204",
        "name": "Mobile App MVP",
        "client_code": "HIT-KNC",
        "workflow_slug": "cancelled",
        "manager": "HIT-001",
        "estimated_hours": 200,
        "budget": 180_000,
        "description": "Lost to competitor after technical evaluation",
        "start_date": datetime.date(2026, 2, 10),
        "end_date": datetime.date(2026, 5, 31),
    },
]

ALL_ALLOCATIONS = [
    # ERP Tool
    {"project_code": "PRJ-260101", "username": "HIT-002", "pct": 15, "start_date": datetime.date(2026, 3, 3), "end_date": datetime.date(2026, 12, 31)},
    {"project_code": "PRJ-260101", "username": "HIT-005", "pct": 35, "start_date": datetime.date(2026, 3, 3), "end_date": datetime.date(2026, 12, 31)},
    {"project_code": "PRJ-260101", "username": "HIT-010", "pct": 50, "start_date": datetime.date(2026, 5, 1), "end_date": datetime.date(2026, 12, 31)},
    {"project_code": "PRJ-260101", "username": "HIT-011", "pct": 50, "start_date": datetime.date(2026, 5, 1), "end_date": datetime.date(2026, 12, 31)},
    {"project_code": "PRJ-260101", "username": "HIT-006", "pct": 20, "start_date": datetime.date(2026, 3, 3), "end_date": datetime.date(2026, 12, 31)},
    # IMS (closed Apr 2026 — no overlap with May+ intern allocations)
    {"project_code": "PRJ-260102", "username": "HIT-005", "pct": 25, "start_date": datetime.date(2026, 3, 10), "end_date": datetime.date(2026, 4, 30)},
    {"project_code": "PRJ-260102", "username": "HIT-006", "pct": 30, "start_date": datetime.date(2026, 3, 10), "end_date": datetime.date(2026, 4, 30)},
    # Nexus
    {"project_code": "PRJ-260103", "username": "HIT-005", "pct": 15, "start_date": datetime.date(2026, 6, 1), "end_date": datetime.date(2026, 9, 30)},
    {"project_code": "PRJ-260103", "username": "HIT-009", "pct": 50, "start_date": datetime.date(2026, 6, 1), "end_date": datetime.date(2026, 9, 30)},
    {"project_code": "PRJ-260103", "username": "HIT-012", "pct": 50, "start_date": datetime.date(2026, 6, 5), "end_date": datetime.date(2026, 9, 30)},
    # Training (CEO — short window, standalone)
    {"project_code": "TRN-260101", "username": "HIT-001", "pct": 100, "start_date": datetime.date(2026, 3, 17), "end_date": datetime.date(2026, 3, 19)},
    # VAPT & QA (client)
    {"project_code": "PRJ-260104", "username": "HIT-003", "pct": 25, "start_date": datetime.date(2026, 4, 7), "end_date": datetime.date(2026, 8, 31)},
    {"project_code": "PRJ-260104", "username": "HIT-007", "pct": 40, "start_date": datetime.date(2026, 5, 1), "end_date": datetime.date(2026, 8, 31)},
    {"project_code": "PRJ-260104", "username": "HIT-008", "pct": 50, "start_date": datetime.date(2026, 5, 1), "end_date": datetime.date(2026, 8, 31)},
    {"project_code": "PRJ-260104", "username": "HIT-006", "pct": 30, "start_date": datetime.date(2026, 4, 7), "end_date": datetime.date(2026, 8, 31)},
    # Internal — ASM
    {"project_code": "INT-260201", "username": "HIT-003", "pct": 20, "start_date": datetime.date(2026, 3, 1), "end_date": datetime.date(2026, 7, 31)},
    {"project_code": "INT-260201", "username": "HIT-007", "pct": 35, "start_date": datetime.date(2026, 5, 1), "end_date": datetime.date(2026, 7, 31)},
    {"project_code": "INT-260201", "username": "HIT-008", "pct": 40, "start_date": datetime.date(2026, 5, 1), "end_date": datetime.date(2026, 7, 31)},
    # QA Generate
    {"project_code": "INT-260202", "username": "HIT-006", "pct": 20, "start_date": datetime.date(2026, 3, 15), "end_date": datetime.date(2026, 7, 31)},
    {"project_code": "INT-260202", "username": "HIT-012", "pct": 40, "start_date": datetime.date(2026, 6, 5), "end_date": datetime.date(2026, 7, 31)},
    # VAPT Tool Automation
    {"project_code": "INT-260203", "username": "HIT-003", "pct": 20, "start_date": datetime.date(2026, 4, 1), "end_date": datetime.date(2026, 8, 31)},
    {"project_code": "INT-260203", "username": "HIT-007", "pct": 15, "start_date": datetime.date(2026, 5, 1), "end_date": datetime.date(2026, 8, 31)},
]

# Backward-compatible aliases used by seed_pmo_demo imports
ERP_PROJECT = BILLING_PROJECT_OVERRIDES[0]
TRAINING_PROJECT = BILLING_PROJECT_OVERRIDES[3]
ERP_ALLOCATIONS = [a for a in ALL_ALLOCATIONS if a["project_code"] == "PRJ-260101"]
TRAINING_ALLOCATIONS = [a for a in ALL_ALLOCATIONS if a["project_code"] == "TRN-260101"]

ERP_TICKETS = [
    {
        "key": "erp-e1",
        "project_code": "PRJ-260101",
        "title": "Epic 1 — Requirements & Discovery",
        "type": TicketType.EPIC,
        "workflow_slug": "done",
        "assignee": "HIT-002",
        "reporter": "HIT-002",
        "estimate": 40,
        "description": "Powerloop ERP discovery — workshops, as-is mapping, FRD baseline.",
    },
    {
        "key": "erp-kickoff",
        "parent_key": "erp-e1",
        "project_code": "PRJ-260101",
        "title": "Project kickoff with Powerloop PMO",
        "type": TicketType.STORY,
        "workflow_slug": "done",
        "assignee": "HIT-002",
        "estimate": 4,
        "due_date": datetime.date(2026, 3, 5),
    },
    {
        "key": "erp-frd",
        "parent_key": "erp-e1",
        "project_code": "PRJ-260101",
        "title": "Functional requirements document (FRD)",
        "type": TicketType.TASK,
        "workflow_slug": "done",
        "assignee": "HIT-005",
        "estimate": 16,
    },
    {
        "key": "erp-e2",
        "project_code": "PRJ-260101",
        "title": "Epic 2 — Core ERP Development",
        "type": TicketType.EPIC,
        "workflow_slug": "inprogress",
        "assignee": "HIT-005",
        "estimate": 200,
    },
    {
        "key": "erp-rbac",
        "parent_key": "erp-e2",
        "project_code": "PRJ-260101",
        "title": "User management & RBAC module",
        "type": TicketType.STORY,
        "workflow_slug": "inprogress",
        "assignee": "HIT-010",
        "estimate": 24,
    },
    {
        "key": "erp-inventory",
        "parent_key": "erp-e2",
        "project_code": "PRJ-260101",
        "title": "Textile inventory & stock ledger",
        "type": TicketType.STORY,
        "workflow_slug": "inprogress",
        "assignee": "HIT-011",
        "estimate": 28,
    },
    {
        "key": "erp-login-bug",
        "parent_key": "erp-rbac",
        "project_code": "PRJ-260101",
        "title": "Login redirect loop after SSO timeout",
        "type": TicketType.BUG,
        "workflow_slug": "inprogress",
        "assignee": "HIT-010",
        "priority": TicketPriority.HIGH,
        "estimate": 4,
    },
    {
        "key": "erp-qa",
        "parent_key": "erp-e2",
        "project_code": "PRJ-260101",
        "title": "ERP regression test pack",
        "type": TicketType.TASK,
        "workflow_slug": "inprogress",
        "assignee": "HIT-006",
        "estimate": 16,
    },
]

TRAINING_TICKETS = [
    {
        "key": "trn-d1",
        "project_code": "TRN-260101",
        "title": "Day 1 — Cyber Security fundamentals",
        "type": TicketType.TASK,
        "workflow_slug": "done",
        "assignee": "HIT-001",
        "estimate": 8,
        "due_date": datetime.date(2026, 3, 17),
    },
    {
        "key": "trn-d2",
        "project_code": "TRN-260101",
        "title": "Day 2 — Ethical hacking workshop",
        "type": TicketType.TASK,
        "workflow_slug": "done",
        "assignee": "HIT-001",
        "estimate": 8,
        "due_date": datetime.date(2026, 3, 18),
    },
    {
        "key": "trn-d3",
        "project_code": "TRN-260101",
        "title": "Day 3 — Security hardening & conclusion",
        "type": TicketType.TASK,
        "workflow_slug": "done",
        "assignee": "HIT-001",
        "estimate": 8,
        "due_date": datetime.date(2026, 3, 19),
    },
]

OTHER_TICKETS = [
    {
        "key": "ims-grn",
        "project_code": "PRJ-260102",
        "title": "GRN module & batch tracking",
        "workflow_slug": "done",
        "assignee": "HIT-005",
        "estimate": 20,
    },
    {
        "key": "ims-uat",
        "project_code": "PRJ-260102",
        "title": "SS Battery UAT sign-off",
        "workflow_slug": "done",
        "assignee": "HIT-006",
        "estimate": 8,
        "due_date": datetime.date(2026, 4, 25),
    },
    {
        "key": "nexus-poc",
        "project_code": "PRJ-260103",
        "title": "Nexus workflow engine PoC",
        "workflow_slug": "inprogress",
        "assignee": "HIT-009",
        "estimate": 16,
    },
    {
        "key": "nexus-ui",
        "project_code": "PRJ-260103",
        "title": "Nexus admin UI scaffold",
        "workflow_slug": "todo",
        "assignee": "HIT-012",
        "estimate": 12,
    },
    {
        "key": "vapt-scan",
        "project_code": "PRJ-260104",
        "title": "External VAPT — web application scan",
        "workflow_slug": "inprogress",
        "assignee": "HIT-007",
        "estimate": 16,
    },
    {
        "key": "vapt-report",
        "project_code": "PRJ-260104",
        "title": "VAPT findings report for YM Automation",
        "workflow_slug": "inprogress",
        "assignee": "HIT-003",
        "estimate": 8,
    },
    {
        "key": "vapt-qa-auto",
        "project_code": "PRJ-260104",
        "title": "Playwright smoke suite for client portal",
        "workflow_slug": "todo",
        "assignee": "HIT-008",
        "estimate": 12,
    },
    {
        "key": "asm-mapper",
        "project_code": "INT-260201",
        "title": "Subdomain discovery module",
        "workflow_slug": "inprogress",
        "assignee": "HIT-007",
        "estimate": 14,
    },
    {
        "key": "qa-gen-api",
        "project_code": "INT-260202",
        "title": "Test case generator API",
        "workflow_slug": "inprogress",
        "assignee": "HIT-006",
        "estimate": 10,
    },
    {
        "key": "vapt-auto-scan",
        "project_code": "INT-260203",
        "title": "Nuclei scan orchestration",
        "workflow_slug": "inprogress",
        "assignee": "HIT-003",
        "estimate": 12,
    },
]

ERP_WORK_LOGS = [
    {"username": "HIT-002", "ticket_key": "erp-kickoff", "date": "2026-03-05", "hours": 3, "description": "Powerloop kickoff facilitation"},
    {"username": "HIT-005", "ticket_key": "erp-frd", "date": "2026-03-06", "hours": 6, "description": "FRD — inventory & production sections"},
    {"username": "HIT-005", "ticket_key": "erp-frd", "date": "2026-03-07", "hours": 5, "description": "FRD review with Karthick"},
    {"username": "HIT-010", "ticket_key": "erp-rbac", "date": "2026-06-03", "hours": 6, "description": "RBAC API endpoints"},
    {"username": "HIT-011", "ticket_key": "erp-inventory", "date": "2026-06-04", "hours": 6, "description": "Stock ledger service layer"},
    {"username": "HIT-010", "ticket_key": "erp-login-bug", "date": "2026-06-04", "hours": 4, "description": "SSO redirect loop investigation"},
    {"username": "HIT-006", "ticket_key": "erp-qa", "date": "2026-06-05", "hours": 5, "description": "Auth & inventory smoke tests"},
]

TRAINING_WORK_LOGS = [
    {"username": "HIT-001", "ticket_key": "trn-d1", "date": "2026-03-17", "hours": 8, "description": "Day 1 delivery at Kongu Nadu", "category": WorkLogCategory.TRAINING},
    {"username": "HIT-001", "ticket_key": "trn-d2", "date": "2026-03-18", "hours": 8, "description": "Ethical hacking lab", "category": WorkLogCategory.TRAINING},
    {"username": "HIT-001", "ticket_key": "trn-d3", "date": "2026-03-19", "hours": 8, "description": "Hardening & certificates", "category": WorkLogCategory.TRAINING},
]

OTHER_WORK_LOGS = [
    {"username": "HIT-005", "ticket_key": "ims-grn", "date": "2026-03-20", "hours": 6, "description": "GRN batch module"},
    {"username": "HIT-006", "ticket_key": "ims-uat", "date": "2026-04-22", "hours": 5, "description": "SS Battery UAT support"},
    {"username": "HIT-009", "ticket_key": "nexus-poc", "date": "2026-06-10", "hours": 5, "description": "Workflow engine spike"},
    {"username": "HIT-012", "ticket_key": "nexus-ui", "date": "2026-06-12", "hours": 4, "description": "Admin UI layout"},
    {"username": "HIT-007", "ticket_key": "vapt-scan", "date": "2026-05-20", "hours": 5, "description": "Burp crawl & active scan"},
    {"username": "HIT-008", "ticket_key": "vapt-qa-auto", "date": "2026-05-21", "hours": 4, "description": "Playwright scaffold"},
    {"username": "HIT-003", "ticket_key": "vapt-report", "date": "2026-05-22", "hours": 4, "description": "Draft findings report"},
    {"username": "HIT-007", "ticket_key": "asm-mapper", "date": "2026-05-15", "hours": 4, "description": "Subdomain enum script"},
    {"username": "HIT-006", "ticket_key": "qa-gen-api", "date": "2026-04-10", "hours": 5, "description": "OpenAPI test gen prototype"},
    {"username": "HIT-003", "ticket_key": "vapt-auto-scan", "date": "2026-04-18", "hours": 4, "description": "Nuclei template runner"},
    # Intern timesheet samples — May & June
    {"username": "HIT-009", "ticket_key": "nexus-poc", "date": "2026-05-06", "hours": 4},
    {"username": "HIT-009", "ticket_key": "nexus-poc", "date": "2026-05-07", "hours": 4},
    {"username": "HIT-010", "ticket_key": "erp-rbac", "date": "2026-05-12", "hours": 5},
    {"username": "HIT-010", "ticket_key": "erp-rbac", "date": "2026-05-13", "hours": 5},
    {"username": "HIT-011", "ticket_key": "erp-inventory", "date": "2026-06-02", "hours": 6},
    {"username": "HIT-008", "ticket_key": "vapt-qa-auto", "date": "2026-05-19", "hours": 4},
    {"username": "HIT-008", "ticket_key": "vapt-qa-auto", "date": "2026-05-20", "hours": 4},
]

TICKET_COMMENTS = {
    "erp-kickoff": [
        ("HIT-002", "Kickoff deck shared with Powerloop. Recording on SharePoint.", 60),
        ("HIT-005", "Warehouse walkthrough scheduled Mar 8.", 59),
    ],
    "erp-frd": [
        ("HIT-005", "FRD v1.0 sent for client review.", 55),
        ("HIT-002", "Add non-functional reqs for stock report performance.", 54),
    ],
    "erp-login-bug": [
        ("HIT-010", "Root cause: refresh token not rotated after 30m idle.", 2),
        ("HIT-006", "Verified fix on staging.", 1),
    ],
    "ims-uat": [
        ("HIT-006", "SS Battery signed UAT checklist Apr 25.", 40),
    ],
    "vapt-scan": [
        ("HIT-007", "Critical finding on admin panel — logged as YMA-001.", 15),
        ("HIT-003", "Retest window agreed for Jun 30.", 10),
    ],
    "trn-d3": [
        ("HIT-001", "Training completed. Feedback avg 4.7/5.", 75),
    ],
}

TICKET_HISTORY = {
    "erp-kickoff": [
        {"action": "create", "by": "HIT-002", "at": "2026-03-03T10:00:00", "changes": {}},
        {"action": "update", "by": "HIT-002", "at": "2026-03-05T17:00:00", "changes": {"Status": {"old": "In Progress", "new": "Done"}}},
    ],
    "erp-login-bug": [
        {"action": "create", "by": "HIT-006", "at": "2026-06-03T11:00:00", "changes": {}},
        {"action": "update", "by": "HIT-010", "at": "2026-06-03T14:00:00", "changes": {"Status": {"old": "Todo", "new": "In Progress"}}},
    ],
    "trn-d1": [
        {"action": "create", "by": "HIT-001", "at": "2026-03-15T15:00:00", "changes": {}},
        {"action": "update", "by": "HIT-001", "at": "2026-03-17T18:00:00", "changes": {"Status": {"old": "In Progress", "new": "Done"}}},
    ],
}

# HR-approved leave requests (reviewer HIT-004)
LEAVE_REQUESTS = [
    {"username": "HIT-009", "leave_code": "CL", "start": "2026-05-12", "end": "2026-05-12", "status": "APPROVED", "reason": "Family function in Madurai"},
    {"username": "HIT-010", "leave_code": "SL", "start": "2026-06-16", "end": "2026-06-17", "status": "APPROVED", "reason": "Fever — medical rest"},
    {"username": "HIT-007", "leave_code": "CL", "start": "2026-06-23", "end": "2026-06-23", "status": "APPROVED", "reason": "College convocation"},
    {"username": "HIT-008", "leave_code": "CL", "start": "2026-07-07", "end": "2026-07-07", "status": "PENDING", "reason": "Personal errand"},
    {"username": "HIT-005", "leave_code": "CL", "start": "2026-04-04", "end": "2026-04-04", "status": "APPROVED", "reason": "Client visit travel buffer"},
]

# May 2026 payslips — subset of interns
PAYROLL_MAY_2026 = [
    {"username": "HIT-007", "basic": 8000, "hra": 2000, "allowances": 1500, "present": 22, "leave": 0, "status": "PAID"},
    {"username": "HIT-009", "basic": 8000, "hra": 2000, "allowances": 1500, "present": 21, "leave": 1, "status": "PAID"},
    {"username": "HIT-010", "basic": 8500, "hra": 2000, "allowances": 1500, "present": 22, "leave": 0, "status": "PAID"},
    {"username": "HIT-011", "basic": 8000, "hra": 2000, "allowances": 1500, "present": 22, "leave": 0, "status": "FINALIZED"},
]

TRAINING_FINANCE = None  # handled by seed_crm_finance
