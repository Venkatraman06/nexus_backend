# Fresh database migrations

All PMT app migrations were squashed into a **single `0001_initial.py` per app** for a clean install on a new database.

Table names use module prefixes (`master_employee_*`, `hrms_*`, `project_*`, etc.). See [DATABASE_TABLE_NAMING.md](./DATABASE_TABLE_NAMING.md).

## Apps included

| App | Migration file |
|-----|----------------|
| `master` | `apps/master/migrations/0001_initial.py` |
| `accounts` | `apps/accounts/migrations/0001_initial.py` |
| `pmt_workflow` | `packages/workflow/migrations/0001_initial.py` |
| `projects` | `apps/projects/migrations/0001_initial.py` |
| `workitems` | `apps/workitems/migrations/0001_initial.py` |
| `allocation` | `apps/allocation/migrations/0001_initial.py` |
| `attendance` | `apps/attendance/migrations/0001_initial.py` |
| `payroll` | `apps/payroll/migrations/0001_initial.py` |
| `compliance` | `apps/compliance/migrations/0001_initial.py` |

## New database setup

```bash
cd backend
# Point DATABASE_URL / .env to your new empty database
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_demo_data      # full demo: workflow, users, projects, CRM
# Or step-by-step — see docs/SEED_DEMO_DATA.md
```

## Existing database (do not use squash)

If you already have data in production/staging, **do not** replace migration history on that DB. This layout is only for **new** databases.

To reset a dev DB completely:

```bash
./venv/bin/python manage.py migrate --run-syncdb  # only if you dropped all tables
# OR drop database and recreate, then:
./venv/bin/python manage.py migrate
```

## Regenerating migrations (developers)

If models change in the future, use normal Django workflow:

```bash
./venv/bin/python manage.py makemigrations
./venv/bin/python manage.py migrate
```

Do not delete `0001_initial.py` on databases that already applied it unless you are intentionally rebasing for another fresh DB cut.
