"""Notification event types, reference types, and delivery channels."""

from django.db import models


class NotificationChannel(models.TextChoices):
    IN_APP = "in_app", "In-App"
    EMAIL = "email", "Email"
    PUSH = "push", "Push"
    SLACK = "slack", "Slack"
    TEAMS = "teams", "Microsoft Teams"
    WHATSAPP = "whatsapp", "WhatsApp"


class NotificationSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    URGENT = "urgent", "Urgent"


class ReferenceType(models.TextChoices):
    TICKET = "ticket", "Ticket"
    PROJECT = "project", "Project"
    ALLOCATION = "allocation", "Allocation"
    TIMESHEET = "timesheet", "Timesheet"
    EMPLOYEE = "employee", "Employee"
    LEAVE = "leave", "Leave Request"
    PAYROLL = "payroll", "Payroll"
    INVOICE = "invoice", "Invoice"
    MILESTONE = "milestone", "Milestone"
    PAYMENT = "payment", "Payment"
    FOLLOWUP = "followup", "Follow-up"
    SOCIAL_POST = "social_post", "Social Post"


class EventType(models.TextChoices):
    TICKET_ASSIGNED = "ticket.assigned", "Ticket Assigned"
    TICKET_DUE_TODAY = "ticket.due_today", "Ticket Due Today"
    PROJECT_ALLOCATION = "project.allocation", "Project Allocation"
    PROJECT_MANAGER_ASSIGNED = "project.manager_assigned", "Project Manager Assigned"
    PROJECT_DUE_REMINDER = "project.due_reminder", "Project Due Reminder"
    TIMESHEET_SUBMITTED = "timesheet.submitted", "Timesheet Submitted"
    TIMESHEET_APPROVED = "timesheet.approved", "Timesheet Approved"
    TIMESHEET_REJECTED = "timesheet.rejected", "Timesheet Rejected"
    EMPLOYEE_ONBOARDED = "employee.onboarded", "Employee Onboarded"
    LEAVE_REQUESTED = "leave.requested", "Leave Requested"
    PAYROLL_FINALIZED = "payroll.finalized", "Payroll Finalized"
    INVOICE_DUE_REMINDER = "invoice.due_reminder", "Invoice Due Reminder"
    MILESTONE_DUE_REMINDER = "milestone.due_reminder", "Milestone Due Reminder"
    PAYMENT_OVERDUE = "payment.overdue", "Payment Overdue"
    FOLLOWUP_DUE_TODAY = "followup.due_today", "Follow-up Due Today"
    FOLLOWUP_OVERDUE = "followup.overdue", "Follow-up Overdue"
    SOCIAL_POST_PENDING_APPROVAL = "social_post.pending_approval", "Social Post Pending Approval"
    SOCIAL_POST_PUBLISHED = "social_post.published", "Social Post Published"


# Channels enabled today — extend without changing call sites.
ACTIVE_CHANNELS = [NotificationChannel.IN_APP]
