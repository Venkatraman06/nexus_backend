"""
Interactive seed command: provisions the initial organisation and CEO admin user.

What it does:
  1. Prompts for organisation name, GST number, admin email, and (optionally) logo
     path (or --org-* / --admin-email CLI flags).
  2. Stores the org info as Django settings / a lightweight JSON sidecar file at
     data/org_profile.json so downstream commands / email templates can read it.
  3. Creates (or ensures) the CEO user in Keycloak under the "Admin" group with
     ALL realm permissions ("*") already configured for that group.
  4. Creates (or updates) the matching Employee record in Django and links it to
     the Keycloak UUID (keycloak_id).
  5. Runs `create_permissions` and `assign_role_permissions` so the Admin group
     gets every permission in permissions.json.
  6. Syncs the user back from Keycloak → Django via KeycloakSyncService.

Credentials:
    username : <prompted at runtime>   (default: ceo@hackersinfotech.com)
    password : ceo@2018                (default — change it from Keycloak afterwards)
    KC group : Admin  (grants is_staff=True, is_superuser=True, is_pmo=True, is_manager=True)

Usage:
    python manage.py seed_initial_org                        # interactive prompts
    python manage.py seed_initial_org --skip-prompts         # use defaults / env vars
    python manage.py seed_initial_org \\
        --org-name "Hackers Infotech" \\
        --org-gst  "33AABCH1234A1ZP" \\
        --admin-email admin@example.com
        # --org-logo is optional; omit to skip logo

    python manage.py seed_initial_org --skip-keycloak        # Django-only (no KC calls)
    python manage.py seed_initial_org --reset                # delete CEO user first
"""

import json
import logging
import os
import shutil
import sys
from pathlib import Path
from datetime import date

from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# Password is intentionally fixed as a default; change it from Keycloak after first login.
CEO_PASSWORD   = "ceo@2018"
CEO_FIRST_NAME = "CEO"
CEO_LAST_NAME  = "Admin"
CEO_KC_GROUP   = "Admin"
CEO_EMP_CODE   = "HIT-CEO"

# Default admin email used when --skip-prompts is supplied or user presses Enter.
_DEFAULT_ADMIN_EMAIL = "ceo@hackersinfotech.com"

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
ORG_PROFILE_PATH = DATA_DIR / "org_profile.json"

# ── Organisational roles (Keycloak groups) to provision ───────────────────────
#
# These map 1-to-1 with the groups defined in role_permissions.json.
# The list is ordered by privilege level (highest first).
ORG_ROLES = [
    "Admin",                    # 1 – Full system access (*)
    "CEO/Founder",              # 2 – Executive: all dashboards + finance + HR visibility
    "HR Admin",                 # 3 – HRMS management
    "PM/Solution Architect",    # 4 – Project + CRM + limited finance
    "Employee",                 # 5 – Standard employee self-service
    "Finance Team",             # 6 – Finance & billing focused
    "Sales/Marketing Team",     # 7 – CRM & lead-gen focused
]

DEPARTMENTS_TO_SEED = [
    "Management",
    "Company Administrative Function",
    "Administration",
    "Human Resource Department",
    "Finance and Accounts Department",
    "Marketing Department",
    "Sales",
    "IT Department",
    "Research and Development",
    "Customer Service Department",
    "The Legal Department",
]

DESIGNATIONS_TO_SEED = [
    "CEO",
    "Director",
    "General Manager",
    "Senior Manager",
    "Manager",
    "Assistant Manager",
    "Team Lead",
    "Senior Executive",
    "Executive",
    "Associate",
    "Junior Associate",
    "Trainee",
    "Intern",
    "Consultant",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _prompt(label: str, default: str = "", required: bool = False, optional: bool = False) -> str:
    """Read a line from stdin with a styled prompt."""
    if optional:
        suffix = f" [{default}] (optional)" if default else " (optional, press Enter to skip)"
    else:
        suffix = f" [{default}]" if default else " (required)"
    while True:
        value = input(f"  {label}{suffix}: ").strip()
        if not value:
            if default:
                return default
            if not required:
                return ""
            print("    ✗  This field is required. Please enter a value.")
        else:
            return value


def _yn(label: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    ans = input(f"  {label} [{hint}]: ").strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes")


def _save_org_profile(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ORG_PROFILE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _copy_logo(src_path: str, org_name: str) -> str | None:
    """Copy a logo file into data/logos/ and return the relative path."""
    if not src_path or not os.path.exists(src_path):
        return None
    logos_dir = DATA_DIR / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(src_path).suffix
    slug = org_name.lower().replace(" ", "_")
    dest = logos_dir / f"{slug}_logo{suffix}"
    shutil.copy2(src_path, dest)
    return str(dest.relative_to(DATA_DIR))


# ── Keycloak helper (self-contained, no circular import) ──────────────────────

class _KeycloakAdminHelper:
    """Thin KC Admin wrapper used only by this command."""

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
        self._group_map: dict[str, str] = {}   # name → id
        self._load_groups()

    def _load_groups(self):
        groups = self._admin.get_groups()
        self._group_map = {g["name"]: g["id"] for g in groups}

    # ── User ─────────────────────────────────────────────────────────────────

    def get_or_create_user(
        self,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        password: str,
        attributes: dict | None = None,
    ) -> str:
        """Upsert user in Keycloak; return KC UUID."""
        payload = {
            "username":  username,
            "email":     email,
            "firstName": first_name,
            "lastName":  last_name,
            "enabled":   True,
            "credentials": [
                {"type": "password", "value": password, "temporary": False}
            ],
        }
        if attributes:
            payload["attributes"] = {k: [v] for k, v in attributes.items()}

        # Try create
        try:
            kc_id = self._admin.create_user(payload, exist_ok=True)
            if kc_id:
                return kc_id
        except Exception:
            pass

        # Already exists — look up by username
        users = self._admin.get_users({"username": username, "exact": True})
        if users:
            kc_id = users[0]["id"]
            # Update password to ensure it matches
            self._admin.set_user_password(kc_id, password, temporary=False)
            return kc_id

        raise RuntimeError(f"Cannot find/create Keycloak user: {username!r}")

    def assign_group(self, kc_id: str, group_name: str) -> None:
        group_id = self._group_map.get(group_name)
        if not group_id:
            logger.warning("Keycloak group %r not found; skipping group assignment.", group_name)
            return
        try:
            self._admin.group_user_add(kc_id, group_id)
        except Exception as exc:
            if "409" not in str(exc) and "Conflict" not in str(exc):
                logger.warning("group_user_add failed (%s → %s): %s", kc_id, group_name, exc)

    def ensure_group(self, group_name: str) -> str:
        """Create the Keycloak group if it doesn't exist; return its ID."""
        if group_name in self._group_map:
            return self._group_map[group_name]
        try:
            self._admin.create_group({"name": group_name})
        except Exception as exc:
            # 409 Conflict means already exists — harmless
            if "409" not in str(exc) and "Conflict" not in str(exc):
                raise
        # Refresh group map after creation
        self._load_groups()
        return self._group_map.get(group_name, "")

    def delete_user_by_username(self, username: str) -> bool:
        users = self._admin.get_users({"username": username, "exact": True})
        if users:
            self._admin.delete_user(users[0]["id"])
            return True
        return False


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Seed initial organisation profile + CEO admin user (Keycloak + Django)"

    def add_arguments(self, parser):
        parser.add_argument("--org-name",    default="", help="Organisation display name")
        parser.add_argument("--org-gst",     default="", help="GSTIN (15-char GST number)")
        parser.add_argument("--org-logo",    default="", help="(Optional) Absolute path to logo image")
        parser.add_argument(
            "--admin-email",
            default="",
            help=f"Admin user email / username (default: {_DEFAULT_ADMIN_EMAIL})",
        )
        parser.add_argument(
            "--skip-prompts",
            action="store_true",
            help="Use CLI flags / env defaults; skip interactive prompts",
        )
        parser.add_argument(
            "--skip-keycloak",
            action="store_true",
            help="Skip all Keycloak calls (create user locally only)",
        )
        parser.add_argument(
            "--skip-permissions",
            action="store_true",
            help="Skip create_permissions and assign_role_permissions steps",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing CEO user (KC + DB) before seeding",
        )

    # ──────────────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        skip_prompts  = options["skip_prompts"]
        skip_kc       = options["skip_keycloak"]
        skip_perm     = options["skip_permissions"]
        do_reset      = options["reset"]

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n╔══════════════════════════════════════════════╗\n"
            "║   Nexus — Initial Organisation Seed Script  ║\n"
            "╚══════════════════════════════════════════════╝\n"
        ))

        # ── Step 1 : Collect org info & admin email ───────────────────────────
        org_name, org_gst, org_logo_path, admin_email = self._collect_org_info(options, skip_prompts)

        # ── Step 2 : Save org profile JSON ────────────────────────────────────
        logo_relative = _copy_logo(org_logo_path, org_name) if org_logo_path else None
        org_profile = {
            "name":       org_name,
            "gst_number": org_gst,
            "logo":       logo_relative,
        }
        _save_org_profile(org_profile)
        self.stdout.write(self.style.SUCCESS(f"\n✔  Org profile saved → {ORG_PROFILE_PATH}"))
        self.stdout.write(f"   Name : {org_name}")
        self.stdout.write(f"   GST  : {org_gst or '(not set)'}")
        self.stdout.write(f"   Logo : {logo_relative or '(not provided)'}")

        # ── Step 2.5 : Seed Departments and Designations ──────────────────────
        self.stdout.write(self.style.HTTP_INFO("\n→ Seeding Departments and Designations …"))
        try:
            from apps.master.models import Department, Designation
            
            dept_created = 0
            for dept_name in DEPARTMENTS_TO_SEED:
                _, created = Department.objects.get_or_create(name=dept_name)
                if created:
                    dept_created += 1
                    
            desig_created = 0
            for desig_name in DESIGNATIONS_TO_SEED:
                _, created = Designation.objects.get_or_create(name=desig_name)
                if created:
                    desig_created += 1

            # Clean up old data not in seed lists
            Department.objects.exclude(name__in=DEPARTMENTS_TO_SEED).delete()
            Designation.objects.exclude(name__in=DESIGNATIONS_TO_SEED).delete()
                    
            self.stdout.write(self.style.SUCCESS(
                f"✔  Master seeding complete: {dept_created} new department(s), {desig_created} new designation(s)."
            ))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  ⚠  Master seeding warning (non-fatal): {exc}"))

        # ── Step 3 : Permission catalog ──────────────────────────────────────
        if not skip_kc and not skip_perm:
            self.stdout.write(self.style.HTTP_INFO("\n→ Pushing permission catalog to Keycloak …"))
            call_command("create_permissions")
            self.stdout.write(self.style.SUCCESS("✔  Permission catalog synced to Keycloak."))

        # ── Step 4 : KC provisioning (groups + CEO user) ─────────────────────
        kc_id = None
        if not skip_kc:
            self.stdout.write(self.style.HTTP_INFO("\n→ Connecting to Keycloak …"))
            try:
                kc = _KeycloakAdminHelper()

                # 4a – Ensure all organisational groups exist ─────────────────
                self.stdout.write(self.style.HTTP_INFO("→ Provisioning organisational roles (groups) …"))
                created_groups: list[str] = []
                skipped_groups: list[str] = []
                for role_name in ORG_ROLES:
                    existing_id = kc._group_map.get(role_name)
                    kc.ensure_group(role_name)
                    if existing_id:
                        skipped_groups.append(role_name)
                    else:
                        created_groups.append(role_name)

                if created_groups:
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✔  Created  : {', '.join(created_groups)}"
                    ))
                if skipped_groups:
                    self.stdout.write(
                        f"  ·  Already existed: {', '.join(skipped_groups)}"
                    )

                # 4b – Assign permissions to all groups ───────────────────────
                if not skip_perm:
                    self.stdout.write(self.style.HTTP_INFO("→ Assigning permissions to Keycloak groups …"))
                    call_command("assign_role_permissions")
                    self.stdout.write(self.style.SUCCESS("✔  Permissions assigned to all groups."))

                # 4c – Provision CEO user ─────────────────────────────────────
                if do_reset:
                    deleted = kc.delete_user_by_username(admin_email)
                    if deleted:
                        self.stdout.write(self.style.WARNING(f"  ⚠  Deleted existing KC user: {admin_email}"))

                kc_id = kc.get_or_create_user(
                    username   = admin_email,
                    email      = admin_email,
                    first_name = CEO_FIRST_NAME,
                    last_name  = CEO_LAST_NAME,
                    password   = CEO_PASSWORD,
                    attributes = {
                        "designation":   "CEO",
                        "department":    "Management",
                        "employee_code": CEO_EMP_CODE,
                        "org_name":      org_name,
                        "org_gst":       org_gst,
                    },
                )
                kc.assign_group(kc_id, CEO_KC_GROUP)

                self.stdout.write(self.style.SUCCESS(
                    f"✔  Keycloak user provisioned: {admin_email}  (KC id: {kc_id})"
                ))
                self.stdout.write(f"   Group: {CEO_KC_GROUP}  (all permissions — Admin = *)")
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"✗  Keycloak provisioning failed: {exc}"))
                self.stdout.write("   Continuing with Django-only setup …")

        # ── Step 5 : Django Employee record ───────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\n→ Creating / updating Django Employee record …"))
        employee = self._ensure_employee(kc_id, org_name, admin_email)
        self.stdout.write(self.style.SUCCESS(
            f"✔  Employee record ready: {employee.username}  "
            f"(PK: {employee.pk}, kc_id: {employee.keycloak_id})"
        ))

        # ── Step 6 : Sync back from Keycloak ──────────────────────────────────
        if not skip_kc and kc_id:
            self.stdout.write(self.style.HTTP_INFO("\n→ Syncing user from Keycloak → Django …"))
            try:
                from apps.accounts.services import KeycloakSyncService
                stats = KeycloakSyncService().sync_all()
                self.stdout.write(self.style.SUCCESS(
                    f"✔  Keycloak sync complete: {stats}"
                ))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  ⚠  Sync warning (non-fatal): {exc}"))

        # ── Done ────────────────────────────────────────────────────────────────
        roles_display = "\n".join(
            f"  {i+1:>2}. {r}" for i, r in enumerate(ORG_ROLES)
        )
        self.stdout.write(self.style.SUCCESS(
            "\n╔══════════════════════════════════════════════╗\n"
            "║   ✔  Initial seed complete!                  ║\n"
            "╚══════════════════════════════════════════════╝"
        ))
        self.stdout.write(f"""
  Organisation : {org_name}
  GST Number   : {org_gst or '(not set)'}
  Logo         : {logo_relative or '(not provided)'}

  CEO Admin User
  ─────────────
  Username     : {admin_email}
  Password     : {CEO_PASSWORD}  ← default; please change this from Keycloak!
  KC Group     : {CEO_KC_GROUP}  → ALL permissions (pmt.*)
  Django flags : is_staff=True | is_superuser=True | is_pmo=True | is_manager=True
  Company      : {org_name}

  Organisational Roles (Keycloak Groups)
  ──────────────────────────────────────
{roles_display}

  Login at   → http://localhost:3000/pmt
  API docs   → http://localhost:8000/pmt/api/docs/
""")

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _collect_org_info(self, options: dict, skip_prompts: bool):
        org_name    = options.get("org_name",    "").strip()
        org_gst     = options.get("org_gst",     "").strip()
        org_logo    = options.get("org_logo",    "").strip()
        admin_email = options.get("admin_email", "").strip()

        if skip_prompts:
            org_name    = org_name    or "Hackers Infotech"
            admin_email = admin_email or _DEFAULT_ADMIN_EMAIL
            return org_name, org_gst, org_logo, admin_email

        self.stdout.write("\n── Organisation Details ──────────────────────────────────────")
        self.stdout.write("  (Press Enter to accept the default shown in [brackets])\n")

        org_name    = _prompt("Organisation name",        org_name    or "Hackers Infotech", required=True)
        org_gst     = _prompt("GST Number (GSTIN)",       org_gst)
        org_logo    = _prompt("Logo file path (absolute)", org_logo,   optional=True)
        admin_email = _prompt(
            "Admin email (username)",
            admin_email or _DEFAULT_ADMIN_EMAIL,
            required=True,
        )

        if org_logo and not os.path.exists(org_logo):
            self.stdout.write(self.style.WARNING(
                f"  ⚠  Logo file not found at: {org_logo!r} — skipping logo."
            ))
            org_logo = ""

        return org_name, org_gst, org_logo, admin_email

    def _ensure_employee(self, kc_id: str | None, org_name: str, admin_email: str):
        """Create or update the CEO Employee record in Django."""
        from apps.accounts.models import Employee

        # Look up by username first (fall back to _DEFAULT_ADMIN_EMAIL for migration safety)
        emp = (
            Employee.base_objects.filter(username=admin_email).first()
            or Employee.base_objects.filter(username=_DEFAULT_ADMIN_EMAIL).first()
        )

        from apps.master.models import Department, Designation
        desig_obj = Designation.objects.filter(name="CEO").first()
        dept_obj = Department.objects.filter(name="Management").first()

        ceo_defaults = {
            "email":          admin_email,
            "first_name":     CEO_FIRST_NAME,
            "last_name":      CEO_LAST_NAME,
            "employee_code":  CEO_EMP_CODE,
            "designation":    "CEO",
            "department":     "Management",
            "designation_ref": desig_obj,
            "department_ref":  dept_obj,
            "keycloak_group": CEO_KC_GROUP,
            "is_staff":       True,
            "is_superuser":   True,
            "is_pmo":         True,
            "is_manager":     True,
            "is_active":      True,
            "company":        org_name,
            "joining_date":   date(2018, 1, 1),
        }
        if kc_id:
            ceo_defaults["keycloak_id"] = kc_id

        if emp is None:
            emp = Employee(**ceo_defaults, username=admin_email)
            emp.set_password(CEO_PASSWORD)
            emp.save()
        else:
            # Always update username/email to the newly provided value
            emp.username = admin_email
            for k, v in ceo_defaults.items():
                setattr(emp, k, v)
            emp.set_password(CEO_PASSWORD)
            emp.save()

        return emp
