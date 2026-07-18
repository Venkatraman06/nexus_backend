# PMT — Project Setup Runbook (VM / fresh environment)

End-to-end steps to stand up PMT (Postgres + Redis on the VM, Keycloak + MinIO via
Docker, Django backend, React frontend) from scratch.

## 1. Provision the VM

Install base infra directly on the VM:

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib redis-server
```

Confirm both are running: `systemctl status postgresql redis-server`.

## 2. Create the Postgres database & user

```bash
sudo -u postgres psql
CREATE DATABASE pmt_db;
CREATE USER pmt_user WITH PASSWORD '<choose-a-password>';
GRANT ALL PRIVILEGES ON DATABASE pmt_db TO pmt_user;
```

Note the DB name/user/password — goes into `.env` in step 11.

## 3. Run Keycloak & MinIO via Docker

```bash
docker run -d --name keycloak -p 8080:8080 \
  -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:latest start-dev

docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

Note the Keycloak admin (`admin`/`admin`) and MinIO root (`minioadmin`/`minioadmin`)
credentials.

## 4. Create the Keycloak realm + client

Required before the backend can authenticate at all.

- Log into `http://<vm-ip>:8080`, create a new **realm** (e.g. `pmt`).
- Create a **client** in that realm (confidential, service-accounts enabled), note
  its **Client ID** and **Client Secret**.
- These values go into `.env` in step 11.

## 5. Create the MinIO bucket

The app does not auto-create this.

- In the MinIO console (`http://<vm-ip>:9001`), create a bucket (e.g. `pmt-files`)
  matching `MINIO_BUCKET_NAME`.

## 6. Clone the frontend & backend repos

```bash
git clone <frontend-repo-url>
git clone <backend-repo-url>
```

## 7. Frontend setup

```bash
cd frontend
git checkout dev
npm install
npm run dev
```

## 8. Backend setup — secret key file

Get `secret.key` from a teammate (the Fernet key used to decrypt env files — never
commit it) and place it at `backend/secret.key` (backend root, same level as
`manage.py`).

## 9. Backend setup — virtualenv

```bash
cd backend
git checkout dev
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 10. Decrypt the env file

```bash
python environments/utils/decrypt_env.py
cp environments/decrypted/local.env .env
```

## 11. Fill in the required `.env` values

| Category | Keys |
|---|---|
| Django | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` |
| Postgres | `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` |
| Redis | `REDIS_URL` |
| Keycloak | `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET_KEY`, `KEYCLOAK_TOKEN_CLIENT_ID` |
| MinIO | `MINIO_ENDPOINT_URL`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME` |
| SMTP | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` |

## 12. Run migrations

Must happen before any seed command.

```bash
python manage.py migrate
```

## 13. Seed roles, permissions, and demo data

Pushes the 4 Keycloak groups (**Admin**, **HR & Admin**, **Project Manager**,
**Employee**) and demo employees/projects. See [SEED_DEMO_DATA.md](SEED_DEMO_DATA.md)
for the full breakdown.

```bash
python manage.py seed_demo_data
```

Use `seed_demo_data --reset` to wipe and re-seed later.

## 14. Start backend services

```bash
python manage.py runserver
celery -A core.celery_app worker -l info       # separate terminal
celery -A core.celery_app beat -l info         # separate terminal
```

## 15. Run frontend (if not already running from step 7)

```bash
npm run dev
```

## 16. Reset the first admin password in Keycloak

Go to the realm's **Users** tab → the seeded admin user (e.g. `HIT-001`) →
**Credentials** → reset password, untick "Temporary" if you don't want a forced
change on first login.

## 17. Log into the frontend

`http://<vm-ip>:3000/pmt` with the admin credentials.

## 18. First-login admin tasks

As the first user, set up:

- Masters (Designation, Department, BusinessType, BillingType, etc.)
- Workflow states/transitions (Project Workflow, Ticket Workflow)
- Roles & permissions (`role_permissions.json` → `assign_role_permissions` if you
  need to tweak group→permission mapping)

## 19. Onboard real users

Create employees through the **Employees** module in-app (this syncs them to
Keycloak automatically) rather than creating users directly in the Keycloak
console — keeps Django and Keycloak in sync.

## 20. Employee Performance tab (optional demo data)

After `seed_demo_data`, you can load May–Jun 2026 performance test tickets and
work logs for the Performance tab charts:

```bash
python manage.py seed_employee_performance_demo
# optional: --employee HIT-002 --reset
```

Requires migration `tickets.0006_ticket_assignee_history` (run `migrate` if not
applied). API: `GET /employees/{id}/performance/?period=week|month&from=&to=`.
