"""
One-shot demo data seed for a fresh PostgreSQL + Keycloak realm.

Runs in order:
  1. create_permissions      — push permissions.json to Keycloak
  2. assign_role_permissions — map Keycloak groups to permissions
  3. seed_workflow           — project + ticket workflow states
  4. migrate_seed_data       — master tables, employees, Mar–Jul attendance
  5. seed_crm_finance        — HIT clients, invoices, payments (full/partial/pending)
  6. seed_pmo_demo           — 8 projects, tickets, timesheets, leaves, payroll

Demo scenario (Hackers Infotech, Mar–Jul 2026):
  Billing: ERP Tool (Powerloop), IMS (SS Battery), Nexus Tool, Cyber Training
           (Kongu Nadu College), VAPT & QA (YM Automation)
  Non-billing: ASM, QA Generate, VAPT Tool Automation
  Attendance with per-employee break variance; HR-approved leaves; manager-approved
  timesheets; May payslips for selected interns.

Usage:
    python manage.py migrate
    python manage.py seed_demo_data
    python manage.py seed_demo_data --skip-keycloak
    python manage.py seed_demo_data --reset
    python manage.py seed_demo_data --dry-run
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed all demo data (master, workflow, users, projects, CRM, finance)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--reset", action="store_true", help="Reset seed data before loading")
        parser.add_argument(
            "--skip-keycloak",
            action="store_true",
            help="Skip Keycloak permission + user provisioning steps",
        )
        parser.add_argument(
            "--skip-permissions",
            action="store_true",
            help="Skip create_permissions and assign_role_permissions",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        reset = options["reset"]
        skip_kc = options["skip_keycloak"]
        skip_perm = options["skip_permissions"]

        steps = []

        if not skip_perm and not skip_kc:
            steps.append(("create_permissions", {}))
            steps.append(("assign_role_permissions", {}))

        # Dependent demo data must be removed before employees (expenses PROTECT paid_by)
        if reset:
            steps.extend([
                ("seed_pmo_demo", {"dry_run": dry, "reset": True}),
                ("seed_crm_finance", {"dry_run": dry, "reset": True}),
            ])

        steps.extend([
            ("seed_workflow", {}),
            (
                "migrate_seed_data",
                {
                    "skip_keycloak": skip_kc,
                    "dry_run": dry,
                    "reset": reset,
                },
            ),
            ("seed_crm_finance", {"dry_run": dry, "reset": False}),
            ("seed_pmo_demo", {"dry_run": dry, "reset": False}),
        ])

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding PMT demo data...\n"))

        for cmd, kwargs in steps:
            if dry and cmd in ("create_permissions", "assign_role_permissions"):
                kwargs["dry_run"] = True
            self.stdout.write(self.style.HTTP_INFO(f"→ {cmd}"))
            call_command(cmd, **kwargs)

        self.stdout.write(self.style.SUCCESS("\nAll demo data seeded successfully."))
        self.stdout.write(
            "\nDefault employee password: employee code (e.g. HIT-001) or ChangeMe@123\n"
            "Keycloak groups: Admin | HR & Admin | Project Manager | Employee\n"
            "Demo period: Mar–Jul 2026 | Clients: Powerloop, SS Battery, Kongu Nadu, YM Automation\n"
        )
