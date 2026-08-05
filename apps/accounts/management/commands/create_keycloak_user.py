from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.accounts.services import KeycloakSyncService
from keycloak import KeycloakAdmin

class Command(BaseCommand):
    help = "Create a new user in Keycloak and sync them into the Django database"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, required=True, help="Username of the user")
        parser.add_argument("--password", type=str, required=True, help="Password of the user")
        parser.add_argument("--first-name", type=str, default="", help="First name of the user")
        parser.add_argument("--last-name", type=str, default="", help="Last name of the user")
        parser.add_argument("--email", type=str, default="", help="Email of the user")
        parser.add_argument("--group", type=str, default="Employee", help="Keycloak group (e.g. Employee, Admin, HR & Admin, Project Manager)")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        first_name = options["first_name"] or username
        last_name = options["last_name"] or ""
        email = options["email"] or f"{username.lower()}@hackersinfotech.com"
        group_name = options["group"]

        self.stdout.write(f"Connecting to Keycloak to create user '{username}'...")

        try:
            kc_admin = KeycloakAdmin(
                server_url=settings.KEYCLOAK_SERVER_URL,
                realm_name=settings.KEYCLOAK_REALM,
                client_id=settings.KEYCLOAK_CLIENT_ID,
                client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
                verify=True,
            )

            # Get groups
            groups = kc_admin.get_groups()
            group_map = {g["name"]: g["id"] for g in groups}

            # Check if exists
            found = kc_admin.get_users({"username": username, "exact": True})
            if found:
                kc_id = found[0]["id"]
                self.stdout.write(self.style.WARNING(f"User '{username}' already exists in Keycloak (ID: {kc_id})"))
            else:
                user_payload = {
                    "username": username,
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "credentials": [
                        {"type": "password", "value": password, "temporary": False}
                    ],
                    "attributes": {
                        "designation": [group_name],
                        "department": ["Engineering" if group_name != "Admin" else "Management"],
                    },
                }
                kc_id = kc_admin.create_user(user_payload, exist_ok=True)
                if not kc_id:
                    found_users = kc_admin.get_users({"username": username, "exact": True})
                    if found_users:
                        kc_id = found_users[0]["id"]
                    else:
                        raise CommandError("Failed to retrieve ID for created Keycloak user")
                self.stdout.write(self.style.SUCCESS(f"User '{username}' created in Keycloak (ID: {kc_id})"))

            # Add to group
            if group_name in group_map:
                kc_admin.group_user_add(kc_id, group_map[group_name])
                self.stdout.write(f"Added user to Keycloak group: {group_name}")
            else:
                self.stdout.write(self.style.WARNING(f"Group '{group_name}' not found in Keycloak. Skipping group mapping."))

            # Reset password
            kc_admin.set_user_password(kc_id, password, temporary=False)

            # Run sync
            self.stdout.write("Running Django database synchronization...")
            result = KeycloakSyncService().sync_all()
            self.stdout.write(self.style.SUCCESS(
                f"Sync complete — created: {result['created']}, "
                f"updated: {result['updated']}, skipped: {result['skipped']}, "
                f"errors: {result['errors']}"
            ))

        except Exception as exc:
            raise CommandError(f"Operation failed: {exc}")
