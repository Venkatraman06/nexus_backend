"""
Management command: clear_reimbursements
=========================================
Deletes ALL reimbursement-related data:

  1. ReimbursementAuditLog   (cascade-safe, deleted first)
  2. ReimbursementAttachment (cascade-safe, deleted first)
  3. EmployeeReimbursement   (all claims regardless of status)
  4. CompanyExpense records  that were auto-created from approved
     reimbursements (identified via the reverse source_reimbursement
     relation).  Their ExpenseAttachment children are also removed.

Usage
-----
    python manage.py clear_reimbursements              # dry-run preview
    python manage.py clear_reimbursements --confirm    # actually delete

Safety
------
  * Default mode is DRY-RUN — nothing is deleted unless --confirm is passed.
  * Prints exactly what will be / was deleted.
  * Wrapped in a single atomic transaction so it either succeeds fully
    or rolls back entirely.
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Remove all reimbursement claims and their linked company expenses."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Actually perform the deletion. Without this flag the command runs in dry-run mode.",
        )

    def handle(self, *args, **options):
        from apps.expenses.models import (
            EmployeeReimbursement,
            ReimbursementAttachment,
            ReimbursementAuditLog,
            CompanyExpense,
            ExpenseAttachment,
        )

        dry_run = not options["confirm"]

        # ── 1. Count what will be deleted ────────────────────────────────
        audit_log_qs      = ReimbursementAuditLog.objects.all()
        attachment_qs     = ReimbursementAttachment.objects.all()
        reimbursement_qs  = EmployeeReimbursement.objects.all()

        # Company expenses that originated from a reimbursement claim
        linked_expense_qs = CompanyExpense.objects.filter(
            source_reimbursement__isnull=False
        ).distinct()
        linked_exp_attach_qs = ExpenseAttachment.objects.filter(
            expense__in=linked_expense_qs
        )

        counts = {
            "ReimbursementAuditLog":   audit_log_qs.count(),
            "ReimbursementAttachment": attachment_qs.count(),
            "EmployeeReimbursement":   reimbursement_qs.count(),
            "Linked ExpenseAttachment": linked_exp_attach_qs.count(),
            "Linked CompanyExpense":   linked_expense_qs.count(),
        }

        # ── 2. Print summary ──────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=" * 56))
        mode = "DRY-RUN (pass --confirm to apply)" if dry_run else "LIVE DELETE"
        self.stdout.write(self.style.WARNING(f"  clear_reimbursements  [{mode}]"))
        self.stdout.write(self.style.WARNING("=" * 56))
        for model, count in counts.items():
            colour = self.style.SUCCESS if count == 0 else self.style.ERROR
            self.stdout.write(f"  {model:<30} {count:>6} rows")
        self.stdout.write(self.style.WARNING("=" * 56))
        self.stdout.write("")

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    "Dry-run complete — no data was changed.\n"
                    "Run with --confirm to permanently delete the rows above."
                )
            )
            return

        # ── 3. Delete inside a single atomic transaction ──────────────────
        with transaction.atomic():
            n_audit   = audit_log_qs.delete()[0]
            n_rattach = attachment_qs.delete()[0]
            n_reimb   = reimbursement_qs.delete()[0]
            n_eattach = linked_exp_attach_qs.delete()[0]
            n_expense = linked_expense_qs.delete()[0]

        self.stdout.write(self.style.SUCCESS("Deletion complete:"))
        self.stdout.write(f"  ReimbursementAuditLog deleted   : {n_audit}")
        self.stdout.write(f"  ReimbursementAttachment deleted : {n_rattach}")
        self.stdout.write(f"  EmployeeReimbursement deleted   : {n_reimb}")
        self.stdout.write(f"  ExpenseAttachment (linked) del  : {n_eattach}")
        self.stdout.write(f"  CompanyExpense (linked) deleted : {n_expense}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("All reimbursement data has been cleared."))
