# PMT Backend — Setup Guide

## Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- MinIO (or S3-compatible storage)
- Keycloak (identity provider)

---

## 1. Clone & Create Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 2. Environment Configuration

### Step 1 — Get the secret key

Obtain `secret.key` from a team member (never committed to git) and place it at:

```
backend/secret.key
```

### Step 2 — Decrypt environment files

```bash
python environments/utils/decrypt_env.py
```

This reads the encrypted `environments/*.env.enc` files and writes plain-text files into `environments/decrypted/`.

### Step 3 — Copy the env file for your target environment

```bash
# For local development
cp environments/decrypted/local.env .env

# For production
cp environments/decrypted/prod.env .env
```

### (Optional) Encrypt after editing

If you update a `.env` file in `environments/decrypted/`, re-encrypt before committing:

```bash
python environments/utils/encrypt_env.py
```

---

## 3. Database Setup

```bash
# Create the database (once)
psql -U postgres -c "CREATE DATABASE pmt_db;"

# Run migrations
python manage.py migrate
```

---

## 4. Load Initial Data (if any)

```bash
python manage.py loaddata permissions.json
```

---

## 5. Run the Development Server

```bash
python manage.py runserver
```

API will be available at `http://localhost:8000`.

---

## 6. Run Celery Worker (background tasks)

```bash
celery -A core worker -l info
```

---

## Environment Variables Reference

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for local, `False` for production |
| `DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT` | PostgreSQL connection |
| `REDIS_URL` | Redis URL for Celery |
| `KEYCLOAK_SERVER_URL` | Keycloak base URL |
| `KEYCLOAK_REALM` | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | Keycloak client ID |
| `KEYCLOAK_CLIENT_SECRET_KEY` | Keycloak client secret |
| `MINIO_ENDPOINT_URL` | MinIO/S3 endpoint |
| `MINIO_ACCESS_KEY / MINIO_SECRET_KEY` | MinIO credentials |
| `MINIO_BUCKET_NAME` | Storage bucket name |
| `EMAIL_HOST / EMAIL_PORT / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD` | SMTP config |
| `TIME_ZONE` | Django timezone (default: `Asia/Kolkata`) |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins |
