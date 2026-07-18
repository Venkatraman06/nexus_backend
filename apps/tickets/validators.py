from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

TICKET_ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_ticket_attachment_file(file) -> None:
    """Reject attachments larger than 5 MB."""
    if file and file.size > TICKET_ATTACHMENT_MAX_BYTES:
        raise serializers.ValidationError("Attachment size cannot exceed 5 MB.")


def validate_ticket_against_project(
    *,
    project,
    due_date=None,
    original_estimate=None,
) -> None:
    """Raise ValidationError when ticket dates/estimate fall outside project bounds."""
    if not project:
        return

    today = timezone.localdate()

    if due_date is not None:
        if due_date < today:
            raise serializers.ValidationError(
                {"due_date": "Due date cannot be in the past."}
            )
        if project.start_date and due_date < project.start_date:
            raise serializers.ValidationError(
                {"due_date": f"Due date cannot be before project start ({project.start_date:%d %b %Y})."}
            )
        if project.end_date and due_date > project.end_date:
            raise serializers.ValidationError(
                {"due_date": f"Due date cannot be after project end ({project.end_date:%d %b %Y})."}
            )

    if original_estimate is not None and project.estimated_hours:
        max_hours = Decimal(str(project.estimated_hours))
        estimate = Decimal(str(original_estimate))
        if estimate > max_hours:
            raise serializers.ValidationError(
                {
                    "original_estimate": (
                        f"Original estimate cannot exceed project estimate of {max_hours}h."
                    )
                }
            )
