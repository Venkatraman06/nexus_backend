# Database table naming

All tables use a **module prefix** so schema matches app areas (Dashboard / Master / HRMS / Project MS / Policy).

Pattern: `{module}_{entity}` (snake_case).

## Master — HRMS (employee)

| Model | Table |
|-------|-------|
| Designation | `master_employee_designation` |
| Department | `master_employee_department` |
| Location | `master_employee_location` |
| Grade | `master_employee_grade` |
| EmploymentType | `master_employee_employment_type` |
| ShiftCategory | `master_employee_shift_category` |
| RateCard | `master_employee_rate_card` |

## Master — Client

| Model | Table |
|-------|-------|
| ClientCategory | `master_client_category` |

## Master — Project

| Model | Table |
|-------|-------|
| BusinessType | `master_project_business_type` |
| BillingType | `master_project_billing_type` |

## Master — Workflow

| Model | Table |
|-------|-------|
| WorkflowGroup | `master_workflow_group` |
| State | `master_workflow_state` |
| Transition | `master_workflow_transition` |
| Proceeding | `master_workflow_proceeding` |

## HRMS

| Model | Table |
|-------|-------|
| Employee | `hrms_employee` |
| EmployeeCertificate | `hrms_employee_certificate` |
| AttendanceRecord | `hrms_attendance_record` |
| AttendanceBreak | `hrms_attendance_break` |
| LeaveType | `hrms_leave_type` |
| LeaveBalance | `hrms_leave_balance` |
| LeaveRequest | `hrms_leave_request` |
| Payroll | `hrms_payroll` |
| HRComplianceDocument | `hrms_compliance_document` |

## Policy

| Model | Table |
|-------|-------|
| PolicyDocument | `policy_document` |

## Project MS

| Model | Table |
|-------|-------|
| Client | `project_client` |
| Project | `project_project` |
| ProjectHistory | `project_history` |
| Epic | `project_epic` |
| Story | `project_story` |
| WorkItem | `project_work_item` |
| WorkItemAttachment | `project_work_item_attachment` |
| WorkLog | `project_work_log` |
| Allocation | `project_allocation` |

Django model class names are unchanged; only `Meta.db_table` values use these names.

For **new databases**, run `migrate` after pulling (squashed `0001_initial` per app). For **existing databases**, add `AlterModelTable` migrations or recreate the DB — see `FRESH_DATABASE_MIGRATIONS.md`.
