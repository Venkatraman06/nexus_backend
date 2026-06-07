# Demo data seed (fresh database)

Use this after `migrate` on an empty PostgreSQL database with Keycloak realm configured.

## Quick start

```bash
cd backend
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_demo_data
```

Postgres-only (no Keycloak user/permission sync):

```bash
./venv/bin/python manage.py seed_demo_data --skip-keycloak
```

Reset and re-seed:

```bash
./venv/bin/python manage.py seed_demo_data --reset
```

## What gets seeded

| Step | Command | Data |
|------|---------|------|
| 1 | `create_permissions` | All `pmt.*` realm roles in Keycloak |
| 2 | `assign_role_permissions` | Group → permission mapping from `role_permissions.json` |
| 3 | `seed_workflow` | Project: Enquiry → Followup → Kickoff → Ongoing → Close / Cancelled |
| | | Ticket: Todo → In Progress → Resolved → Done |
| 4 | `migrate_seed_data` | Master CSVs, 12 employees (org chart), weekday attendance May 2026 → today |
| 5 | `seed_crm_finance` | 5 demo clients, finance docs (quotations, invoices), payments, expenses |
| 6 | `seed_pmo_demo` | Pipeline projects, internal PMT build, **ERP kickoff** (epic hierarchy), **cyber training** (closed + invoice), allocations, tickets, comments, history, work logs |

## Employees (org chart)

| Code | Name | Role | Manager | Keycloak group |
|------|------|------|---------|----------------|
| HIT-001 | Chandraprakash Sankar | CEO | — | Admin |
| HIT-002 | Karthicksankar Kathirvel | PM & Architect | HIT-001 | Project Manager |
| HIT-004 | Shruthi Nadhitha | HR | HIT-001 | HR & Admin |
| HIT-005 | Gowri Ganesh | Senior Engineer | HIT-002 | Employee |
| HIT-003 | Gowrisankar K | Team Lead | HIT-002 | Employee |
| HIT-006 | Kiruba Kaliyappan | Senior Engineer | HIT-002 | Employee |
| HIT-007–012 | Interns | Intern | respective lead | Employee |

Source: `backend/data/employees.csv`

## Featured demo projects

| Code | Name | Dates | State | Team |
|------|------|-------|-------|------|
| `PRJ-260010` | ERP Project Kickoff | Jun 1 – Jun 25 | Kickoff | Karthick (PM), Gowri (lead), Kavya & Samyuktha (dev), Kiruba (QA) |
| `TRN-260002` | Cyber Security Training | Jun 2 – Jun 4 | Close | Chandraprakash (delivery + PM) — invoice Jun 5, 60% paid Jun 7 |
| `INT-260001` | PMT Product Build | ongoing | internal product tickets |

ERP tickets use parent/child hierarchy: 4 epics → stories → tasks/bugs with comments and audit history.

## Keycloak groups & permissions

| Group | Access |
|-------|--------|
| **Admin** | Full access (CEO) |
| **HR & Admin** | HRMS, attendance, leave, employees |
| **Project Manager** | Projects, allocations, tickets, timesheets, CRM, finance, payments |
| **Employee** | Own dashboard, assigned work, timesheets, attendance |

Edit `backend/role_permissions.json` and re-run `assign_role_permissions`.

## Run steps individually

```bash
./venv/bin/python manage.py create_permissions
./venv/bin/python manage.py assign_role_permissions
./venv/bin/python manage.py seed_workflow
./venv/bin/python manage.py migrate_seed_data
./venv/bin/python manage.py seed_crm_finance
./venv/bin/python manage.py seed_pmo_demo
```

## Default passwords

- Employee code (e.g. `HIT-009`) or `ChangeMe@123` if not set in CSV.
