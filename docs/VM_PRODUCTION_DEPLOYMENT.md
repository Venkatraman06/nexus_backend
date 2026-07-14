# PMT — VM Production Deployment (nginx + HTTPS)

Extends [SETUP_RUNBOOK.md](SETUP_RUNBOOK.md) for a real, internet-facing VM.
Differences from the local runbook: services run as long-lived **systemd** units
(not foreground `manage.py runserver`), the frontend is built to static files
instead of served by Vite dev server, and **nginx terminates TLS** and reverse
proxies everything under `/pmt`.

This version has been run end-to-end on a real Ubuntu 22.04 VM. Every gotcha
below is something that actually broke on that run, not a hypothetical.

> **Secrets note**: this file is committed to the `backend` git repo. Do not
> paste real passwords into it. Every credential below is a placeholder —
> fill actual values only into `.env` (gitignored) or the VM's root shell.
> If you've ever pasted real VM/DB credentials into a chat session, rotate
> them once the box is stable (`passwd`, `ALTER USER pmt_user WITH PASSWORD
> '...'`) — chat transcripts aren't a secrets store.

## 0. Architecture

```
Internet
  │  :443 (TLS)                 :80 → 301 redirect to :443
  ▼
 nginx  (public, only service exposed to 0.0.0.0)
  ├─ /pmt/api/*      → proxy_pass 127.0.0.1:8000   (gunicorn, systemd: pmt-backend)
  ├─ /pmt/static/*   → alias backend/staticfiles/   (served directly, no Django)
  ├─ /pmt/media/*    → alias backend/media/         (served directly, no Django)
  └─ /pmt/*          → alias frontend/dist/         (SPA, try_files → index.html)

  Optional, admin consoles (see step 5B) — same nginx, separate HTTPS ports
  since there's no domain for subdomain-style routing on a bare IP:
  ├─ :8443 → proxy_pass 127.0.0.1:8080   (Keycloak admin console)
  └─ :9443 → proxy_pass 127.0.0.1:9001   (MinIO console)

Keycloak (8080) and MinIO (9000/9001) — Docker containers bound to 127.0.0.1
only. Not public directly. Reached either via SSH tunnel (step 5A) or the
nginx proxy ports above (step 5B).

Postgres + Redis + MongoDB — installed directly on the VM (apt), bound to
127.0.0.1. MongoDB holds chat messages only (apps/chat) — everything else
stays in Postgres; see step 3B.
```

Only ports **22 (or your custom SSH port), 80, 443**, and — if you set up
step 5B — **8443, 9443** are open to the world.

> **Docker bypasses ufw for published ports.** If a container is run with
> `-p 0.0.0.0:PORT:PORT`, traffic reaches it even with `ufw` enabled and no
> explicit allow rule — Docker inserts its own iptables DNAT/FORWARD rules
> ahead of ufw's INPUT chain. `ufw deny` does **not** protect a
> Docker-published port. The only reliable fix is binding the container's
> port to `127.0.0.1` in the `-p` flag itself (as below) — never rely on ufw
> to firewall a container port that's published on `0.0.0.0`.

## 1. Connect to the VM

```bash
ssh -p 2521 root@103.235.105.35
```

Recommended before going further: create a non-root `deploy` user with sudo,
and disable root SSH login once that's confirmed working. Optional, but do it
before this box is doing anything real — skip if you want to move fast now
and harden later. (The run this doc is based on stayed on root throughout —
fine for a first pass, worth fixing before real traffic.)

## 2. Install packages

```bash
apt update
apt install -y postgresql postgresql-contrib redis-server nginx certbot \
  python3-certbot-nginx git ufw build-essential libpq-dev python3-dev python3-venv
# Docker (for Keycloak + MinIO only)
curl -fsSL https://get.docker.com | sh
```

Confirm: `systemctl status postgresql redis-server nginx docker`.

**Gotcha — apt lock / masked services.** If this VM already had a partial
Docker install attempt (or the SSH session dropped mid-`apt-get`), you can
land in a bad state:

- A stuck `apt-get` process in `T` (stopped, not dead) state holding
  `/var/lib/dpkg/lock-frontend` forever. Check with
  `ps aux | grep apt` — if the process state (column `STAT`) is `T`, resume it
  with `kill -CONT <pid>` rather than killing it; it's usually mid-install,
  not hung.
- `docker.service` / `containerd.service` left `masked` (from a prior
  `apt remove`/reinstall cycle) with `docker.socket` in a `service-start-limit-hit`
  state. Fix in order:
  ```bash
  systemctl unmask docker.service containerd.service docker.socket
  systemctl daemon-reload
  systemctl reset-failed containerd docker.socket docker.service
  systemctl restart containerd
  systemctl restart docker.socket docker.service
  systemctl is-active docker   # should print "active"
  ```

## 3. Postgres database & user

```bash
sudo -u postgres psql
CREATE DATABASE pmt_db;
CREATE USER pmt_user WITH PASSWORD '<the password you were given>';
GRANT ALL PRIVILEGES ON DATABASE pmt_db TO pmt_user;
\c pmt_db
GRANT ALL ON SCHEMA public TO pmt_user;
```

Goes into `.env` in step 9: `DB_HOST=127.0.0.1`, `DB_PORT=5432`,
`DB_NAME=pmt_db`, `DB_USER=pmt_user`, `DB_PASSWORD=...`.

Verify the app-level login actually works (not just that the role exists):

```bash
PGPASSWORD='...' psql -h 127.0.0.1 -U pmt_user -d pmt_db -c 'select current_user;'
```

## 3B. MongoDB (chat message storage)

Chat messages live in MongoDB, not Postgres (`apps/chat/mongo.py`) — everything
else in the app (conversations, membership, all other modules) stays
relational. Ubuntu 22.04's default apt repos don't carry `mongodb-org`
(dropped for licensing reasons), so add MongoDB's own repo first:

```bash
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
  gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  tee /etc/apt/sources.list.d/mongodb-org-7.0.list
apt update
apt install -y mongodb-org
systemctl enable --now mongod
```

By default `mongod` listens on `127.0.0.1:27017` with **no authentication** —
fine for the local laptop runbook, not for a box with a public IP even though
the port itself is never opened in ufw (step 14). Enable auth before this VM
holds real conversations:

```bash
mongosh
> use admin
> db.createUser({ user: "pmt", pwd: "<a real password>", roles: [{ role: "readWrite", db: "pmt" }] })
> exit
```

Then edit `/etc/mongod.conf` and add:

```yaml
security:
  authorization: enabled
```

```bash
systemctl restart mongod
mongosh "mongodb://pmt:<password>@127.0.0.1:27017/pmt" --eval 'db.runCommand({ ping: 1 })'   # {ok: 1} confirms it
```

Goes into `.env` in step 9: `MONGO_HOST=127.0.0.1`, `MONGO_PORT=27017`,
`MONGO_NAME=pmt`, `MONGO_USER=pmt`, `MONGO_PASSWORD=<the password above>`.

## 4. Keycloak & MinIO via Docker — bind to localhost only

Unlike the laptop runbook, do **not** publish these on `0.0.0.0` — nginx and
the backend are the only things that need to reach them, and both run on the
same box. See the ufw/Docker warning in step 0 for why this matters even
with a firewall enabled.

```bash
docker run -d --name keycloak --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:latest start-dev

docker run -d --name minio --restart unless-stopped \
  -p 127.0.0.1:9000:9000 -p 127.0.0.1:9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

Change the admin/root passwords from the defaults before this is anything
other than a scratch box. Neither container has a data volume in the command
above — realm/bucket config lives in the container's writable layer, so
**don't `docker rm` these once configured** (recreating loses everything;
`docker stop`/`start`/`restart` are fine).

Sanity-check nothing is reachable from outside before moving on
(run from your own machine, not the VM):

```bash
for p in 8080 9000 9001; do
  timeout 5 bash -c "echo > /dev/tcp/<vm-ip>/$p" 2>&1 && echo "$p REACHABLE (bad)" || echo "$p blocked (good)"
done
```

## 5A. Reach the Keycloak/MinIO admin UIs via SSH tunnel (default)

From your laptop, since these ports aren't public:

```bash
ssh -p 2521 -L 8080:127.0.0.1:8080 -L 9001:127.0.0.1:9001 root@103.235.105.35
```

Then open `http://localhost:8080` and `http://localhost:9001` locally.

## 5B. Alternative — expose both consoles through nginx (no tunnel needed)

If you'd rather not keep an SSH tunnel open, proxy both consoles through
nginx on **separate HTTPS ports** instead of a `/subpath` — Keycloak and the
MinIO console both generate root-relative asset/redirect URLs and break under
naive subpath reverse-proxying, and there's no domain here for
subdomain-style separation (bare IP).

`/etc/nginx/sites-available/pmt-admin`:

```nginx
server {
    listen 8443 ssl;
    server_name <vm-ip-or-domain>;

    ssl_certificate     /etc/nginx/ssl/pmt.crt;
    ssl_certificate_key /etc/nginx/ssl/pmt.key;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $http_host;          # NOT $host — must keep the :8443 port
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_redirect http:// https://;           # Keycloak doesn't trust X-Forwarded-Proto
    }                                                # by default → issues http:// redirects
}                                                    # without this, nginx then 400s them.

server {
    listen 9443 ssl;
    server_name <vm-ip-or-domain>;

    ssl_certificate     /etc/nginx/ssl/pmt.crt;
    ssl_certificate_key /etc/nginx/ssl/pmt.key;

    location / {
        proxy_pass http://127.0.0.1:9001;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
ln -sf /etc/nginx/sites-available/pmt-admin /etc/nginx/sites-enabled/pmt-admin
nginx -t && systemctl reload nginx
ufw allow 8443/tcp comment 'keycloak-console'
ufw allow 9443/tcp comment 'minio-console'
```

Two gotchas that will bite if skipped:

- **`Host $host` vs `Host $http_host`.** `$host` strips the port. Keycloak
  builds absolute redirect URLs (e.g. after login, to `/admin/`) from the
  `Host` header — strip the port and it redirects to `:443` (the main app),
  producing a 404 there instead of landing back on the admin console.
- **`proxy_redirect http:// https://`.** Keycloak decides the scheme for its
  own redirects based on whether it trusts the proxy (`KC_PROXY_HEADERS`),
  which isn't set on a plain `docker run`. Without this line it issues
  `http://` redirects; since nginx's `8443` listener is TLS-only, the
  browser's follow-up plain-HTTP request to `:8443` gets nginx's own
  `400 The plain HTTP request was sent to HTTPS port`. Don't try to fix this
  by changing the container's env vars — recreating it loses the realm
  config (see step 4). Fixing it in nginx is non-destructive.

Access afterward at `https://<vm-ip>:8443/` (Keycloak) and
`https://<vm-ip>:9443/` (MinIO console) — same self-signed cert as the main
app, so the same browser warning applies.

## 6. Create the Keycloak realm + client

```bash
KC='docker exec keycloak /opt/keycloak/bin/kcadm.sh'
$KC config credentials --server http://127.0.0.1:8080 --realm master --user admin --password admin
$KC create realms -s realm=pmt -s enabled=true

$KC create clients -r pmt \
  -s clientId=pmt-backend \
  -s enabled=true \
  -s publicClient=false \
  -s serviceAccountsEnabled=true \
  -s standardFlowEnabled=true \
  -s directAccessGrantsEnabled=true \
  -s 'redirectUris=["*"]' \
  -i   # prints the client's internal UUID, save it

$KC get clients/<uuid-from-above>/client-secret -r pmt   # → KEYCLOAK_CLIENT_SECRET_KEY
```

**Gotcha — service account needs realm-management rights.** The backend uses
this client's service-account token to manage realm roles/groups
(`create_permissions`, `assign_role_permissions`, employee sync). Without
this, those calls fail with `403 Forbidden`:

```bash
$KC add-roles -r pmt --uusername service-account-pmt-backend \
  --cclientid realm-management --rolename realm-admin
```

**Gotcha — the 4 Keycloak groups don't get created automatically.** Despite
[SEED_DEMO_DATA.md](SEED_DEMO_DATA.md) implying `seed_demo_data` "pushes" the
groups, none of `create_permissions` / `assign_role_permissions` /
`migrate_seed_data` actually create Keycloak **groups** — they only look up
groups that already exist by name and skip silently
(`[SKIP] Keycloak group not found: ...`) if they don't. Create them yourself
*before* running `seed_demo_data`, with names matching `role_permissions.json`
exactly:

```bash
for g in "Admin" "HR & Admin" "Project Manager" "Employee"; do
  $KC create groups -r pmt -s name="$g" -i
done
```

If you only discover this after `seed_demo_data` already ran (employees
created but ungrouped), create the groups then assign membership per the
org chart in [SEED_DEMO_DATA.md](SEED_DEMO_DATA.md) (HIT-001→Admin,
HIT-002→Project Manager, HIT-004→HR & Admin, everyone else→Employee), then
re-run `python manage.py assign_role_permissions` (safe to re-run, it's a
pure mapping step).

## 7. Create the MinIO bucket

```bash
docker exec minio mc alias set local http://127.0.0.1:9000 minioadmin minioadmin
docker exec minio mc mb local/pmt-files
```

## 8. Clone the repos (develop branch)

```bash
mkdir -p /opt/pmt && cd /opt/pmt
git clone -b develop https://github.com/karthicksankark110799/nexus_backend.git backend
git clone -b develop https://github.com/karthicksankark110799/nexus_frontend.git frontend
```

Both repos are private. If cloning over HTTPS with a personal access token,
scrub it from the stored remote right after so it doesn't sit in
`.git/config` on disk:

```bash
git clone -b develop https://<user>:<token>@github.com/karthicksankark110799/nexus_backend.git backend
git -C backend remote set-url origin https://github.com/karthicksankark110799/nexus_backend.git
```

## 9. Backend setup

```bash
cd /opt/pmt/backend
# secret.key from a teammate → /opt/pmt/backend/secret.key
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn   # see gotcha below

python environments/utils/decrypt_env.py
```

**Gotcha — `gunicorn` isn't in `requirements.txt`.** The backend's own
`Dockerfile` CMDs into `gunicorn`, but it's absent from `requirements.txt` —
install it explicitly in the venv (above). Worth fixing upstream in the repo.

`environments/decrypted/` will contain both `local.env` and `prod.env` —
**use `prod.env` as the base** (`DEBUG=False`, production-shaped defaults),
not `local.env`:

```bash
cp environments/decrypted/prod.env .env
```

Then edit `.env`:

| Category | Keys | Notes for this VM |
|---|---|---|
| Django | `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | `ALLOWED_HOSTS=<vm-ip-or-domain>,127.0.0.1,localhost`, `CORS_ALLOWED_ORIGINS=https://<vm-ip-or-domain>` |
| Postgres | `DB_NAME=pmt_db`, `DB_USER=pmt_user`, `DB_PASSWORD`, `DB_HOST=127.0.0.1`, `DB_PORT=5432` | `prod.env`'s template defaults to `DB_HOST=postgres` (a Docker service name) — must be `127.0.0.1` here since Postgres is bare-metal |
| Redis | `REDIS_URL=redis://127.0.0.1:6379/1` | same reason — template default is `redis://redis:6379/1` |
| MongoDB | `MONGO_HOST=127.0.0.1`, `MONGO_PORT=27017`, `MONGO_NAME=pmt`, `MONGO_USER=pmt`, `MONGO_PASSWORD` | from step 3B — `prod.env`'s template defaults to `MONGO_HOST=mongo` (a Docker service name, in case this VM ever runs Mongo in Docker instead); must be `127.0.0.1` here since MongoDB is bare-metal, same reasoning as Postgres/Redis above |
| Keycloak | `KEYCLOAK_SERVER_URL=http://127.0.0.1:8080/`, `KEYCLOAK_REALM=pmt`, `KEYCLOAK_CLIENT_ID=pmt-backend`, `KEYCLOAK_CLIENT_SECRET_KEY`, `KEYCLOAK_TOKEN_CLIENT_ID=pmt-backend` | No `/auth` path prefix on modern Keycloak (24+). `KEYCLOAK_TOKEN_CLIENT_ID` isn't referenced anywhere in current code (grep confirms) — set it the same as `KEYCLOAK_CLIENT_ID` for forward-compatibility, it's harmless either way |
| MinIO | `MINIO_ENDPOINT_URL=http://127.0.0.1:9000`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME=pmt-files` | |
| SMTP | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Leave blank to skip email for now — nothing else depends on it at setup time |

**Gotcha — don't reuse `secret.key`'s value as `SECRET_KEY`.** The
committed `prod.env.enc`/`local.env.enc` templates both decrypt to a
`SECRET_KEY` that's identical to the Fernet `secret.key` used to decrypt
them — two unrelated secrets sharing one value. Generate a fresh one instead:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

```bash
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
```

**Gotcha — `collectstatic` errors on a missing `.map` file.**
`whitenoise.storage.MissingFileError` for
`vendor/bootstrap/js/bootstrap.bundle.min.js.map` (bundled with the
django-jazzmin admin theme). This is pre-existing and already tolerated by
the backend's own `Dockerfile` (`collectstatic ... || true`) — the actual
static files still get copied before the manifest step fails on that one
reference. Non-blocking; ignore the traceback.

```bash
python manage.py seed_demo_data
```

**Gotcha — `seed_pmo_demo` (the last step of `seed_demo_data`) can crash on
a duplicate `LeaveType` name.** `apps/accounts/management/commands/seed_pmo_demo.py`
has two separate leave-type lists that both include "Bereavement Leave"
under different codes (`BRL` vs `BL`); the second one's `get_or_create` only
matches on `code`, so it tries to insert a duplicate `name` and hits
`hrms_leave_type_name_key`'s unique constraint. This is a real bug in the
seed script, reproducible on any fresh database — not VM-specific. Everything
*before* this step in `seed_demo_data` (permissions, workflow, master data,
employees + Keycloak sync, CRM/finance data) is unaffected since
`seed_pmo_demo` runs last. Either patch the `get_or_create` lookup to key on
`name` instead of `code`, or accept the partial demo dataset and move on —
core functionality (login, permissions, employees) doesn't depend on it.

## 10. Backend as a systemd service (gunicorn)

The units below run as `root` for simplicity, matching whatever user cloned
the repo — fine to start, worth switching to a dedicated non-root `deploy`
user (`chown -R deploy:deploy /opt/pmt`, add `User=`/`Group=` lines) once the
box is stable.

`/etc/systemd/system/pmt-backend.service`:

```ini
[Unit]
Description=PMT Django backend (gunicorn)
After=network.target postgresql.service redis-server.service mongod.service docker.service

[Service]
WorkingDirectory=/opt/pmt/backend
EnvironmentFile=/opt/pmt/backend/.env
ExecStart=/opt/pmt/backend/venv/bin/gunicorn core.wsgi:application \
  --bind 127.0.0.1:8000 --workers 4 --timeout 120
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/pmt-celery.service`:

```ini
[Unit]
Description=PMT Celery worker
After=network.target redis-server.service pmt-backend.service

[Service]
WorkingDirectory=/opt/pmt/backend
EnvironmentFile=/opt/pmt/backend/.env
ExecStart=/opt/pmt/backend/venv/bin/celery -A core.celery_app worker -l info
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/pmt-celery-beat.service` — same as above but:

```ini
ExecStart=/opt/pmt/backend/venv/bin/celery -A core.celery_app beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

```bash
systemctl daemon-reload
systemctl enable --now pmt-backend pmt-celery pmt-celery-beat
systemctl status pmt-backend pmt-celery pmt-celery-beat
```

Verify: `curl -I http://127.0.0.1:8000/pmt/api/docs/` → `200`;
`curl -I http://127.0.0.1:8000/pmt/api/v1/` → `401` (correct — unauthenticated).

## 11. Frontend — production build

**Gotcha — check the VM's Node version first.** Fresh Ubuntu 22.04 ships
Node 12 by default, which is far too old for Vite 6. The frontend's own
`Dockerfile` uses Node 20.

```bash
node --version   # if not 18+, upgrade:
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get remove -y --purge nodejs libnode-dev libnode72 npm   # old Ubuntu nodejs conflicts with the new .deb
apt-get autoremove -y
apt-get install -y nodejs
node --version && npm --version
```

```bash
cd /opt/pmt/frontend
npm install --legacy-peer-deps
npm run build      # → dist/, base path already "/pmt" (vite.config.ts)
```

**Gotcha — peer dependency conflict in `package.json`.**
`@tiptap/extension-color@^3.26.0` and `@tiptap/starter-kit@^3.24.0` (which
pulls in `@tiptap/extension-bold@^3.24.0` etc.) pin conflicting exact peer
versions of `@tiptap/core`. Both `npm ci` and plain `npm install` fail with
`ERESOLVE` — matches what the `Dockerfile`'s `npm install` would hit too.
`--legacy-peer-deps` works around it without touching the app's source;
worth aligning the tiptap package versions in the repo when convenient.

No Node process needs to stay running — nginx serves `dist/` as static files
directly. Re-run `npm install --legacy-peer-deps && npm run build` on every
deploy.

## 12. nginx site config

`/etc/nginx/sites-available/pmt`:

```nginx
server {
    listen 80;
    server_name <vm-ip-or-domain>;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name <vm-ip-or-domain>;

    ssl_certificate     /etc/nginx/ssl/pmt.crt;      # or /etc/letsencrypt/... — see step 13
    ssl_certificate_key /etc/nginx/ssl/pmt.key;

    client_max_body_size 25m;

    location /pmt/api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /pmt/static/ {
        alias /opt/pmt/backend/staticfiles/;
    }

    location /pmt/media/ {
        alias /opt/pmt/backend/media/;
    }

    location /pmt/ {
        alias /opt/pmt/frontend/dist/;
        try_files $uri $uri/ /pmt/index.html;
    }

    # both of these are needed — the exact-match `/pmt` (no trailing slash)
    # does NOT fall through to `location /pmt/` in nginx's matching rules,
    # so without it you get a bare 404 on the URL everyone will actually type.
    location = / {
        return 301 /pmt/;
    }
    location = /pmt {
        return 301 /pmt/;
    }
}
```

```bash
ln -sf /etc/nginx/sites-available/pmt /etc/nginx/sites-enabled/pmt
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

## 13. TLS certificate (Let's Encrypt)

Requires a **real domain name pointed at the VM's IP** (Let's Encrypt's
HTTP-01 challenge can't issue for a bare IP). Point an A record at the VM,
then:

```bash
certbot --nginx -d <your-domain>
```

Certbot rewrites the config from step 12 in place and sets up auto-renewal
(`systemctl status certbot.timer`).

**No domain yet?** Self-signed cert as a stopgap — browsers show an
untrusted-cert warning until you switch to a real domain + Let's Encrypt,
but the transport is still genuinely encrypted end-to-end:

```bash
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/pmt.key -out /etc/nginx/ssl/pmt.crt \
  -subj "/CN=<vm-ip>"
```

This is what step 12's config above already points at.

## 14. Firewall

```bash
ufw allow 2521/tcp    # SSH — do this FIRST or you'll lock yourself out
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status verbose
```

Postgres (5432), Redis (6379), MongoDB (27017) are bare-metal and bound to
`127.0.0.1` — ufw is belt-and-suspenders there. Keycloak/MinIO are **Docker-published** ports
bound to `127.0.0.1` in step 4's `-p` flags — that binding is what actually
protects them (re-read the warning in step 0: ufw alone does not block
Docker-published ports even on `0.0.0.0`).

## 15. Verify

```bash
curl -kI https://<vm-ip-or-domain>/pmt/
curl -k https://<vm-ip-or-domain>/pmt/api/v1/ -o /dev/null -w '%{http_code}\n'   # expect 401
curl -kI http://<vm-ip-or-domain>/pmt/ -w '%{http_code}\n'                       # expect 301
for p in 8080 9000 9001 8000 27017; do
  timeout 5 bash -c "echo > /dev/tcp/<vm-ip>/$p" 2>&1 && echo "$p REACHABLE (bad)" || echo "$p blocked (good)"
done
```

Then browse to `https://<vm-ip-or-domain>/pmt` and log in.

## 16. First-login admin tasks / onboarding

Same as [SETUP_RUNBOOK.md](SETUP_RUNBOOK.md) steps 16–20: reset the seeded
admin's Keycloak password, set up masters/workflow states/roles, onboard real
employees through the app (not the Keycloak console directly). Also rotate
the Keycloak admin (`admin`/`admin`) and MinIO root (`minioadmin`/`minioadmin`)
credentials — especially if you set up step 5B, since they're now reachable
from the internet (behind TLS, but still default creds).

## 17. Redeploys

```bash
cd /opt/pmt/backend && git pull && source venv/bin/activate && \
  pip install -r requirements.txt && python manage.py migrate && \
  python manage.py collectstatic --noinput && systemctl restart pmt-backend pmt-celery pmt-celery-beat

cd /opt/pmt/frontend && git pull && npm install --legacy-peer-deps && npm run build
```
