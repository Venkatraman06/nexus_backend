import json
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase
from django.core.management import call_command
from io import StringIO

from apps.accounts.group_config import resolve_group_flags, PMO_GROUPS, MANAGER_GROUPS
from apps.accounts.views import KEYCLOAK_DEFAULT_GROUPS


class KeycloakRoleConfigTests(SimpleTestCase):
    databases = set()

    def test_role_permissions_json_contains_new_roles(self):
        role_file = Path(settings.BASE_DIR) / "role_permissions.json"
        self.assertTrue(role_file.exists())
        with role_file.open(encoding="utf-8") as f:
            role_map = json.load(f)
        self.assertIn("Co-Founder", role_map)
        self.assertIn("CTO", role_map)
        self.assertEqual(role_map["Co-Founder"], ["*"])
        self.assertEqual(role_map["CTO"], ["*"])

    def test_resolve_group_flags_for_co_founder_and_cto(self):
        co_founder_flags = resolve_group_flags("Co-Founder")
        self.assertTrue(co_founder_flags["is_pmo"])
        self.assertTrue(co_founder_flags["is_manager"])

        cto_flags = resolve_group_flags("CTO")
        self.assertTrue(cto_flags["is_pmo"])
        self.assertTrue(cto_flags["is_manager"])

    def test_keycloak_default_groups_contains_new_roles(self):
        self.assertIn("Co-Founder", KEYCLOAK_DEFAULT_GROUPS)
        self.assertIn("CTO", KEYCLOAK_DEFAULT_GROUPS)

    def test_assign_role_permissions_dry_run(self):
        out = StringIO()
        call_command("assign_role_permissions", dry_run=True, stdout=out)
        output = out.getvalue()
        self.assertIn("Co-Founder", output)
        self.assertIn("CTO", output)
