"""
Seed dummy data for the CRM & Finance menu:
  - Clients / Vendors
  - Finance documents (quotations, invoices, POs)
  - Payment milestones, invoices, collections
  - Company expenses

Usage:
    python manage.py seed_crm_finance
    python manage.py seed_crm_finance --reset   # wipe demo records first
    python manage.py seed_crm_finance --dry-run
"""

import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from packages.workflow.models import State

DEMO_CLIENT_PREFIX = "HIT-"
DEMO_PROJECT_PREFIX = "PRJ-260"

# Billing clients — Hackers Infotech real demo portfolio (Mar–Jul 2026)
CLIENTS = [
    {
        "name": "Textiles Powerloop Pvt Ltd",
        "code": "HIT-PWR",
        "contact_person": "Ramesh Velusamy",
        "contact_email": "ramesh@powerlooptextiles.in",
        "phone": "+91 98422 11001",
        "address": "Avinashi Road, Tiruppur, Tamil Nadu 641603",
        "latitude": 11.1085,
        "longitude": 77.3411,
        "pan_number": "AABCP1234A",
        "gst_number": "33AABCP1234A1Z5",
        "category": "Enterprise",
    },
    {
        "name": "SS Battery Ltd",
        "code": "HIT-SSB",
        "contact_person": "Sundar Rajan",
        "contact_email": "sundar@ssbattery.com",
        "phone": "+91 94433 22002",
        "address": "Ambattur Industrial Estate, Chennai, Tamil Nadu 600058",
        "latitude": 13.1143,
        "longitude": 80.1548,
        "pan_number": "AABCS5678B",
        "gst_number": "33AABCS5678B1Z3",
        "category": "Enterprise",
    },
    {
        "name": "Kongu Nadu College of Engineering",
        "code": "HIT-KNC",
        "contact_person": "Dr. Murugesan",
        "contact_email": "principal@kongunadu.ac.in",
        "phone": "+91 94425 33003",
        "address": "Nanjanapuram, Erode, Tamil Nadu 638052",
        "latitude": 11.3410,
        "longitude": 77.7172,
        "pan_number": "AABCK9012C",
        "gst_number": "33AABCK9012C1Z8",
        "category": "Education",
    },
    {
        "name": "YM Automation Pvt Ltd",
        "code": "HIT-YMA",
        "contact_person": "Yogesh Manickam",
        "contact_email": "yogesh@ymautomation.com",
        "phone": "+91 98430 44004",
        "address": "Peelamedu, Coimbatore, Tamil Nadu 641004",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "pan_number": "AABCY3456D",
        "gst_number": "33AABCY3456D1Z1",
        "category": "SME",
    },
]

# Five billing projects (non-billing internal projects are seeded in seed_pmo_demo)
PROJECTS = [
    {
        "code": "PRJ-260101",
        "name": "ERP Tool",
        "client_code": "HIT-PWR",
        "description": "Textile ERP — inventory, production planning, and finance modules for Powerloop",
        "estimated_hours": Decimal("1800.00"),
        "contract_value": Decimal("1800000.00"),
        "budget": Decimal("1800000.00"),
        "workflow_slug": "ongoing",
    },
    {
        "code": "PRJ-260102",
        "name": "Inventory Management System",
        "client_code": "HIT-SSB",
        "description": "Warehouse & battery stock ledger with GRN, batch tracking, and reorder alerts",
        "estimated_hours": Decimal("1200.00"),
        "contract_value": Decimal("950000.00"),
        "budget": Decimal("950000.00"),
        "workflow_slug": "ongoing",
    },
    {
        "code": "PRJ-260103",
        "name": "Nexus Tool",
        "client_code": "HIT-PWR",
        "description": "Internal learning product — workflow automation toolkit (pilot with Powerloop)",
        "estimated_hours": Decimal("640.00"),
        "contract_value": Decimal("420000.00"),
        "budget": Decimal("420000.00"),
        "workflow_slug": "kickoff",
    },
    {
        "code": "TRN-260101",
        "name": "Cyber Security Training",
        "client_code": "HIT-KNC",
        "description": "3-day onsite cyber security workshop for Kongu Nadu College — Mar 2026",
        "estimated_hours": Decimal("24.00"),
        "contract_value": Decimal("150000.00"),
        "budget": Decimal("150000.00"),
        "workflow_slug": "close",
    },
    {
        "code": "PRJ-260104",
        "name": "VAPT & QA",
        "client_code": "HIT-YMA",
        "description": "Vulnerability assessment, penetration testing, and QA automation for YM Automation",
        "estimated_hours": Decimal("480.00"),
        "contract_value": Decimal("680000.00"),
        "budget": Decimal("680000.00"),
        "workflow_slug": "ongoing",
    },
]

FINANCE_DOCS = [
    {
        "client_code": "HIT-PWR",
        "project_code": "PRJ-260101",
        "document_type": "quotation",
        "status": "accepted",
        "currency": "INR",
        "valid_until_days": 30,
        "notes": "ERP Tool quotation for Textiles Powerloop — 40% advance, 30% UAT, 30% go-live",
        "line_items": [
            ("ERP Core — Inventory & Production", 1, 720000, 18),
            ("ERP Finance & Reporting Module", 1, 480000, 18),
            ("Implementation & UAT Support (400 hrs)", 400, 1500, 18),
        ],
    },
    {
        "client_code": "HIT-PWR",
        "project_code": "PRJ-260101",
        "document_type": "gst_invoice",
        "status": "paid",
        "currency": "INR",
        "seed_key": "erp-kickoff-invoice",
        "notes": "ERP Tool — Kickoff & discovery milestone (fully collected)",
        "line_items": [
            ("Kickoff & Requirements — Mar 2026", 1, 540000, 18),
        ],
    },
    {
        "client_code": "HIT-SSB",
        "project_code": "PRJ-260102",
        "document_type": "quotation",
        "status": "accepted",
        "currency": "INR",
        "line_items": [
            ("Inventory Management System — License", 1, 380000, 18),
            ("Warehouse Integration & GRN Module", 1, 320000, 18),
            ("QA & Deployment Support", 80, 3125, 18),
        ],
    },
    {
        "client_code": "HIT-SSB",
        "project_code": "PRJ-260102",
        "document_type": "gst_invoice",
        "status": "paid",
        "currency": "INR",
        "seed_key": "ims-final-invoice",
        "notes": "IMS — Final delivery invoice (fully paid Apr 2026)",
        "line_items": [
            ("Inventory IMS — Go-Live & Handover", 1, 950000, 18),
        ],
    },
    {
        "client_code": "HIT-KNC",
        "project_code": "TRN-260101",
        "document_type": "quotation",
        "status": "accepted",
        "currency": "INR",
        "line_items": [
            ("Cyber Security Fundamentals — Day 1", 1, 50000, 18),
            ("Ethical Hacking Workshop — Day 2", 1, 50000, 18),
            ("Security Hardening & Wrap-up — Day 3", 1, 50000, 18),
        ],
    },
    {
        "client_code": "HIT-KNC",
        "project_code": "TRN-260101",
        "document_type": "gst_invoice",
        "status": "paid",
        "currency": "INR",
        "seed_key": "training-invoice",
        "notes": "Cyber Security Training — Kongu Nadu College (fully paid)",
        "line_items": [
            ("3-Day Cyber Security Training — Mar 2026", 1, 150000, 18),
        ],
    },
    {
        "client_code": "HIT-YMA",
        "project_code": "PRJ-260104",
        "document_type": "quotation",
        "status": "sent",
        "currency": "INR",
        "line_items": [
            ("VAPT Assessment — Web & API", 1, 280000, 18),
            ("QA Automation Framework Setup", 1, 220000, 18),
            ("Remediation Retest & Sign-off", 1, 180000, 18),
        ],
    },
    {
        "client_code": "HIT-YMA",
        "project_code": "PRJ-260104",
        "document_type": "gst_invoice",
        "status": "generated",
        "currency": "INR",
        "seed_key": "vapt-partial-invoice",
        "notes": "VAPT & QA — Phase 1 invoice (60% collected, balance pending)",
        "line_items": [
            ("VAPT Phase 1 — Assessment Report", 1, 408000, 18),
        ],
    },
    {
        "client_code": "HIT-PWR",
        "project_code": "PRJ-260103",
        "document_type": "proforma_invoice",
        "status": "sent",
        "currency": "INR",
        "seed_key": "nexus-proforma",
        "notes": "Nexus Tool pilot — proforma (payment pending)",
        "line_items": [
            ("Nexus Workflow Toolkit — Pilot License", 1, 420000, 18),
        ],
    },
]

EXPENSES = [
    {"category": "TRAVEL",    "description": "Client visit — Textiles Powerloop, Tiruppur", "amount": 4200,  "status": "APPROVED",   "client_code": "HIT-PWR", "days_ago": 45},
    {"category": "TRAVEL",    "description": "Site visit — SS Battery warehouse, Chennai",   "amount": 6800,  "status": "REIMBURSED", "client_code": "HIT-SSB", "days_ago": 60},
    {"category": "TRAVEL",    "description": "Training travel — Kongu Nadu College, Erode",  "amount": 3500,  "status": "REIMBURSED", "client_code": "HIT-KNC", "days_ago": 90},
    {"category": "MEALS",     "description": "Team lunch — ERP sprint planning",             "amount": 3200,  "status": "APPROVED",   "client_code": None,      "days_ago": 18},
    {"category": "SOFTWARE",  "description": "Burp Suite Pro — VAPT project license",        "amount": 8900,  "status": "APPROVED",   "client_code": "HIT-YMA", "days_ago": 25},
    {"category": "OFFICE",    "description": "Whiteboard markers & stationery",              "amount": 850,   "status": "SUBMITTED",  "client_code": None,      "days_ago": 4},
    {"category": "EQUIPMENT", "description": "USB Wi-Fi adapter for intern QA bench",        "amount": 1200,  "status": "APPROVED",   "client_code": None,      "days_ago": 30},
    {"category": "UTILITIES", "description": "Office internet — May 2026",                   "amount": 5500,  "status": "REIMBURSED", "client_code": None,      "days_ago": 35},
]


class Command(BaseCommand):
    help = "Seed dummy CRM & Finance data (clients, documents, payments, expenses)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
        parser.add_argument("--reset",   action="store_true", help="Delete existing demo records first")

    def handle(self, *args, **options):
        dry   = options["dry_run"]
        reset = options["reset"]

        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN mode — no changes will be saved\n"))

        with transaction.atomic():
            if reset:
                self._reset(dry)

            client_map  = self._seed_clients(dry)
            project_map = self._seed_projects(dry, client_map)
            doc_count   = self._seed_finance_documents(dry, client_map, project_map)
            pay_counts  = self._seed_payments(dry, client_map, project_map)
            exp_count   = self._seed_expenses(dry, client_map, project_map)

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"\nCRM & Finance seed complete."
            f"\n  Clients:    {len(client_map)}"
            f"\n  Projects:   {len(project_map)}"
            f"\n  Documents:  {doc_count}"
            f"\n  Invoices:   {pay_counts['invoices']}"
            f"\n  Payments:   {pay_counts['payments']}"
            f"\n  Milestones: {pay_counts['milestones']}"
            f"\n  Expenses:   {exp_count}"
        ))

    # ── Reset ─────────────────────────────────────────────────────────────────

    def _reset(self, dry):
        from apps.expenses.models import CompanyExpense
        from apps.finance.models import Document
        from apps.payment.models import Milestone, Invoice, Payment, PaymentAllocation
        from apps.projects.models import Client, Project

        from django.db.models import Q

        billing_codes = [p["code"] for p in PROJECTS]
        demo_clients = Client.objects.filter(
            Q(code__startswith=DEMO_CLIENT_PREFIX) | Q(code__startswith="DEMO-")
        )
        demo_projects = Project.objects.filter(
            Q(code__in=billing_codes) | Q(code__startswith="DEMO-PRJ-")
        )
        demo_expenses = CompanyExpense.objects.filter(
            Q(client__in=demo_clients) | Q(reference_number__startswith="BILL-DEMO-")
        )

        counts = {
            "allocations": PaymentAllocation.objects.filter(payment__client__in=demo_clients).count(),
            "payments":    Payment.objects.filter(client__in=demo_clients).count(),
            "invoices":    Invoice.objects.filter(client__in=demo_clients).count(),
            "milestones":  Milestone.objects.filter(project__in=demo_projects).count(),
            "documents":   Document.objects.filter(client__in=demo_clients).count(),
            "expenses":    demo_expenses.count(),
            "projects":    demo_projects.count(),
            "clients":     demo_clients.count(),
        }

        if not dry:
            PaymentAllocation.objects.filter(payment__client__in=demo_clients).delete()
            Payment.objects.filter(client__in=demo_clients).delete()
            Invoice.objects.filter(client__in=demo_clients).delete()
            Milestone.objects.filter(project__in=demo_projects).delete()
            Document.objects.filter(client__in=demo_clients).delete()
            demo_expenses.delete()
            demo_projects.delete()
            demo_clients.delete()

        self._log(f"  Reset: removed {counts['clients']} clients, {counts['projects']} projects, "
                  f"{counts['documents']} documents, {counts['invoices']} invoices, "
                  f"{counts['payments']} payments, {counts['expenses']} expenses")

    # ── Clients ─────────────────────────────────────────────────────────────

    def _seed_clients(self, dry):
        from apps.master.models import ClientCategory
        from apps.projects.models import Client

        client_map = {}
        categories = {}

        for cfg in CLIENTS:
            cat_name = cfg["category"]
            if cat_name not in categories and not dry:
                cat, _ = ClientCategory.objects.get_or_create(
                    name=cat_name,
                    defaults={"is_active": True},
                )
                categories[cat_name] = cat

            if dry:
                client_map[cfg["code"]] = cfg
                continue

            defaults = {
                "code":              cfg["code"],
                "contact_person":    cfg["contact_person"],
                "contact_email":     cfg["contact_email"],
                "phone":             cfg["phone"],
                "address":           cfg["address"],
                "formatted_address": cfg["address"],
                "pan_number":        cfg["pan_number"],
                "gst_number":        cfg["gst_number"],
                "category":          categories.get(cat_name),
                "is_active":         True,
            }
            if cfg.get("latitude") is not None:
                defaults["latitude"] = Decimal(str(cfg["latitude"]))
            if cfg.get("longitude") is not None:
                defaults["longitude"] = Decimal(str(cfg["longitude"]))
            client, created = Client.objects.get_or_create(name=cfg["name"], defaults=defaults)
            if not created:
                for k, v in defaults.items():
                    setattr(client, k, v)
                client.save()
            client_map[cfg["code"]] = client
            self._log(f"  {'Created' if created else 'Updated'} client: {client.name}")

        return client_map

    # ── Projects ──────────────────────────────────────────────────────────────

    def _seed_projects(self, dry, client_map):
        from apps.master.models import BusinessType, BillingType
        from apps.projects.models import Project

        project_map = {}
        today = datetime.date.today()

        if not dry:
            business_type, _ = BusinessType.objects.get_or_create(
                name="Project",
                defaults={"prefix": "PRJ", "is_active": True},
            )
            billing_type, _ = BillingType.objects.get_or_create(
                name="Fixed Price",
                defaults={"is_active": True},
            )
            ct = ContentType.objects.get(app_label="projects", model="project")
            default_state = State.objects.filter(content_type=ct, slug="enquiry").first()
        else:
            business_type = billing_type = default_state = None

        for cfg in PROJECTS:
            if dry:
                project_map[cfg["code"]] = cfg
                continue

            client = client_map[cfg["client_code"]]
            slug = cfg.get("workflow_slug", "enquiry")
            workflow_state = State.objects.filter(content_type=ct, slug=slug).first() or default_state
            defaults = {
                "name":            cfg["name"],
                "description":     cfg["description"],
                "client":          client,
                "business_type":   business_type,
                "billing_type":    billing_type,
                "estimated_hours": cfg["estimated_hours"],
                "budget":          cfg.get("budget") or Decimal("0"),
                "start_date":      today - datetime.timedelta(days=60),
                "end_date":        today + datetime.timedelta(days=180),
                "workflow_state":  workflow_state,
                "is_active":       True,
            }
            project, created = Project.objects.get_or_create(code=cfg["code"], defaults=defaults)
            if not created:
                for k, v in defaults.items():
                    setattr(project, k, v)
                project.save()
            project_map[cfg["code"]] = project
            self._log(f"  {'Created' if created else 'Updated'} project: {project.code}")

        return project_map

    # ── Finance documents ─────────────────────────────────────────────────────

    def _seed_finance_documents(self, dry, client_map, project_map):
        from apps.finance.models import Document, DocumentLineItem

        created = 0
        today = datetime.date.today()

        for cfg in FINANCE_DOCS:
            key = f"{cfg['client_code']}-{cfg['document_type']}-{cfg['status']}"
            if dry:
                created += 1
                continue

            client  = client_map[cfg["client_code"]]
            project = project_map.get(cfg.get("project_code"))

            if cfg.get("seed_key") and Document.objects.filter(
                notes=cfg.get("notes", ""),
                is_deleted=False,
            ).exists():
                continue

            # Skip duplicate seed docs (idempotent re-run)
            existing = Document.objects.filter(
                client=client,
                project=project,
                document_type=cfg["document_type"],
                status=cfg["status"],
                is_deleted=False,
            ).first()
            if existing and not cfg.get("seed_key"):
                continue

            valid_until = None
            if cfg.get("valid_until_days"):
                valid_until = today + datetime.timedelta(days=cfg["valid_until_days"])

            doc = Document(
                document_number=Document.generate_document_number(cfg["document_type"]),
                document_type=cfg["document_type"],
                client=client,
                project=project,
                currency=cfg.get("currency", "INR"),
                status=cfg["status"],
                valid_until=valid_until,
                notes=cfg.get("notes", ""),
                client_name=client.name,
                client_email=client.contact_email,
                client_gst_number=client.gst_number,
                billing_address=client.formatted_address or client.address,
                shipping_address=client.formatted_address or client.address,
            )
            doc.save()

            for i, (desc, qty, rate, gst) in enumerate(cfg["line_items"]):
                DocumentLineItem.objects.create(
                    document=doc,
                    description=desc,
                    quantity=Decimal(str(qty)),
                    rate=Decimal(str(rate)),
                    gst_percentage=Decimal(str(gst)),
                    sort_order=i,
                )

            doc.recalculate_totals()
            created += 1
            self._log(f"  Created document: {doc.document_number} ({cfg['document_type']})")

        return created

    # ── Payments (milestones, invoices, collections) ────────────────────────────

    def _seed_payments(self, dry, client_map, project_map):
        from apps.payment.models import (
            Milestone, MilestoneStatus, Invoice, InvoiceType,
            Payment, PaymentMode, PaymentAllocation,
        )

        today = datetime.date.today()
        counts = {"milestones": 0, "invoices": 0, "payments": 0}

        invoice_specs = [
            # (project_code, type, amount, days_ago, due_days_offset, paid_pct)
            ("PRJ-260101", InvoiceType.MILESTONE, 540000, 75, -30, 100),   # ERP kickoff — fully paid
            ("PRJ-260101", InvoiceType.MILESTONE, 720000, 25,  30,  50),   # ERP dev phase — partial
            ("PRJ-260102", InvoiceType.FINAL,     950000, 55, -20, 100),   # IMS — fully paid
            ("TRN-260101", InvoiceType.FINAL,     150000, 85, -60, 100),   # Training — fully paid
            ("PRJ-260104", InvoiceType.MILESTONE, 408000, 20,  45,  60),   # VAPT — partial, balance pending
            ("PRJ-260103", InvoiceType.ADVANCE,   126000, 10,  60,   0),   # Nexus — unpaid / pending
        ]

        milestone_map = {}

        for cfg in PROJECTS:
            code = cfg["code"]
            if dry:
                counts["milestones"] += 3
                continue

            project = project_map[code]
            if Milestone.objects.filter(project=project).exists():
                milestones = list(Milestone.objects.filter(project=project).order_by("sequence"))
                milestone_map[code] = milestones
                continue

            splits = [
                ("Kickoff & Discovery",  Decimal("30"), 0),
                ("Development Phase",    Decimal("40"), 1),
                ("UAT & Go-Live",        Decimal("30"), 2),
            ]
            value = cfg["contract_value"]
            ms_list = []
            for name, pct, seq in splits:
                amount = (value * pct / Decimal("100")).quantize(Decimal("0.01"))
                ms = Milestone.objects.create(
                    project=project,
                    milestone_name=name,
                    description=f"{name} for {project.name}",
                    percentage=pct,
                    amount=amount,
                    due_date=today + datetime.timedelta(days=30 * (seq + 1)),
                    sequence=seq,
                    status=MilestoneStatus.PENDING,
                )
                ms_list.append(ms)
                counts["milestones"] += 1
            milestone_map[code] = ms_list

        for proj_code, inv_type, amount, days_ago, due_offset, paid_pct in invoice_specs:
            if dry:
                counts["invoices"] += 1
                if paid_pct > 0:
                    counts["payments"] += 1
                continue

            project = project_map[proj_code]
            client  = project.client
            inv_date = today - datetime.timedelta(days=days_ago)
            due_date = today + datetime.timedelta(days=due_offset)

            if Invoice.objects.filter(
                client=client, project=project,
                invoice_amount=Decimal(str(amount)), invoice_date=inv_date,
                is_deleted=False,
            ).exists():
                continue

            milestone = None
            if inv_type == InvoiceType.MILESTONE and proj_code in milestone_map:
                milestones = milestone_map[proj_code]
                idx = min(len(milestones) - 1, counts["invoices"] % len(milestones))
                milestone = milestones[idx]

            invoice = Invoice(
                invoice_type=inv_type,
                invoice_date=inv_date,
                client=client,
                project=project,
                milestone=milestone,
                invoice_amount=Decimal(str(amount)),
                tax_percentage=Decimal("18.00"),
                due_date=due_date,
                notes=f"Demo invoice for {project.name}",
            )
            invoice.save()
            counts["invoices"] += 1

            if paid_pct > 0:
                pay_amount = (invoice.total_amount * Decimal(paid_pct) / Decimal("100")).quantize(Decimal("0.01"))
                payment = Payment(
                    client=client,
                    project=project,
                    payment_date=inv_date + datetime.timedelta(days=7),
                    payment_amount=pay_amount,
                    payment_mode=PaymentMode.BANK_TRANSFER,
                    bank_reference=f"UTR{DEMO_CLIENT_PREFIX}{counts['payments']:06d}",
                    remarks=f"Demo payment for {invoice.invoice_number}",
                )
                payment.save()
                PaymentAllocation.objects.create(
                    payment=payment,
                    invoice=invoice,
                    allocated_amount=pay_amount,
                    notes="Demo allocation",
                )
                counts["payments"] += 1

                if milestone and paid_pct >= 100:
                    milestone.status = MilestoneStatus.PAID
                    milestone.save(update_fields=["status", "updated_at"])

        # Spread payments across recent months for dashboard chart
        if not dry:
            for i, month_offset in enumerate(range(5, -1, -1)):
                m = today.month - month_offset
                y = today.year
                while m <= 0:
                    m += 12
                    y -= 1
                pay_date = datetime.date(y, m, min(15, 28))
                client = list(client_map.values())[i % len(client_map)]
                ref = f"PAY-DEMO-{y}{m:02d}"
                if Payment.objects.filter(bank_reference=ref).exists():
                    continue
                Payment.objects.create(
                    client=client,
                    payment_date=pay_date,
                    payment_amount=Decimal(str(50000 + i * 15000)),
                    payment_mode=PaymentMode.UPI,
                    bank_reference=ref,
                    remarks="Demo monthly collection",
                )
                counts["payments"] += 1

        return counts

    # ── Expenses ──────────────────────────────────────────────────────────────

    def _seed_expenses(self, dry, client_map, project_map):
        from apps.accounts.models import Employee
        from apps.expenses.models import CompanyExpense, ExpensePaymentMode

        today = datetime.date.today()
        created = 0

        if dry:
            return len(EXPENSES)

        employee = Employee.objects.filter(is_active=True).order_by("created_at").first()
        if not employee:
            self.stdout.write(self.style.WARNING("  [WARN] No employees found — skipping expenses"))
            return 0

        approver = Employee.objects.filter(is_manager=True, is_active=True).first() or employee
        first_project = list(project_map.values())[0] if project_map else None

        for cfg in EXPENSES:
            desc = cfg["description"]
            if CompanyExpense.objects.filter(description=desc, is_deleted=False).exists():
                continue

            client = client_map.get(cfg["client_code"]) if cfg.get("client_code") else None
            expense = CompanyExpense(
                date=today - datetime.timedelta(days=cfg["days_ago"]),
                category=cfg["category"],
                description=desc,
                amount=Decimal(str(cfg["amount"])),
                paid_by=employee,
                project=first_project if client else None,
                client=client,
                payment_mode=ExpensePaymentMode.CORPORATE_CARD,
                reference_number=f"BILL-DEMO-{created + 1:04d}",
                status=cfg["status"],
                approved_by=approver if cfg["status"] in ("APPROVED", "REIMBURSED") else None,
                approved_at=timezone.now() if cfg["status"] in ("APPROVED", "REIMBURSED") else None,
                notes="Seeded demo expense",
            )
            expense.save()
            created += 1

        self._log(f"  Expenses: {created} created")
        return created

    def _log(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))
