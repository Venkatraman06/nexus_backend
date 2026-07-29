from datetime import timedelta
from django.core.management.base import BaseCommand
from apps.attendance.models import LeaveRequest, LeaveRequestStatus, AttendanceRecord, AttendanceStatus


class Command(BaseCommand):
    help = "Sync all existing approved leave requests into AttendanceRecord as ON_LEAVE."

    def handle(self, *args, **options):
        approved_leaves = LeaveRequest.objects.filter(
            status=LeaveRequestStatus.APPROVED,
            is_deleted=False
        ).select_related("employee", "leave_type")

        synced_count = 0
        for leave in approved_leaves:
            if not leave.start_date or not leave.end_date or not leave.employee:
                continue
            curr_d = leave.start_date
            while curr_d <= leave.end_date:
                rec, _ = AttendanceRecord.objects.get_or_create(
                    employee=leave.employee,
                    date=curr_d,
                    defaults={
                        "status": AttendanceStatus.ON_LEAVE,
                        "notes": f"Leave: {leave.leave_type.name if leave.leave_type else 'Approved Leave'}"
                    }
                )
                if rec.status not in (AttendanceStatus.PRESENT, AttendanceStatus.WFH):
                    rec.status = AttendanceStatus.ON_LEAVE
                    rec.notes = f"Leave: {leave.leave_type.name if leave.leave_type else 'Approved Leave'}"
                    rec.save(update_fields=["status", "notes"])
                    synced_count += 1
                curr_d += timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully synced {synced_count} attendance day record(s) for approved leaves.")
        )
