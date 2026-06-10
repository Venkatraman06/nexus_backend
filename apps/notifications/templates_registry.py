"""Default notification templates — synced to DB on startup/migrate."""

from apps.notifications.constants import EventType, NotificationSeverity

DEFAULT_TEMPLATES = [
    {
        "event_type": EventType.TICKET_ASSIGNED,
        "title_template": "Ticket assigned: {ticket_id}",
        "message_template": "You have been assigned to \"{title}\" on project {project_name}.",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "/tickets/{reference_id}",
    },
    {
        "event_type": EventType.TICKET_DUE_TODAY,
        "title_template": "Ticket due today: {ticket_id}",
        "message_template": "\"{title}\" is due today ({due_date}). Please complete or update the ticket.",
        "severity": NotificationSeverity.WARNING,
        "default_action_url": "/tickets/{reference_id}",
    },
    {
        "event_type": EventType.PROJECT_ALLOCATION,
        "title_template": "Project allocation: {project_name}",
        "message_template": "You have been allocated to project \"{project_name}\" ({allocation_pct}% from {start_date}).",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "/projects/{project_id}",
    },
    {
        "event_type": EventType.PROJECT_MANAGER_ASSIGNED,
        "title_template": "Project manager role: {project_name}",
        "message_template": "You have been assigned as project manager for \"{project_name}\".",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "/projects/{reference_id}",
    },
    {
        "event_type": EventType.PROJECT_DUE_REMINDER,
        "title_template": "Project ending soon: {project_name}",
        "message_template": "Project \"{project_name}\" ends on {end_date}. Please review deliverables.",
        "severity": NotificationSeverity.WARNING,
        "default_action_url": "/projects/{reference_id}",
    },
    {
        "event_type": EventType.TIMESHEET_SUBMITTED,
        "title_template": "Timesheet submitted: {employee_name}",
        "message_template": "{employee_name} submitted timesheet for week {week_start} – {week_end} ({total_hours}h).",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "/timesheets/reporting",
    },
    {
        "event_type": EventType.TIMESHEET_APPROVED,
        "title_template": "Timesheet approved",
        "message_template": "Your timesheet for week {week_start} – {week_end} has been approved.",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "/timesheets",
    },
    {
        "event_type": EventType.TIMESHEET_REJECTED,
        "title_template": "Timesheet rejected",
        "message_template": "Your timesheet for week {week_start} – {week_end} was rejected. {comment}",
        "severity": NotificationSeverity.WARNING,
        "default_action_url": "/timesheets",
    },
    {
        "event_type": EventType.EMPLOYEE_ONBOARDED,
        "title_template": "New employee onboarded: {employee_name}",
        "message_template": "{employee_name} ({employee_code}) has joined as {designation}.",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "/employees/{reference_id}",
    },
    {
        "event_type": EventType.LEAVE_REQUESTED,
        "title_template": "Leave request: {employee_name}",
        "message_template": "{employee_name} requested {leave_type} from {start_date} to {end_date} ({days_count} days).",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "/employees/leave-requests",
    },
    {
        "event_type": EventType.PAYROLL_FINALIZED,
        "title_template": "Payslip finalized: {period}",
        "message_template": "Your payslip for {period} has been finalized. Net pay: {net_pay}.",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "/employees/payroll",
    },
    {
        "event_type": EventType.INVOICE_DUE_REMINDER,
        "title_template": "Invoice due tomorrow: {invoice_number}",
        "message_template": "Invoice {invoice_number} for {client_name} (₹{amount}) is due on {due_date}.",
        "severity": NotificationSeverity.WARNING,
        "default_action_url": "/payment/invoices/{reference_id}",
    },
    {
        "event_type": EventType.MILESTONE_DUE_REMINDER,
        "title_template": "Milestone due tomorrow: {milestone_name}",
        "message_template": "Milestone \"{milestone_name}\" on {project_name} is due on {due_date}.",
        "severity": NotificationSeverity.WARNING,
        "default_action_url": "/payment/milestones",
    },
    {
        "event_type": EventType.PAYMENT_OVERDUE,
        "title_template": "Payment overdue: {invoice_number}",
        "message_template": "Invoice {invoice_number} is {days_overdue} day(s) overdue. Outstanding: ₹{outstanding}.",
        "severity": NotificationSeverity.URGENT,
        "default_action_url": "/payment/invoices/{reference_id}",
    },
    {
        "event_type": EventType.SOCIAL_POST_PENDING_APPROVAL,
        "title_template": "Post pending approval: {title}",
        "message_template": "{created_by_name} submitted a new post \"{title}\" for approval — {content_preview}",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "",
    },
    {
        "event_type": EventType.SOCIAL_POST_PUBLISHED,
        "title_template": "New post: {title}",
        "message_template": "{created_by_name} published a new post: \"{title}\" — {content_preview}",
        "severity": NotificationSeverity.INFO,
        "default_action_url": "",
    },
    {
        "event_type": EventType.FOLLOWUP_DUE_TODAY,
        "title_template": "Follow-up today: {type_label}",
        "message_template": "\"{title}\" ({type_label}) is scheduled for today{time_suffix}.",
        "severity": NotificationSeverity.WARNING,
        "default_action_url": "/followups?view=calendar",
    },
    {
        "event_type": EventType.FOLLOWUP_OVERDUE,
        "title_template": "Follow-up overdue: {type_label}",
        "message_template": "\"{title}\" ({type_label}) is {days_overdue} day(s) overdue (due {due_date}). Please complete or reschedule.",
        "severity": NotificationSeverity.URGENT,
        "default_action_url": "/followups",
    },
]


def sync_templates():
    from apps.notifications.models import NotificationTemplate

    for tpl in DEFAULT_TEMPLATES:
        NotificationTemplate.objects.update_or_create(
            event_type=tpl["event_type"],
            defaults={
                "title_template": tpl["title_template"],
                "message_template": tpl["message_template"],
                "severity": tpl["severity"],
                "default_action_url": tpl.get("default_action_url", ""),
                "supported_channels": ["in_app"],
            },
        )
