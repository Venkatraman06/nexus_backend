"""Notification event types, reference types, and delivery channels."""

from django.db import models


class NotificationChannel(models.TextChoices):
    IN_APP = "in_app", "In-App"
    EMAIL = "email", "Email"
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
    MEETING = "meeting", "Meeting"
    SOCIAL_POST = "social_post", "Social Post"
    TODO = "todo", "To-Do"
    CHAT_MESSAGE = "chat_message", "Chat Message"
    REIMBURSEMENT = "reimbursement", "Reimbursement Claim"


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
    FOLLOWUP_ASSIGNED = "followup.assigned", "Follow-up Assigned"
    FOLLOWUP_COMMENTED = "followup.commented", "Follow-up Commented"
    FOLLOWUP_UPDATED = "followup.updated", "Follow-up Updated"
    MEETING_DUE_TODAY = "meeting.due_today", "Meeting Due Today"
    MEETING_OVERDUE = "meeting.overdue", "Meeting Overdue"
    MEETING_ASSIGNED = "meeting.assigned", "Meeting Assigned"
    MEETING_COMMENTED = "meeting.commented", "Meeting Commented"
    MEETING_UPDATED = "meeting.updated", "Meeting Updated"
    SOCIAL_POST_PENDING_APPROVAL = "social_post.pending_approval", "Social Post Pending Approval"
    SOCIAL_POST_PUBLISHED = "social_post.published", "Social Post Published"
    TODO_ASSIGNED = "todo.assigned", "To-Do Assigned"
    TODO_TRANSITIONED = "todo.transitioned", "To-Do Transitioned"
    TODO_COMMENTED = "todo.commented", "To-Do Commented"
    TODO_UPDATED = "todo.updated", "To-Do Updated"
    CHAT_MESSAGE_NEW = "chat.message.new", "New Chat Message"
    REIMBURSEMENT_SUBMITTED = "reimbursement.submitted", "Reimbursement Submitted"
    REIMBURSEMENT_APPROVED  = "reimbursement.approved", "Reimbursement Approved"
    REIMBURSEMENT_REJECTED  = "reimbursement.rejected", "Reimbursement Rejected"
    REIMBURSEMENT_INFO_REQUESTED = "reimbursement.info_requested", "Reimbursement Info Requested"
    REIMBURSEMENT_PAID      = "reimbursement.paid", "Reimbursement Paid"



# Channels enabled today — extend without changing call sites.
ACTIVE_CHANNELS = [NotificationChannel.IN_APP]
