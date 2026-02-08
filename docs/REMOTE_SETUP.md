# Remote VM one-click setup

Deploy Project Inside on a single VM **without Docker**: backend (systemd + Python 3.12), frontend (Nginx + built Vite app), Postgres and Redis installed on the host.

**The setup script runs on the remote machine.** SSH into the VM, clone the repo, then run the script there.

## Prerequisites

- VM is Ubuntu/Debian (apt) or RHEL/CentOS (yum/dnf)
- Ports: **80** (Nginx), **8000** (backend), **5432** (Postgres), **6379** (Redis)

## One-click script

On the **remote VM**, clone the repo then run from the repo root (use `sudo` so the script can install packages and write to `/etc`):

```bash
git clone -b main https://github.com/your-org/project_inside.git /opt/project_inside
cd /opt/project_inside
sudo ./scripts/remote_setup.sh
```

The script will (all on this machine, no Docker):

1. Install **nginx**, **postgresql**, **redis** (and start them)
2. Create Postgres user `project_inside` and database `project_inside`
3. **Use `backend/.env.example`** as the backend env base, set **DATABASE_URL** for host Postgres (port 5432), apply `--domain` for CORS/APP_PUBLIC_URL, and **prompt only for API keys that are not present** (SECRET_KEY, GEMINI_API_KEY, OPENAI_API_KEY, SENDGRID_API_KEY, GOOGLE_APPLICATION_CREDENTIALS_JSON) unless you pass `--backend-env`
4. Write backend env to `/etc/project_inside/backend.env`
5. Run **backend install** (Python 3.12, venv, requirements, migrations, systemd)
6. Install **Node 22** if needed, then **build the frontend** (Vite) with `VITE_API_BASE_URL`
7. Copy frontend build to **/var/www/project_inside** and configure **Nginx** to serve it and proxy `/v1` to the backend

### Options

| Option | Description |
|--------|-------------|
| `--domain https://app.example.com` | Public domain; used for CORS, APP_PUBLIC_URL, and VITE_API_BASE_URL |
| `--api-base URL` | Override API base URL for frontend build (default: same as `--domain`) |
| `--backend-env FILE` | Use this file as backend env instead of prompting |
| `--frontend-env FILE` | Use this file for VITE_API_BASE_URL instead of prompting |

### Examples

With domain (fewer prompts):

```bash
cd /opt/project_inside
sudo ./scripts/remote_setup.sh --domain https://app.example.com
```

Use existing env files (no prompts):

```bash
sudo ./scripts/remote_setup.sh --domain https://app.example.com \
  --backend-env ./my-backend.env \
  --frontend-env ./mobile/.env.production
```

## Env templates

- **Backend:** [deploy/backend.env.example](../deploy/backend.env.example) — or pass with `--backend-env`
- **Frontend:** [deploy/frontend.env.example](../deploy/frontend.env.example) — for `VITE_API_BASE_URL` at build time

Backend env is built from **`backend/.env.example`**. The script sets **DATABASE_URL** to `postgresql+asyncpg://project_inside:postgres@localhost:5432/project_inside` for the host Postgres. With `--domain`, CORS_ORIGINS and APP_PUBLIC_URL are set from the domain. You are **only prompted for API keys that are empty or placeholder**: SECRET_KEY, GEMINI_API_KEY, OPENAI_API_KEY, SENDGRID_API_KEY, GOOGLE_APPLICATION_CREDENTIALS_JSON.

## Backend on host (Python 3.12)

- **Install script:** `deploy/backend_install.sh` (run by `remote_setup.sh`)
- **Systemd unit:** `project_inside_backend.service` (port 8000)
- **Env file:** `/etc/project_inside/backend.env`
- **Venv:** `/opt/project_inside/backend/.venv`
- **Requirements:** `requirements-do.txt` by default; set `REQUIREMENTS_FILE=requirements-full.txt` for full STT/NeMo features

## Frontend and services on host (no Docker)

- **Frontend:** Nginx serves `/var/www/project_inside` (Vite build) and proxies `/v1/` and WebSockets to `http://127.0.0.1:8000`
- **Config:** `deploy/nginx-host.conf` is installed as the Nginx site
- **Postgres:** port 5432, database `project_inside`, user `project_inside` (password `postgres`)
- **Redis:** port 6379

## HTTPS Setup (Required for Microphone Access)

Browsers require HTTPS to access the microphone API. You have two options:

### Option 1: Let's Encrypt (Production - Recommended)

If you have a domain name pointing to your server:

```bash
sudo ./deploy/setup_https.sh your-domain.com
```

This will:
- Install certbot
- Obtain a free SSL certificate from Let's Encrypt
- Configure Nginx for HTTPS
- Set up automatic certificate renewal

After setup, rebuild the frontend with the HTTPS URL:

```bash
cd /opt/project_inside/mobile
VITE_API_BASE_URL=https://your-domain.com npm run build
sudo cp -r dist/. /var/www/project_inside/
```

### Option 2: Self-Signed Certificate (Testing Only)

For testing without a domain (browsers will show a security warning):

```bash
sudo ./deploy/setup_https_selfsigned.sh
```

Then access via `https://<vm-ip>`. You'll need to accept the browser security warning:
- **Chrome/Edge:** Click "Advanced" → "Proceed to <ip> (unsafe)"
- **Safari:** Click "Show Details" → "visit this website"
- **Firefox:** Click "Advanced" → "Accept the Risk and Continue"

After setup, rebuild the frontend with the HTTPS URL:

```bash
cd /opt/project_inside/mobile
VITE_API_BASE_URL=https://<vm-ip> npm run build
sudo cp -r dist/. /var/www/project_inside/
```

## Updating server and web code

After the initial setup, use the one-click update script on the VM (from repo root, with `sudo`):

```bash
cd /opt/project_inside
sudo ./scripts/remote_update.sh
```

This will:

1. **Pull** latest code (`git pull`)
2. **Backend:** run `deploy/backend_install.sh` (venv, requirements, migrations, systemd) and restart the backend service
3. **Frontend:** build the Vite app (using `APP_PUBLIC_URL` from `/etc/project_inside/backend.env` as `VITE_API_BASE_URL`) and copy to `/var/www/project_inside`
4. **Nginx:** copy updated `deploy/nginx-host.conf` and reload nginx

**Options:**

| Option | Description |
|--------|-------------|
| `--backend-only` | Update only backend (pull, install, restart); skip frontend build |
| `--frontend-only` | Update only frontend (pull, build, copy); skip backend |
| `--no-pull` | Skip `git pull` (e.g. you deployed from a tarball or already pulled) |

**API URL for frontend (avoids blank site):** The update script **never overwrites** `/etc/project_inside/backend.env` or `/etc/project_inside/frontend.env`. It reads `VITE_API_BASE_URL` from (in order): `frontend.env`, then `APP_PUBLIC_URL` in `backend.env`, then repo `mobile/.env.production`. After each frontend build it **saves** the value used into `frontend.env` so the next update keeps the same URL. If the site is blank or "Cannot connect", set the URL explicitly:

```bash
# On the VM (use your domain)
echo 'VITE_API_BASE_URL=https://se-ai.live' | sudo tee /etc/project_inside/frontend.env
# Then rebuild frontend (or run update again)
cd /opt/project_inside && sudo ./scripts/remote_update.sh --frontend-only
```

## Validation

- Open `http://<vm-ip>` (or `https://<domain>` after HTTPS setup) in a browser — frontend should load
- `curl http://<vm-ip>/v1/health` — backend health (proxied via Nginx)
- Backend logs: `journalctl -u project_inside_backend -f`
- **Web log viewer** (optional): To serve logs at `https://<domain>:8888/logs`, run the log viewer as a service:
  ```bash
  sudo cp deploy/log_viewer.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now log_viewer.service
  ```
  Then open `http://<vm-ip>:8888/logs` or `https://<domain>:8888/logs` (ensure port 8888 is open in firewall if needed).

## Troubleshooting

- **Blank site or "environment vars overwritten":** The update script does not overwrite `/etc/project_inside/backend.env` or `frontend.env`. If the site is blank, the frontend was likely built with wrong or empty `VITE_API_BASE_URL`. On the VM: set `echo 'VITE_API_BASE_URL=https://your-domain.com' | sudo tee /etc/project_inside/frontend.env`, then run `sudo ./scripts/remote_update.sh --frontend-only` to rebuild and redeploy. The script now saves the URL used into `frontend.env` after each build so it persists.
- **"Cannot connect to server" (API base: https://se-ai.live or your domain):** The frontend cannot reach the backend. (1) Backend running? `systemctl status project_inside_backend` and `curl -s http://localhost/v1/health`. (2) If you use **HTTPS** and it worked before: the update script may have overwritten your Nginx config with an HTTP-only one. **Restore HTTPS** on the VM: `cd /opt/project_inside && sudo ./deploy/setup_https.sh se-ai.live` (use your domain). Then reload: `sudo nginx -t && sudo systemctl reload nginx`. (3) Ensure `/etc/project_inside/backend.env` has `APP_PUBLIC_URL` and `CORS_ORIGINS` for your domain (e.g. `https://se-ai.live`).
- **"Microphone is not available" error:** Browsers require HTTPS for microphone access. Set up HTTPS using one of the options above (Let's Encrypt for production, self-signed for testing).
- **Live Coach / STT stream 405 Method Not Allowed:** The browser sends a WebSocket upgrade (GET with `Upgrade: websocket`). If Nginx forwards the request without those headers, the backend returns 405. **Fix:** Your Nginx site config (HTTP: `deploy/nginx-host.conf`; HTTPS: the one from `setup_https.sh`) must have **dedicated** `location` blocks for the STT WebSockets (so they get `Upgrade` and `Connection "upgrade"`), not only a generic `location /v1/`. **Quick fix:** `cd /opt/project_inside && sudo ./deploy/nginx_ensure_stt_websocket.sh` — adds the STT WebSocket location blocks to the main config and to Certbot’s `project_inside-le-ssl.conf` if present, then reloads Nginx. If 405 persists after one run, pull the latest script (it now patches the SSL config file too) and run it again. Or re-run full HTTPS setup: `sudo ./deploy/setup_https.sh YOUR_DOMAIN` then `sudo nginx -t && sudo systemctl reload nginx`. If you don’t use HTTPS, ensure `deploy/nginx-host.conf` is installed and includes the `location /v1/stt/stream/` and `location /v1/stt-v2/stream/` blocks with `proxy_set_header Upgrade $http_upgrade` and `proxy_set_header Connection "upgrade"`.
- **CORS errors:** Ensure `CORS_ORIGINS` in `/etc/project_inside/backend.env` includes your frontend origin and that `VITE_API_BASE_URL` matches.
- **502 Bad Gateway:** Backend may not be up; check `systemctl status project_inside_backend` and `journalctl -u project_inside_backend -n 50`
- **Postgres connection refused:** Ensure `pg_hba.conf` allows local connections (e.g. `host project_inside project_inside 127.0.0.1/32 md5`) and Postgres is listening on 127.0.0.1:5432
- **Python 3.12 not found:** The script installs it via deadsnakes PPA (Ubuntu) or yum/dnf; run with sudo
