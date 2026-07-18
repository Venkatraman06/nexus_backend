from django.db import models


class WorkItemType(models.TextChoices):
    TASK = "TASK", "Task"
    BUG = "BUG", "Bug"
    CR = "CR", "Change Request"


class WorkItemStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    IN_REVIEW = "IN_REVIEW", "In Review"
    DONE = "DONE", "Done"
    CLOSED = "CLOSED", "Closed"
    REOPENED = "REOPENED", "Reopened"


class Priority(models.TextChoices):
    CRITICAL = "CRITICAL", "Critical"
    HIGH = "HIGH", "High"
    MEDIUM = "MEDIUM", "Medium"
    LOW = "LOW", "Low"


class EmployeeStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    ON_LEAVE = "ON_LEAVE", "On Leave"
    RESIGNED = "RESIGNED", "Resigned"


class WorkLogCategory(models.TextChoices):
    BILLABLE     = "BILLABLE",     "Billable"
    NON_BILLABLE = "NON_BILLABLE", "Non-Billable"
    INTERNAL     = "INTERNAL",     "Internal"
    TRAINING     = "TRAINING",     "Training"
    SUPPORT      = "SUPPORT",      "Support"


class TimesheetStatus(models.TextChoices):
    DRAFT     = "DRAFT",     "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED  = "APPROVED",  "Approved"
    REJECTED  = "REJECTED",  "Rejected"


DAILY_HOURS = 8
MONTHLY_WORKING_DAYS = 22
MONTHLY_CAPACITY_HOURS = DAILY_HOURS * MONTHLY_WORKING_DAYS
OVER_ALLOCATION_THRESHOLD = 100
AT_RISK_OVERRUN_PERCENT = 1.2
AT_RISK_OVERDUE_PERCENT = 0.20
