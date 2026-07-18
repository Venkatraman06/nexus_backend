"""
Management command to detect and fix circular parent-child references among tickets.

Circular references (e.g. Ticket A.parent = B and B.parent = A) cause tickets to
disappear from the tree view and can lead to infinite recursion in descendant
traversal. This command scans all tickets, detects cycles, and breaks them by
setting parent = NULL on the ticket that creates the cycle.

Usage:
    python manage.py fix_circular_ticket_parents
    python manage.py fix_circular_ticket_parents --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Detect and fix circular parent-child references among tickets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report cycles without making changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        from apps.tickets.models import Ticket

        all_tickets = {
            str(t.id): t
            for t in Ticket.objects.filter(is_deleted=False)
            .exclude(parent__isnull=True)
            .only("id", "parent_id", "ticket_id", "title")
        }

        fixed = 0
        total_cycles = 0

        for ticket_id, ticket in all_tickets.items():
            # Walk up the parent chain — if we ever revisit an ID, it's a cycle
            seen = set()
            current = ticket
            has_cycle = False
            cycle_path = []

            while current.parent_id and str(current.parent_id) in all_tickets:
                parent_id_str = str(current.parent_id)
                if parent_id_str in seen:
                    has_cycle = True
                    break
                seen.add(parent_id_str)
                cycle_path.append(f"{current.ticket_id} → {all_tickets[parent_id_str].ticket_id}")
                current = all_tickets[parent_id_str]

            if has_cycle:
                total_cycles += 1
                # The cycle starts at the top of the path; break it at the last
                # ticket in the cycle (the one whose parent points back into the cycle)
                last_in_cycle = all_tickets[cycle_path[-1].split(" → ")[1]]

                self.stdout.write(self.style.WARNING(
                    f"  [CYCLE] {' → '.join(cycle_path)} → {last_in_cycle.ticket_id}"
                ))
                self.stdout.write(
                    f"    Breaking: setting {last_in_cycle.ticket_id} "
                    f"({last_in_cycle.title[:60]}) parent → NULL"
                )

                if not dry_run:
                    with transaction.atomic():
                        last_in_cycle.parent = None
                        last_in_cycle.save(update_fields=["parent"])
                    fixed += 1

        if total_cycles == 0:
            self.stdout.write(self.style.SUCCESS("No circular references found. All tickets have valid parent chains."))
        else:
            action = "Would fix" if dry_run else "Fixed"
            self.stdout.write(
                self.style.SUCCESS(f"\n{action} {fixed} circular reference(s) out of {total_cycles} cycle(s) detected.")
            )
