from datetime import date

from rest_framework import serializers


def validate_due_date_on_write(
    due_date: date | None,
    *,
    previous_due_date: date | None = None,
    is_create: bool = False,
) -> None:
    """Block new items on past dates; allow keeping or moving to today/future when editing."""
    if due_date is None:
        return
    today = date.today()
    if is_create:
        if due_date < today:
            raise serializers.ValidationError(
                {"due_date": "Due date cannot be in the past."}
            )
        return
    if due_date < today and due_date != previous_due_date:
        raise serializers.ValidationError(
            {"due_date": "Due date cannot be moved to a past date."}
        )
