"""
Data migration command: loads master tables and employees from CSV files
located in backend/data/, provisions them in Keycloak, and seeds weekday
attendance from March 2026 through July 2026 (or today if earlier) with
per-employee check-in/out variance and break records for shift staff.

Usage:
    python manage.py migrate_seed_data                    # full run (Django + Keycloak)
    python manage.py migrate_seed_data --skip-keycloak    # Django / Postgres only
    python manage.py migrate_seed_data --dry-run          # simulate, no DB writes
    python manage.py migrate_seed_data --reset            # wipe existing seed data first
"""

import csv
import hashlib
import logging
import os
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data")


def _attendance_weekdays(start=None, end=None):
    """Weekdays (Mon–Fri) from start through end (defaults: 2026-03-01 → min(today, Jul 31))."""
    start = start or date(2026, 3, 1)
    end = end or min(date.today(), date(2026, 7, 31))
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _emp_offset(username: str, salt: str, span: int) -> int:
    digest = hashlib.md5(f"{username}:{salt}".encode()).hexdigest()
    return int(digest, 16) % span


def _add_minutes(t: time, minutes: int) -> time:
    base = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
    return base.time()


def _csv_path(filename):
    p = os.path.join(DATA_DIR, filename)
    if not os.path.exists(p):
        raise CommandError(f"CSV not found: {p}")
    return p


def _bool(val):
    return str(val).strip().lower() in ("true", "1", "yes")


def _parse_date(val):
    """Accept YYYY-MM-DD, M/D/YYYY, D/M/YYYY, or D-Mon-YYYY."""
    v = str(val).strip()
    if not v:
        return None
    from datetime import datetime
    if v.count("/") == 2:
        parts = v.split("/")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            a, b = int(parts[0]), int(parts[1])
            if a > 12:
                return datetime.strptime(v, "%d/%m/%Y").date()
            if b > 12:
                return datetime.strptime(v, "%m/%d/%Y").date()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {v!r}")


def _parse_gender(val):
    """Map CSV values (male/female/M/F) to Employee model codes."""
    v = str(val).strip().lower()
    if not v:
        return ""
    if v in ("m", "male"):
        return "M"
    if v in ("f", "female"):
        return "F"
    if v in ("o", "other"):
        return "O"
    return ""


# ── Keycloak helper ────────────────────────────────────────────────────────────

class KeycloakProvisioner:
    """
    Thin wrapper around KeycloakAdmin for seeding:
      - create user (idempotent via exist_ok)
      - set permanent password
      - assign to group
      - return keycloak user UUID
    """

    def __init__(self):
        from django.conf import settings
        from keycloak import KeycloakAdmin
        self._admin = KeycloakAdmin(
            server_url=settings.KEYCLOAK_SERVER_URL,
            realm_name=settings.KEYCLOAK_REALM,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
            verify=True,
        )
        # Cache groups as {name: id}
        self._group_map: dict[str, str] = {}
        self._load_groups()

    def _load_groups(self):
        groups = self._admin.get_groups()
        self._group_map = {g["name"]: g["id"] for g in groups}

    def _get_or_create_user(self, username: str, email: str,
                             first_name: str, last_name: str,
                             designation: str, department: str,
                             employee_code: str, password: str) -> str:
        """Create user in Keycloak. If already exists return existing UUID."""
        payload = {
            "username":  username,
            "email":     email,
            "firstName": first_name,
            "lastName":  last_name,
            "enabled":   True,
            "credentials": [
                {"type": "password", "value": password, "temporary": False}
            ],
            "attributes": {
                "designation":   [designation],
                "department":    [department],
                "employee_code": [employee_code],
            },
        }
        try:
            # create_user raises on duplicate; exist_ok suppresses it and
            # returns '' — we fall back to a username lookup in that case.
            kc_id = self._admin.create_user(payload, exist_ok=True)
            if kc_id:
                return kc_id
        except Exception:
            pass

        # Already exists — look up by username
        users = self._admin.get_users({"username": username, "exact": True})
        if users:
            return users[0]["id"]
        raise RuntimeError(f"Cannot find Keycloak user after create: {username!r}")

    def provision(self, username: str, email: str, first_name: str, last_name: str,
                  designation: str, department: str, employee_code: str,
                  password: str, group_name: str) -> str:
        """
        Ensure user exists in Keycloak, assign to group, return keycloak UUID.
        """
        kc_id = self._get_or_create_user(
            username, email, first_name, last_name,
            designation, department, employee_code, password,
        )

        if group_name and group_name in self._group_map:
            try:
                self._admin.group_user_add(kc_id, self._group_map[group_name])
            except Exception as exc:
                # "Conflict" means already in group — harmless
                if "409" not in str(exc) and "Conflict" not in str(exc):
                    logger.warning("group_user_add failed for %s → %s: %s", username, group_name, exc)
        elif group_name:
            logger.warning("Keycloak group not found: %r  (user: %s)", group_name, username)

        return kc_id


# ── Command ────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed pmt_db from CSV files and provision Keycloak accounts"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run",        action="store_true", help="Simulate without writing")
        parser.add_argument("--reset",          action="store_true", help="Delete existing seeded records first")
        parser.add_argument("--skip-keycloak",  action="store_true", help="Skip Keycloak provisioning (Django/Postgres only)")

    def handle(self, *args, **options):
        dry          = options["dry_run"]
        reset        = options["reset"]
        skip_kc      = options["skip_keycloak"]

        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN mode — no changes will be saved\n"))

        # Build Keycloak provisioner once (fail fast if KC is unreachable)
        provisioner = None
        if not skip_kc and not dry:
            try:
                provisioner = KeycloakProvisioner()
                self._log(f"  Keycloak:     connected ({len(provisioner._group_map)} groups found: "
                          f"{', '.join(provisioner._group_map.keys())})")
            except Exception as exc:
                self.stdout.write(self.style.WARNING(
                    f"  [WARN] Keycloak unreachable — skipping KC provisioning. ({exc})\n"
                    f"         Run with --skip-keycloak to suppress this warning."
                ))

        with transaction.atomic():
            self._load_designations(dry, reset)
            self._load_departments(dry, reset)
            self._load_locations(dry, reset)
            self._load_employment_types(dry, reset)
            self._load_shift_categories(dry, reset)
            self._load_rate_cards(dry, reset)
            emp_map = self._load_employees(dry, reset, provisioner)
            self._load_managers(dry, emp_map)
            self._seed_attendance(dry, emp_map)

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("\nMigration complete."))

    # ──────────────────────────────────────────────────────────────────────────
    # Master tables
    # ──────────────────────────────────────────────────────────────────────────

    def _load_designations(self, dry, reset):
        from apps.master.models import Designation
        if reset:
            Designation.objects.all().delete()
        created = 0
        with open(_csv_path("master_designations.csv")) as f:
            for row in csv.DictReader(f):
                name = row["name"].strip()
                if not dry:
                    _, c = Designation.objects.get_or_create(
                        name=name, defaults={"is_active": _bool(row["is_active"])})
                    if c:
                        created += 1
                else:
                    created += 1
        self._log(f"  Designations: {created} created")

    def _load_departments(self, dry, reset):
        from apps.master.models import Department
        if reset:
            Department.objects.all().delete()
        created = 0
        with open(_csv_path("master_departments.csv")) as f:
            for row in csv.DictReader(f):
                name = row["name"].strip()
                if not dry:
                    _, c = Department.objects.get_or_create(
                        name=name, defaults={"is_active": _bool(row["is_active"])})
                    if c:
                        created += 1
                else:
                    created += 1
        self._log(f"  Departments:  {created} created")

    def _load_locations(self, dry, reset):
        from apps.master.models import Location
        if reset:
            Location.objects.all().delete()
        created = 0
        with open(_csv_path("master_locations.csv")) as f:
            for row in csv.DictReader(f):
                name = row["name"].strip()
                if not dry:
                    _, c = Location.objects.get_or_create(
                        name=name,
                        defaults={
                            "city":      row["city"].strip(),
                            "state":     row["state"].strip(),
                            "country":   row["country"].strip(),
                            "is_active": _bool(row["is_active"]),
                        },
                    )
                    if c:
                        created += 1
                else:
                    created += 1
        self._log(f"  Locations:    {created} created")

    def _load_employment_types(self, dry, reset):
        from apps.master.models import EmploymentType
        if reset:
            EmploymentType.objects.all().delete()
        created = 0
        with open(_csv_path("master_employment_types.csv")) as f:
            for row in csv.DictReader(f):
                name = row["name"].strip()
                if not dry:
                    _, c = EmploymentType.objects.get_or_create(
                        name=name, defaults={"is_active": _bool(row["is_active"])})
                    if c:
                        created += 1
                else:
                    created += 1
        self._log(f"  Emp. Types:   {created} created")

    def _load_rate_cards(self, dry, reset):
        from apps.master.models import RateCard, Designation, Department
        if reset:
            RateCard.objects.all().delete()
        created = updated = 0
        with open(_csv_path("master_rate_cards.csv")) as f:
            for row in csv.DictReader(f):
                desig_name = row["designation"].strip()
                dept_name  = row["department"].strip()
                try:
                    desig = Designation.objects.get(name=desig_name)
                    dept  = Department.objects.get(name=dept_name)
                except (Designation.DoesNotExist, Department.DoesNotExist) as e:
                    self.stdout.write(self.style.WARNING(f"    [WARN] Rate card skip — {e}"))
                    continue
                if not dry:
                    _, c = RateCard.objects.update_or_create(
                        designation_ref=desig,
                        department_ref=dept,
                        defaults={
                            "hr_daily_rate":       row["hr_daily_rate"].strip(),
                            "client_billing_rate": row["client_billing_rate"].strip(),
                            "is_active": True,
                        },
                    )
                    if c: created += 1
                    else: updated += 1
                else:
                    created += 1
        self._log(f"  Rate Cards:   {created} created, {updated} updated")

    def _load_shift_categories(self, dry, reset):
        from apps.master.models import ShiftCategory
        if reset:
            ShiftCategory.objects.all().delete()
        created = 0
        with open(_csv_path("master_shift_categories.csv")) as f:
            for row in csv.DictReader(f):
                name = row["name"].strip()
                if not dry:
                    _, c = ShiftCategory.objects.get_or_create(
                        name=name,
                        defaults={
                            "start_time": row["start_time"].strip(),
                            "end_time":   row["end_time"].strip(),
                            "is_active":  _bool(row["is_active"]),
                        },
                    )
                    if c:
                        created += 1
                else:
                    created += 1
        self._log(f"  Shift Cats:   {created} created")

    # ──────────────────────────────────────────────────────────────────────────
    # Employees — pass 1: create without manager FK
    # ──────────────────────────────────────────────────────────────────────────

    def _purge_hit_employee_blockers(self):
        """Remove records that block deleting HIT-* employees (e.g. expense paid_by PROTECT)."""
        from django.db.models import Q

        from apps.accounts.models import Employee
        from apps.expenses.models import CompanyExpense

        hit_ids = list(
            Employee.objects.filter(employee_code__startswith="HIT-").values_list("pk", flat=True)
        )
        if not hit_ids:
            return

        exp_qs = CompanyExpense.objects.filter(
            Q(paid_by_id__in=hit_ids) | Q(reference_number__startswith="BILL-DEMO-")
        )
        exp_count = exp_qs.count()
        if exp_count:
            exp_qs.delete()
            self._log(f"  Reset prep:   removed {exp_count} expense(s) blocking employee delete")

    def _load_employees(self, dry, reset, provisioner):
        from apps.master.models import Designation, Department, Location, EmploymentType, ShiftCategory
        from apps.accounts.models import Employee

        if reset and not dry:
            self._purge_hit_employee_blockers()
            Employee.objects.filter(employee_code__startswith="HIT-").delete()

        emp_map = {}

        def _fk(model, name):
            if not name or not name.strip():
                return None
            try:
                return model.objects.get(name=name.strip())
            except model.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"    [WARN] {model.__name__} not found: '{name}'"))
                return None

        created = updated = kc_provisioned = kc_skipped = 0

        with open(_csv_path("employees.csv")) as f:
            for row in csv.DictReader(f):
                username     = row["username"].strip()
                group_name   = row.get("keycloak_group", "Employee").strip()
                emp_code     = row["employee_code"].strip()
                password     = row.get("password", emp_code or "ChangeMe@123").strip()
                first_name   = row["first_name"].strip()
                last_name    = row["last_name"].strip()
                designation  = row["designation"].strip()
                department   = row["department"].strip()
                dob_raw      = row.get("dob", "").strip()

                defaults = {
                    "first_name":       first_name,
                    "last_name":        last_name,
                    "email":            row["email"].strip(),
                    "employee_code":    emp_code,
                    "gender":           _parse_gender(row.get("gender", "")),
                    "date_of_birth":    _parse_date(dob_raw) if dob_raw else None,
                    "designation_ref":  _fk(Designation,   designation),
                    "department_ref":   _fk(Department,    department),
                    "location":         _fk(Location,      row["location"]),
                    "employment_type":  _fk(EmploymentType, row["employment_type"]),
                    "joining_date":     _parse_date(row["joining_date"]),
                    "shift_applicable": _bool(row["shift_applicable"]),
                    "shift_category":   _fk(ShiftCategory, row.get("shift_category", "")),
                    "is_staff":         _bool(row["is_staff"]),
                    "is_superuser":     _bool(row["is_superuser"]),
                    "is_pmo":           _bool(row["is_pmo"]),
                    "is_manager":       _bool(row["is_manager"]),
                    "keycloak_group":   group_name,
                    "is_active":        True,
                }

                if dry:
                    # Minimal stub for downstream attendance seeding
                    emp_map[username] = type("E", (), {
                        "username":         username,
                        "joining_date":     defaults["joining_date"],
                        "shift_applicable": defaults["shift_applicable"],
                        "shift_category":   defaults["shift_category"],
                    })()
                    created += 1
                    continue

                emp, c = Employee.objects.get_or_create(username=username, defaults=defaults)
                if not c:
                    for k, v in defaults.items():
                        setattr(emp, k, v)
                    emp.save()
                    updated += 1
                else:
                    emp.set_password(password)
                    emp.save()
                    created += 1

                # ── Keycloak provisioning ─────────────────────────────────
                if provisioner and not emp.keycloak_id:
                    try:
                        kc_id = provisioner.provision(
                            username=username,
                            email=emp.email,
                            first_name=first_name,
                            last_name=last_name,
                            designation=designation,
                            department=department,
                            employee_code=emp.employee_code,
                            password=password,
                            group_name=group_name,
                        )
                        Employee.objects.filter(pk=emp.pk).update(keycloak_id=kc_id)
                        emp.keycloak_id = kc_id
                        kc_provisioned += 1
                    except Exception as exc:
                        self.stdout.write(self.style.WARNING(
                            f"    [KC-WARN] {username}: {exc}"))
                elif emp.keycloak_id:
                    kc_skipped += 1

                emp_map[username] = emp

        msg = f"  Employees:    {created} created, {updated} updated"
        if provisioner:
            msg += f"  |  Keycloak: {kc_provisioned} provisioned, {kc_skipped} already mapped"
        self._log(msg)
        return emp_map

    # ──────────────────────────────────────────────────────────────────────────
    # Employees — pass 2: wire manager FK
    # ──────────────────────────────────────────────────────────────────────────

    def _load_managers(self, dry, emp_map):
        from apps.accounts.models import Employee
        updated = 0
        with open(_csv_path("employees.csv")) as f:
            for row in csv.DictReader(f):
                mgr_username = row["manager_username"].strip()
                if not mgr_username:
                    continue
                emp_username = row["username"].strip()
                mgr = emp_map.get(mgr_username)
                if mgr is None:
                    self.stdout.write(self.style.WARNING(
                        f"    [WARN] manager not found: {mgr_username}"))
                    continue
                if not dry:
                    Employee.objects.filter(username=emp_username).update(manager=mgr)
                updated += 1
        self._log(f"  Manager FKs:  {updated} wired")

    # ──────────────────────────────────────────────────────────────────────────
    # Attendance — Mar–Jul 2026, weekdays, varied breaks for shift staff
    # ──────────────────────────────────────────────────────────────────────────

    def _seed_attendance(self, dry, emp_map):
        from apps.attendance.models import (
            AttendanceBreak, AttendanceRecord, AttendanceStatus, BreakType,
        )

        SHIFT_TIMES = {
            "Morning Shift (9AM-6PM)":  (time(9,  0), time(18, 0)),
            "General Shift (10AM-7PM)": (time(10, 0), time(19, 0)),
        }
        DEFAULT_TIMES = (time(9, 0), time(18, 0))

        # Approved leave days seeded later in seed_pmo_demo — pre-mark common ones here
        ON_LEAVE = {
            ("HIT-009", date(2026, 5, 12)),
            ("HIT-010", date(2026, 6, 16)),
            ("HIT-010", date(2026, 6, 17)),
            ("HIT-007", date(2026, 6, 23)),
            ("HIT-005", date(2026, 4, 4)),
        }

        created = skipped = breaks_created = 0
        work_days = _attendance_weekdays()

        for emp in emp_map.values():
            jd = emp.joining_date
            if isinstance(jd, str) and jd:
                jd = _parse_date(jd)

            sc      = getattr(emp, "shift_category", None)
            sc_name = sc.name if sc and hasattr(sc, "name") else ""
            base_cin, base_cout = SHIFT_TIMES.get(sc_name, DEFAULT_TIMES)
            shift_on = getattr(emp, "shift_applicable", False)

            # Per-employee clock variance (not identical across team)
            cin  = _add_minutes(base_cin,  _emp_offset(emp.username, "in",  25) - 8)
            cout = _add_minutes(base_cout, _emp_offset(emp.username, "out", 35) - 5)

            tea_start = _add_minutes(time(10, 30), _emp_offset(emp.username, "tea", 20))
            tea_mins  = 8 + _emp_offset(emp.username, "tea-len", 8)
            lunch_start = _add_minutes(time(12, 30), _emp_offset(emp.username, "lunch", 25))
            lunch_mins  = 42 + _emp_offset(emp.username, "lunch-len", 20)

            for work_day in work_days:
                if jd and work_day < jd:
                    skipped += 1
                    continue

                if (emp.username, work_day) in ON_LEAVE:
                    if dry:
                        created += 1
                        continue
                    AttendanceRecord.objects.update_or_create(
                        employee=emp,
                        date=work_day,
                        defaults={
                            "status": AttendanceStatus.ON_LEAVE,
                            "notes":  "Seeded approved leave",
                        },
                    )
                    created += 1
                    continue

                if dry:
                    created += 1
                    continue

                if shift_on:
                    status = AttendanceStatus.PRESENT
                    defaults = {
                        "check_in":  cin,
                        "check_out": cout,
                        "status":    status,
                        "notes":     "Seeded by migrate_seed_data",
                    }
                else:
                    # Senior staff — WFH / office presence without punch detail
                    status = AttendanceStatus.WFH if work_day.weekday() == 4 else AttendanceStatus.PRESENT
                    defaults = {
                        "check_in":  None,
                        "check_out": None,
                        "status":    status,
                        "notes":     "Seeded — management / non-shift",
                    }

                record, c = AttendanceRecord.objects.get_or_create(
                    employee=emp,
                    date=work_day,
                    defaults=defaults,
                )
                if not c:
                    skipped += 1
                    continue
                created += 1

                if shift_on and not record.breaks.filter(is_deleted=False).exists():
                    tea_end = _add_minutes(tea_start, tea_mins)
                    lunch_end = _add_minutes(lunch_start, lunch_mins)
                    AttendanceBreak.objects.create(
                        attendance=record,
                        break_type=BreakType.TEA,
                        start_time=tea_start,
                        end_time=tea_end,
                    )
                    AttendanceBreak.objects.create(
                        attendance=record,
                        break_type=BreakType.LUNCH,
                        start_time=lunch_start,
                        end_time=lunch_end,
                    )
                    breaks_created += 2

        self._log(
            f"  Attendance:   {created} records, {breaks_created} breaks, "
            f"{skipped} skipped (pre-joining or exists)"
        )

    def _log(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))
